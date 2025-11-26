import asyncio
import json
import random
import re
import string
import uuid
from datetime import datetime
from typing import List, Dict, TypedDict, Optional, Any

import dateparser
from rapidfuzz import process
from livekit.rtc.participant import LocalParticipant
from livekit.agents import Agent, RunContext, ChatContext
from livekit.agents.llm import function_tool
from dataclasses import dataclass
from supabase import create_client, Client

# SUPABASE_URL = os.getenv("SUPABASE_URL")
# SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxoZmRvZ29lZnJ3dG5oZHRpYnNoIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjA0NTIxNzgsImV4cCI6MjA3NjAyODE3OH0.mIpn-FbyvbobjxzF_Zb5nL2yPAa61Ke3Ed78LZC5pQ0"
SUPABASE_URL = "https://lhfdogoefrwtnhdtibsh.supabase.co"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


@dataclass
class SessionData:
    from_city: Optional[str] = None
    to_city: Optional[str] = None
    from_city_code: Optional[str] = None
    to_city_code: Optional[str] = None
    available_flights: Optional[List[Dict[str, Any]]] = None
    passengers: Optional[List[Dict[str, Any]]] = None
    selected_flight: Optional[Dict[str, Any]] = None
    flight_class: Optional[str] = None
    trip_type: Optional[str] = None
    departure_date: Optional[str] = None
    return_date: Optional[str] = None
    payment_confirmed: bool = False
    payment_summary: Optional[Dict[str, Any]] = None
    _kids_asked: bool = False
    # ==== FOOD ORDERING ====
    selected_area: str | None = None
    selected_restaurant: dict | None = None
    available_restaurants: list | None = None
    menu_items: list | None = None
    cart: List[Dict] | None = None
    delivery_address: dict | None = None
    food_payment_summary: dict | None = None
    food_order_confirmed: bool = False
    payment_method: str | None = None


class PassengerDetail(TypedDict):
    name: str
    age: int
    type: str  # "adult" or "kid"
    passport_number: str | None  # optional


def json_response(status: str, action: int, message: str = None, data=None):
    return {
        "status": status,
        "action": action,
        "message": message,
        "data": data,
    }


def _get_userdata(context: RunContext) -> SessionData:
    if "userdata" not in context.session.userdata:
        print("Userdata not found, using default values")
        context.session.userdata["userdata"] = SessionData()
        context.session.userdata["userdata"].passengers = [{"type": "adult", "count": 0}, {"type": "kid", "count": -1}]
    return context.session.userdata["userdata"]


CITIES = [
    {"city": "Riyadh"},
    {"city": "Kuwait City"},
    {"city": "Abu Dhabi"},
    {"city": "Jeddah"},
    {"city": "Muscat"},
    {"city": "Manama"},
    {"city": "Dubai"},
    {"city": "Doha"}
]


def fuzzy_match_city(user_input: str):
    """Match city with typos using your exact fuzzy_match"""
    return fuzzy_match(user_input, CITIES, "city", threshold=68)


AIRLINES = [
    {"airline": "Flynas"},
    {"airline": "Kuwait Airways"},
    {"airline": "Qatar Airways"},
    {"airline": "FlyDubai"},
    {"airline": "Emirates"},
    {"airline": "Flyadeal"},
    {"airline": "Oman Air"},
    {"airline": "Gulf Air"},
    {"airline": "Saudia"},
    {"airline": "Etihad Airways"}
]


def fuzzy_match_airline(user_input: str):
    """Fuzzy match airline name (handles 'Qatar', 'Etihad', 'Emirates', etc.)"""
    return fuzzy_match(user_input, AIRLINES, "airline", threshold=68)


def fuzzy_match(user_input: str, choices: list, key: str, threshold: int = 70):
    if not choices:
        return None
    user_input = user_input.strip().lower()
    names = [item[key].lower() for item in choices]
    result = process.extractOne(user_input, names)
    if result is None:
        return None
    match_str, score, _ = result
    if score >= threshold:
        index = names.index(match_str)
        return choices[index]
    return None


class Assistant(Agent):
    city_cache = None

    def __init__(self, participant=LocalParticipant):
        self.participant = participant
        super().__init__(
            instructions="""
                You are a helpful voice assistant that can book flights, order food, book hotels and book a ride.
                You speak in short, natural, friendly sentences. You are allowed to use normal punctuation.
                
                There are TWO completely separate flows:
                1. Flight booking
                2. Food delivery
                
                Detect intent from the very first words:
                • If user mentions flight, fly, airport, ticket, travel, departure, Dubai, London, etc. → start FLIGHT flow
                • If user says food, hungry, order, restaurant, pizza, burger, shawarma, delivery, etc. → start FOOD flow
                
                If the user switches from one flow to the other, immediately drop the old flow and start the new one from scratch. Do not mix them.
                
                FLIGHT FLOW (natural, one thing at a time – exactly as implemented):

                → When user wants to book a flight, immediately start collect_flight_details tool
                → The tool will ask ONLY ONE question at a time in this exact order:
                
                1. Where are you flying from?
                2. And to which city?
                3. When do you want to fly? (accepts any natural date: "tomorrow", "next Friday", "25 December", etc.)
                4. One-way or round-trip?
                   → If round-trip → automatically ask: "What’s your return date?"
                5. How many adults? (minimum 1)
                6. Any kid? Say zero or none if not. (asked only once – zero is fully accepted)
                7. Economy, Premium Economy, or Business class?
                
                → When ALL info is collected → automatically call search_and_show_flights
                → Show numbered list of available flights
                   Example:
                   1. Jazeera Airways to Dubai at 14:30 – 28.500 KWD
                   2. FlyDubai to Dubai at 18:15 – 32.000 KWD
                   3. Kuwait Airways to London at 09:00 – 98.750 KWD
                
                → User can now pick by:
                   • Number: "number 2", "option 1", "3"
                   • City name: "Dubai", "London", "Istanbul"
                   • Airline name: "Jazeera", "Emirates", "FlyDubai", "Kuwait Airways"
                   → All handled automatically by select_flight tool using fuzzy matching
                
                → After selection → show total price (per passenger × count)
                → Call show_flight_payment → ask: "How would you like to pay — KNET, or Visa?"
                → Show final total → "Confirm your flight?"
                → If yes → call confirm_flight_booking → booking saved + confirmation message
                
                FOOD FLOW (updated – matches our final implementation):
                → Immediately call show_all_restaurants (no area needed)
                → Show all restaurants with numbers + their cuisine and area in brackets
                → User can pick by number OR by saying the restaurant name (even with typos)
                → Call select_restaurant (supports both number and fuzzy name)
                → Show full menu with numbers
                → User adds items freely by saying:
                   • “two cheeseburgers”
                   • “number 5”
                   • “three shawarmas please”
                   • “one of each”
                   → Call add_to_cart – it understands numbers, names, and spoken quantities automatically
                → User can keep adding items as long as they want
                → When user says “done”, “that’s all”, “checkout”, “pay”, or “enough” → call show_payment_summary_food
                → Ask payment method only if not given (KNET / Visa / Cash)
                → Show final total with delivery fee (0.750 KWD) → ask “Confirm order?”
                
                General Rules:
                • Always speak in short, natural, friendly sentences.
                • Never list or ask for everything at once.
                • Only ask one thing at a time.
                • You may (and should) use function calling – that is expected and correct.
                • Be very forgiving with spelling (e.g. “salmia” = Salmiya, “shawerma” = shawarma).
                • Be extremely forgiving with spelling (Dubia, Londn, Jazira, Emirats → all work)
                • Zero kid is valid and accepted silently
                • Never mention tool names to user
                • If something is unclear, just ask again nicely.
                • Be friendly, patient, and fast.
                """
        )
        self.ride_bookings = []
        self.food_orders = []
        self.flight_bookings = []
        self.hotel_bookings = []

    async def _load_city_cache(self):
        if self.city_cache is None:
            response = supabase.table("flights") \
                .select("from_city, from_city_code, to_city, to_city_code") \
                .execute()

            cache = {}
            for row in response.data:
                cache[row["from_city"].strip().lower()] = row["from_city_code"]
                cache[row["to_city"].strip().lower()] = row["to_city_code"]

            self.city_cache = cache

    async def _publish(self, payload: dict):
        await self.participant.publish_data(
            payload=json.dumps(payload).encode("utf-8"),
            reliable=True
        )
        print(payload)

    async def fetch_city_code(self, city_name: str, field: str):
        if not city_name:
            return None

        await self._load_city_cache()

        key = city_name.strip().lower()
        if key in self.city_cache:
            return city_name.strip(), self.city_cache[key]

        return None

    # ──────────────────────────────────────────────────────────────
    # 1. Collect flight details – one field at a time
    # ──────────────────────────────────────────────────────────────
    @function_tool()
    async def collect_flight_details(
            self,
            context: RunContext,
            from_city: str | None = None,
            to_city: str | None = None,
            departure_date: str | None = None,
            trip_type: str | None = None,
            return_date: str | None = None,
            adults: int | None = None,
            kids: int | None = None,
            flight_class: str | None = None
    ):
        """
        Collect flight info naturally. Ask only ONE question at a time.
        Accept natural dates, class names, and numbers.
        Zero children is perfectly valid — do NOT ask again after user says "none".
        """
        userdata = _get_userdata(context)

        # Initialize flight session
        if not hasattr(userdata, "passengers"):
            userdata.passengers = [{"type": "adult", "count": 1}]
            userdata.flight_class = "economy"
            userdata.trip_type = "one-way"
            userdata._kids_asked = False

        # Update fields
        if from_city:
            matched = fuzzy_match_city(from_city)
            if not matched:
                return json_response("partial", 1, "I didn't catch the departure city. Can you repeat?")
            userdata.from_city = matched["city"].strip().title()
            city_result = await self.fetch_city_code(userdata.from_city, field="from_city")
            if not city_result:
                # Ask user to re-enter city name
                res = json_response(
                    "partial", 1,
                    f"I couldn’t find any flights from '{userdata.from_city}'. Can you recheck the city name?",
                    {"missing_field": "from_city"}
                )
                return res
            canonical_name, city_code = city_result
            userdata.from_city_code = city_code
        if to_city:
            matched = fuzzy_match_city(to_city)
            if not matched:
                return json_response("partial", 1, "Which city are you flying to?")
            userdata.to_city = matched["city"].strip().title()
            city_result = await self.fetch_city_code(userdata.to_city, field="to_city")
            if not city_result:
                res = json_response(
                    "partial", 1,
                    f"Couldn’t find any flights to '{userdata.to_city}'. Please confirm or spell it differently.",
                    {"missing_field": "to_city"}
                )
                return res
            canonical_name, city_code = city_result
            userdata.to_city_code = city_code
        if departure_date:
            parsed = dateparser.parse(departure_date, settings={'PREFER_DATES_FROM': 'future'})
            if not parsed:
                return json_response("partial", 1, "When do you want to fly?")
            userdata.departure_date = parsed.strftime("%Y-%m-%d")
        if return_date:
            parsed = dateparser.parse(return_date, settings={'PREFER_DATES_FROM': 'future'})
            if not parsed:
                return json_response("partial", 1, "When are you coming back?")
            userdata.return_date = parsed.strftime("%Y-%m-%d")
        if trip_type:
            clean = trip_type.lower()
            userdata.trip_type = "round trip" if any(w in clean for w in ["round", "return", "back"]) else "one-way"
        if adults is not None:
            count = max(1, int(adults))
            adult = next((p for p in userdata.passengers if p["type"] == "adult"), None)
            if adult:
                adult["count"] = count
            else:
                userdata.passengers.append({"type": "adult", "count": count})
        if kids is not None:
            count = max(0, int(kids))
            kid = next((p for p in userdata.passengers if p["type"] == "kid"), None)
            if kid:
                kid["count"] = count
            elif count > 0:
                userdata.passengers.append({"type": "kid", "count": count})
            userdata._kids_asked = True  # mark as asked
        if flight_class:
            clean = flight_class.lower()
            if "business" in clean:
                userdata.flight_class = "business"
            elif "premium" in clean:
                userdata.flight_class = "premium economy"
            else:
                userdata.flight_class = "economy"

        # Ask next missing field (in perfect order)
        if not getattr(userdata, "from_city", None):
            return json_response("partial", 1, "Where are you flying from?")
        if not getattr(userdata, "to_city", None):
            return json_response("partial", 1, "And to which city?")
        if not getattr(userdata, "departure_date", None):
            return json_response("partial", 1, "When do you want to fly?")
        if not getattr(userdata, "trip_type", None):
            return json_response("partial", 1, "One-way or round-trip?")

        if userdata.trip_type == "round trip" and not getattr(userdata, "return_date", None):
            return json_response("partial", 1, "What’s your return date?")

        adults_count = next((p["count"] for p in userdata.passengers if p["type"] == "adult"), 0)
        if adults_count < 1:
            return json_response("partial", 1, "How many adults?")

        if not userdata._kids_asked:
            userdata._kids_asked = True
            return json_response("partial", 1, "Any children? Say zero or none if not.")

        if not getattr(userdata, "flight_class", None):
            return json_response("partial", 1, "Economy, Premium Economy, or Business class?")

        res = json_response("success",
                            1,
                            "",
                            {
                                "from_city": userdata.from_city,
                                "to_city": userdata.to_city,
                                "from_city_code": userdata.from_city_code,
                                "to_city_code": userdata.to_city_code,
                                "departure_date": userdata.departure_date,
                                "flight_class": userdata.flight_class,
                                "adults": next((p["count"] for p in userdata.passengers if p["type"] == "adult"), 1),
                                "kids": next((p["count"] for p in userdata.passengers if p["type"] == "kid"), 0),
                                "trip_type": userdata.trip_type,
                                "return_date": userdata.return_date
                            })
        await self._publish(res)
        return res

    @function_tool()
    async def search_and_show_flights(self, context: RunContext):
        """Search and show available flights with numbers"""
        userdata = _get_userdata(context)

        flights = supabase.table("flights") \
                      .select("*") \
                      .ilike("from_city", userdata.from_city) \
                      .ilike("to_city", userdata.to_city) \
                      .execute().data or []

        if not flights:
            return json_response("error", 2,
                                 f"Sorry, no flights from {userdata.from_city} to {userdata.to_city} on that date.")

        userdata.available_flights = flights

        list_text = "\n".join(
            f"{i + 1}. {f['airline']} → {f['to_city']} at {f['departure_time']} – {f['price']:.3f} {f['currency']}"
            for i, f in enumerate(flights)
        )
        res = json_response("success", 2,
                            f"Found {len(flights)} flights:\n\n{list_text}\n\nWhich one? Say the number or city.",
                            {
                                "from_city": userdata.from_city,
                                "to_city": userdata.to_city,
                                "departure_date": userdata.departure_date,
                                "return_date": userdata.return_date,
                                "available_flights": userdata.available_flights,
                                "passengers": userdata.passengers,
                                "trip_type": userdata.trip_type
                            })
        await asyncio.sleep(2)
        await self._publish(res)
        return res

    @function_tool()
    async def select_flight(self, context: RunContext, user_input: str):
        """User selects flight by number or airline name (typo tolerant)"""
        userdata = _get_userdata(context)
        if not userdata.available_flights:
            return json_response("error", 3, "No flights to choose from.")

        flight = None
        if user_input.strip().isdigit():
            idx = int(user_input.strip()) - 1
            if 0 <= idx < len(userdata.available_flights):
                flight = userdata.available_flights[idx]

        if not flight:
            airline_match = fuzzy_match_airline(user_input)
            if airline_match:
                airline_name = airline_match["airline"]
                flight = next((f for f in userdata.available_flights if f["airline"] == airline_name), None)

        if not flight:
            flight = fuzzy_match(user_input, userdata.available_flights, "airline", threshold=68)

        if not flight:
            return json_response("error", 3, "Didn't find that. Try the number, city, or airline again.")

        userdata.selected_flight = flight
        total_passengers = sum(p["count"] for p in userdata.passengers)
        price_str = flight.get("price", "0")
        try:
            price = float(price_str)
        except (ValueError, TypeError):
            price = 0.0
        total_price = round(price * total_passengers, 3)
        res = json_response("success", 3,
                            f"Selected {flight['airline']} to {flight['to_city']}\n"
                            f"{total_passengers} passenger(s) × {flight['price']} = {total_price:.3f} {flight['currency']}\n\n"
                            f"Ready to book?",
                            {"selected_flight": flight, "passenger_count": total_passengers})
        await self._publish(res)
        return res

    @function_tool()
    async def show_flight_payment(self, context: RunContext, payment_method: str | None = None):
        """Show final price and ask for payment method"""
        userdata = _get_userdata(context)
        if not userdata.selected_flight:
            return json_response("error", 5, "No flight selected yet.")

        if payment_method:
            userdata.payment_method = payment_method.strip().title()

        if not getattr(userdata, "payment_method", None):
            return json_response("partial", 5, "How would you like to pay — KNET, Visa")

        price = float(userdata.selected_flight.get("price", 0) or 0)
        total_passengers = sum(p["count"] for p in userdata.passengers)
        total = round(price * total_passengers, 3)

        userdata.payment_summary = {
            "total_price": total,
            "currency": userdata.selected_flight.get("currency", "KWD"),
            "flight": userdata.selected_flight,
            "class": userdata.flight_class,
            "trip_type": userdata.trip_type,
            "paymentMethod": userdata.payment_method,
        }
        res = json_response("success", 5,
                            f"Total: {total:.3f} {userdata.selected_flight['currency']}\n\nConfirm your flight?",
                            {"payment_summary": userdata.payment_summary})
        await self._publish(res)
        return res

    @function_tool()
    async def confirm_flight_booking(self, context: RunContext, confirm: bool = True):
        """Save booking to Supabase"""
        if not confirm:
            return json_response("error", 6, "Booking cancelled.")

        userdata = _get_userdata(context)
        flight = userdata.selected_flight

        if not userdata.payment_summary or "total_price" not in userdata.payment_summary:
            # Recalculate just in case
            price = float(flight.get("price", 0) or 0)
            total_passengers = sum(p["count"] for p in userdata.passengers)
            total_price = round(price * total_passengers, 3)
        else:
            total_price = userdata.payment_summary["total_price"]

        booking_data = {
            "booking_type": "flight",
            "user_id": str(uuid.uuid4()),
            "item_id": flight["id"],
            "booking_details": json.dumps({
                "trip_type": userdata.trip_type,
                "departure_date": userdata.departure_date,
                "return_date": userdata.return_date,
                "passengers": userdata.passengers,
                "class": userdata.flight_class,
                "flight": flight
            }),
            "payment_status": "Confirmed",
            "total_price": total_price,
            "currency": flight["currency"],
            "booking_date": datetime.now().isoformat(),
            "start_date": userdata.departure_date,
            "end_date": userdata.return_date if userdata.trip_type == "round trip" else None
        }

        result = supabase.table("bookings").insert(booking_data).execute()
        booking_id = result.data[0].get("booking_id", "FL123") if result.data else "TEMP"
        res = json_response(status="success", action=6,
                            message=f"Flight booked!\nBooking ID: {booking_id}\nHave a great trip to {userdata.to_city}!",
                            data=result.data[0])
        await self._publish(res)
        await self.update_chat_ctx(ChatContext())
        return res

    # ===================== FOOD ORDERING FLOW =====================

    @function_tool()
    async def show_all_restaurants(self, context: RunContext):
        """Show all active restaurants instantly"""
        userdata = _get_userdata(context)

        restaurants = supabase.table("restaurants") \
                          .select("*") \
                          .execute().data or []

        if not restaurants:
            return json_response("error", 8, "No restaurants available right now.")

        userdata.available_restaurants = restaurants
        userdata.selected_restaurant = None
        userdata.payment_method = None
        userdata.menu_items = None
        userdata.cart = []

        msg = "Here are all our restaurants:\n\n" + "\n".join(
            f"{i + 1}. {r['name']} – {r['cuisine']} ({r['area']})"
            for i, r in enumerate(restaurants)
        ) + "\n\nWhich one would you like? (Name or number)"
        res = json_response("success", 8, msg, {"restaurants": restaurants})
        await self._publish(res)
        return res

    @function_tool()
    async def select_restaurant(self, context: RunContext, restaurant_input: str):
        """Select restaurant by name or number → loads & caches menu once"""
        userdata = _get_userdata(context)

        if not userdata.available_restaurants:
            return json_response("error", 9, "No restaurants loaded yet.")

        # Try number
        restaurant = None
        if restaurant_input.strip().isdigit():
            idx = int(restaurant_input.strip()) - 1
            if 0 <= idx < len(userdata.available_restaurants):
                restaurant = userdata.available_restaurants[idx]

        # Then name (fuzzy)
        if not restaurant:
            restaurant = fuzzy_match(restaurant_input, userdata.available_restaurants, "name", 68)

        if not restaurant:
            return json_response("error", 9, f"Couldn't find \"{restaurant_input}\". Try again.")

        userdata.selected_restaurant = restaurant

        # Load menu ONCE and cache
        menu = supabase.table("menu_items") \
                   .select("*") \
                   .eq("restaurantID", restaurant["id"]) \
                   .execute().data or []

        userdata.menu_items = menu  # ← Cached!

        menu_text = "\n".join(
            f"{i + 1}. {item['name']} – {item['price']:.3f} KWD"
            for i, item in enumerate(menu)
        )

        msg = f"Menu for *{restaurant['name']}*:\n\n{menu_text}\n\nWhat would you like to order?"
        res = json_response(
            "success", 9,
            msg,
            {"restaurant": restaurant, "items": menu})
        await self._publish(res)
        return res

    @function_tool()
    async def add_to_cart(
            self,
            context: RunContext,
            item_input: str,
            quantity: int = 1
    ):
        """Add item using cached menu → zero DB calls"""
        userdata = _get_userdata(context)

        if not userdata.selected_restaurant or not userdata.menu_items:
            return json_response("error", 10, "No restaurant or menu selected.")

        menu = userdata.menu_items  # ← From cache
        item = None

        # Try number
        num_match = re.search(r'\b(\d+)\b', item_input)
        if num_match:
            idx = int(num_match.group(1)) - 1
            if 0 <= idx < len(menu):
                item = menu[idx]

        # Try name
        if not item:
            item = fuzzy_match(item_input, menu, "name", 65)

        if not item:
            return json_response("error", 10, f"Can't find \"{item_input}\". Try again.")

        # Detect quantity from words
        qty_map = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
                   "ten": 10}
        for word in item_input.lower().split():
            if word in qty_map:
                quantity = qty_map[word]

        # Add to cart
        if not userdata.cart:
            userdata.cart = []

        existing = next((c for c in userdata.cart if c["item"]["id"] == item["id"]), None)
        if existing:
            existing["quantity"] += quantity
            existing["total"] = existing["item"]["price"] * existing["quantity"]
        else:
            userdata.cart.append({
                "id": str(uuid.uuid4()),
                "item": item,
                "quantity": quantity,
                "total": item["price"] * quantity
            })

        subtotal = sum(c["total"] for c in userdata.cart)
        total_items = sum(c["quantity"] for c in userdata.cart)
        res = json_response(
            "success", 10,
            f"Added {quantity} × {item['name']}\n"
            f"Cart: {total_items} item(s) → {subtotal:.3f} KWD",
            {"cartItems": userdata.cart, "subtotal": round(subtotal, 3)}
        )
        await self._publish(res)
        return res

    @function_tool()
    async def show_payment_summary_food(self, context: RunContext, payment_method: str | None = None):
        userdata = _get_userdata(context)

        if not userdata.cart:
            return json_response("error", 12, "Your cart is empty.")

        if payment_method:
            userdata.payment_method = payment_method.strip().title()

        if not userdata.payment_method:
            return json_response("partial", 12, "How would you like to pay — KNET, Visa, or Cash?")

        subtotal = sum(c["total"] for c in userdata.cart)
        delivery_fee = 0.750
        total = subtotal + delivery_fee

        summary = {
            "subtotal": round(subtotal, 3),
            "deliveryFee": delivery_fee,
            "total": round(total, 3),
            "currency": "KWD",
            "cart": userdata.cart,
            "paymentMethod": userdata.payment_method,
            "restaurant": userdata.selected_restaurant["name"]
        }
        userdata.food_payment_summary = summary

        msg = f"Subtotal: {subtotal:.3f} KWD + Delivery 0.750 KWD = Total {total:.3f} KWD\n\nConfirm your order?"
        res = json_response("success", 12, msg, {"paymentSummary": summary})
        await self._publish(res)
        return res

    @function_tool()
    async def confirm_food_order(self, context: RunContext, confirm: bool = True):
        if not confirm:
            return json_response("error", 13, "Order cancelled.")

        userdata = _get_userdata(context)
        summary = userdata.food_payment_summary

        order_data = {
            "booking_type": "food",
            "user_id": str(uuid.uuid4()),
            "item_id": userdata.selected_restaurant["id"],
            "booking_details": json.dumps({
                "restaurant": userdata.selected_restaurant,
                "cart": userdata.cart,
                "delivery_address": userdata.delivery_address or "Address not collected",
                "payment_summary": summary
            }),
            "payment_status": "Confirmed",
            "total_price": summary["total"],
            "currency": "KWD",
            "booking_date": datetime.now().isoformat()
        }

        result = supabase.table("bookings").insert(order_data).execute()
        if not result.data:
            return json_response("error", 13, "Failed to place order.")

        order_id = result.data[0].get("booking_id", "TEMP123")
        res = json_response(
            "success", 13,
            f"Order #{order_id} confirmed!\nEstimated delivery: 30–45 minutes",
            result.data[0]
        )
        userdata.food_order_confirmed = True
        await self._publish(res)
        await self.update_chat_ctx(ChatContext())
        return res
