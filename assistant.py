import json
import uuid
from typing import List, Dict, TypedDict, Annotated

import dateparser
from livekit.rtc.participant import LocalParticipant
from livekit.agents import Agent, RunContext
from livekit.agents.llm import function_tool
from dataclasses import dataclass
from supabase import create_client, Client
import os

# SUPABASE_URL = os.getenv("SUPABASE_URL")
# SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_KEY="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxoZmRvZ29lZnJ3dG5oZHRpYnNoIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjA0NTIxNzgsImV4cCI6MjA3NjAyODE3OH0.mIpn-FbyvbobjxzF_Zb5nL2yPAa61Ke3Ed78LZC5pQ0"
SUPABASE_URL="https://lhfdogoefrwtnhdtibsh.supabase.co"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

@dataclass
class SessionData:
    pickup: str | None = None
    destination: str | None = None
    ride_type: str | None = None
    distance_km: int | None = None
    available_food: list | None = None
    from_city: str | None = None
    to_city: str | None = None
    from_city_code: str | None = None
    to_city_code: str | None = None
    available_flights: list | None = None
    hotel_city: str | None = None
    available_hotels: list | None = None
    passengers: list | None = None
    selected_flight: dict | None = None
    flight_class: str | None = None
    trip_type: str | None = None
    departure_date: str | None = None
    return_date: str | None = None
    payment_confirmed: bool = False
    passenger_details: List[Dict] | None = None
    payment_summary: dict | None = None
    # ==== FOOD ORDERING ====
    selected_area: str | None = None
    selected_restaurant: dict | None = None
    available_restaurants: list | None = None
    cart: List[Dict] | None = None
    delivery_address: dict | None = None
    food_payment_summary: dict | None = None
    food_order_confirmed: bool = False

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


class Assistant(Agent):
    city_cache = None

    def __init__(self, participant=LocalParticipant):
        self.participant = participant
        super().__init__(
            instructions="""
                You are a JSON-only assistant that can book Flights and Food delivery.
                NEVER speak normal text. Always respond with valid JSON only.
        
                INTENT DETECTION (do this first):
                - Words like flight, fly, airport, ticket, travel, departure → start FLIGHT flow
                - Words like food, hungry, order, delivery, restaurant, burger, pizza, machboos → start FOOD flow
        
                ——————— FLIGHT FLOW (actions 1–6) ———————
                Required fields (collect one by one):
                1. from_city
                2. to_city
                3. departure_date
                4. flight_class (economy / premium / business)
                5. adults (minimum 1)
                6. kids (0 or more)
                7. trip_type (one-way or round-trip) → if round-trip, also ask return_date
        
                Exact sequence:
                1. ALWAYS start with collect_flight_info
                2. When all required fields collected → automatically call search_flights
                3. Show results → ask only for "option number"
                4. User says option X → call select_flight_by_option(X)
                5. Then add_passenger_details → show_payment_summary → confirm_booking
        
                ——————— FOOD FLOW (actions 7–13) ———————
                Required fields (collect strictly in this order):
        
                Phase 1 – Area
                • selected_area (Salmiya, Hawally, etc.)
        
                Phase 2 – Restaurant
                • User must pick by option number only → select_restaurant_by_option
        
                Phase 3 – Cart (can be multiple items)
                • User adds items by menu option number + quantity → add_to_cart
                • Allow adding many times until user says "done", "checkout", "deliver"
        
                Phase 4 – Delivery Address (collect one by one):
                    1. full_name
                    2. phone
                    3. flat / apartment number
                    4. building
                    5. street
                    6. area (pre-filled but confirm)
                    7. notes (optional)
        
                Phase 5 – Payment & Confirm
                • After address complete → automatically show_payment_summary_food
                • User confirms → confirm_food_order(confirm=true)
        
                FOOD FLOW SEQUENCE (never break):
                collect_food_info                → only ask "Which area for delivery?"
                search_restaurants               → auto-called when area known
                select_restaurant_by_option      → user picks by number
                add_to_cart                      → repeat as needed
                set_delivery_address             → start when user is ready to checkout
                show_payment_summary_food        → auto after address complete
                confirm_food_order               → only on final confirmation
        
                GENERAL RULES (both flows):
                • Keep questions ultra short: "From?", "To?", "Date?", "Which area?", "Full name?", "Phone?"
                • Never read full lists out loud — just publish JSON and let frontend display
                • Never ask for raw IDs — always use option numbers
                • If user switches flow (flight ↔ food), reset the previous one and start fresh
                • You are 100% JSON. No explanations, no apologies, no extra text ever. 
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

    @function_tool()
    async def collect_flight_info(
            self,
            context: RunContext,
            from_city: str = None,
            to_city: str | None = None,
            departure_date: str | None = None,
            flight_class: str | None = None,
            adults: int | None = None,
            kids: int | None = None,
            trip_type: str | None = None,
            return_date: str | None = None
    ):
        """
        Collect flight booking details.
        Never say 'No' or 'Null' for missing fields —
        just ask the next required question naturally.
        """
        userdata = _get_userdata(context)

        # --- progressively capture and publish after each field ---
        if from_city:
            userdata.from_city = from_city.strip()
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
            await self._publish(json_response(
                "partial", 1, "Got it! Flying from recorded.",
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
                }
            ))

        if to_city:
            userdata.to_city = to_city.strip()
            city_result = await self.fetch_city_code(userdata.to_city, field="to_city")

            if not city_result:
                res = json_response(
                    "partial", 1,
                    f"Couldn’t find any flights to '{userdata.to_city}'. Please confirm or spell it differently.",
                    {"missing_field": "to_city"}
                )
                return res

            canonical_name, city_code = city_result
            userdata.to_city = canonical_name
            userdata.to_city_code = city_code
            await self._publish(json_response(
                "partial", 1, "Destination noted.",
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
                }
            ))

        if departure_date:
            parsed_dep = dateparser.parse(departure_date)
            if not parsed_dep:
                return await self._publish(json_response(
                    "error", 1,
                    "Couldn't understand the departure date. Can you repeat it clearly?"
                ))
            userdata.departure_date = parsed_dep.strftime("%Y-%m-%d")
            await self._publish(json_response(
                "partial", 1, "Departure date locked in.",
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
                }
            ))

        if return_date:
            parsed_ret = dateparser.parse(return_date)
            if not parsed_ret:
                return await self._publish(json_response(
                    "error", 1,
                    "Couldn't understand the return date. Please say it clearly."
                ))
            userdata.return_date = parsed_ret.strftime("%Y-%m-%d")
            await self._publish(json_response(
                "partial", 1, "Return date added.",
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
                }
            ))

        if flight_class:
            userdata.flight_class = flight_class.lower().strip()
            await self._publish(json_response(
                "partial", 1, "Flight class selected.",
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
                }
            ))

        if adults is not None:
            userdata.passengers = userdata.passengers or []
            adult_entry = next((p for p in userdata.passengers if p["type"] == "adult"), None)
            if adult_entry:
                adult_entry["count"] = max(1, adults)
            else:
                userdata.passengers.append({"type": "adult", "count": max(1, adults)})
            await self._publish(json_response(
                "partial", 1, "Adult passengers updated.",
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
                }
            ))

        if kids is not None:
            userdata.passengers = userdata.passengers or []
            kid_entry = next((p for p in userdata.passengers if p["type"] == "kid"), None)
            if kid_entry:
                kid_entry["count"] = max(0, kids)
            else:
                userdata.passengers.append({"type": "kid", "count": max(0, kids)})
            await self._publish(json_response(
                "partial", 1, "Kids count recorded.",
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
                }
            ))

        if trip_type:
            userdata.trip_type = trip_type.lower()
            await self._publish(json_response(
                "partial", 1, "Trip type confirmed.",
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
                }
            ))

        required_fields = [
            "from_city", "to_city", "departure_date",
            "flight_class", "adults", "kids", "trip_type"
        ]
        field_prompts = {
            "from_city": "From?",
            "to_city": "To?",
            "departure_date": "Date? Do not ask for date format",
            "flight_class": "Class? (eco/premium/business)",
            "adults": "Adults?",
            "kids": "Kids?",
            "trip_type": "One-way or round?"
        }

        # --- dynamic check: round trip needs return_date ---
        if getattr(userdata, "trip_type", None) == "round trip" and not userdata.return_date:
            res = json_response(
                "partial",
                1,
                "What’s your return date?",
                {"missing_field": "return_date"}
            )
            return res

        # --- check all required fields one by one ---
        for field in required_fields:
            value = None
            print(f"Required Field Check: {field}")
            if field == "adults":
                value = next((p["count"] for p in userdata.passengers if p["type"] == "adult"), None)
                if value is None or value < 1:
                    next_question = field_prompts[field]
                    res = json_response("partial", 1, next_question, {"missing_field": field})
                    return res
                continue

            elif field == "kids":
                value = next((p["count"] for p in userdata.passengers if p["type"] == "kid"), None)
                # ⚡ If kids == 0, accept it as valid
                if value is None or value < 0:
                    next_question = field_prompts[field]
                    res = json_response("partial", 1, next_question, {"missing_field": field})
                    return res
                continue

            else:
                value = getattr(userdata, field, None)
                # For strings, check for missing/empty
                if value is None or (isinstance(value, str) and not value.strip()):
                    next_question = field_prompts[field]
                    res = json_response("partial", 1, next_question, {"missing_field": field})
                    return res

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
    async def search_flights(
            self,
            context: RunContext,
            from_city: str,
            to_city: str,
            departure_date: str,
            flight_class: str,
            adults: int = 1,
            kids: int = 0,
            trip_type: str = "one way",
            return_date: str | None = None
    ):
        """
        Doesn’t need to read flight details out loud.
        """
        missing_fields = []
        for field, val in {"from_city": from_city, "to_city": to_city, "departure_date": departure_date,
                           "flight_class": flight_class}.items():
            if not val:
                missing_fields.append(field)
        if missing_fields:
            return json_response("error", 1, f"Missing fields: {', '.join(missing_fields)}")
        # Parse natural language dates
        parsed_dep = dateparser.parse(departure_date)
        if not parsed_dep:
            return await self._publish({
                "status": "error",
                "action": 2,
                "message": "Could not understand the departure date. Please say the date clearly."
            })
        departure_date_str = parsed_dep.strftime("%Y-%m-%d")

        if return_date:
            parsed_ret = dateparser.parse(return_date)
            if not parsed_ret:
                return await self._publish({
                    "status": "error",
                    "action": 2,
                    "message": "Could not understand the return date. Please say the date clearly."
                })
            return_date_str = parsed_ret.strftime("%Y-%m-%d")
        else:
            return_date_str = None

        # Validate adults and kids counts
        if not isinstance(adults, int) or adults < 1:
            return await self._publish({
                "status": "error",
                "action": 2,
                "message": "Please specify the number of adult passengers as a positive number."
            })

        if not isinstance(kids, int) or kids < 0:
            kids = 0  # default 0 if invalid or unrecognized

        # Now proceed to query flights from your DB with from_city, to_city, departure_date_str, flight_class...
        response = supabase.table("flights").select("*").ilike("from_city", from_city).ilike("to_city", to_city).execute()
        available_flights = response.data or []

        for f in available_flights:
            f["departure_date"] = departure_date

        if not available_flights:
            return await self._publish({
                "status": "error",
                "action": 2,
                "message": f"No flights found from {from_city} to {to_city} on {departure_date_str}."
            })

        # Save session state for later steps if needed
        userdata = _get_userdata(context)
        userdata.available_flights = available_flights
        userdata.flight_class = flight_class
        userdata.trip_type = trip_type
        userdata.departure_date = departure_date_str
        userdata.return_date = return_date_str
        userdata.from_city = from_city
        userdata.to_city = to_city
        userdata.passengers = [{"type": "adult", "count": adults}, {"type": "kid", "count": kids}]

        # Publish success response with flights and passenger info
        res = json_response("success",
                            2,
                            f"Found {len(available_flights)} flights from {from_city} to {to_city} on {departure_date_str}.",
                            {
                                "from_city": from_city,
                                "to_city": to_city,
                                "departure_date": departure_date_str,
                                "return_date": return_date_str,
                                "available_flights": available_flights,
                                "passengers": userdata.passengers,
                                "trip_type": trip_type
                            })

        await self._publish(res)
        return res

    @function_tool()
    async def select_flight_by_option(
            self,
            context: RunContext,
            option: int  # 1-based index the user says
    ) -> dict:
        """
        Select a flight using the human-readable option number shown after a search.
        User says "option 3" → option=3 → selects flights[2]
        """
        if not option or not isinstance(option, int) or option < 1:
            return json_response("error", 3, "Please say a valid option number (e.g., 1, 2, 3).")

        print("Selected flight: {}".format(option))
        userdata = _get_userdata(context)
        print(userdata)
        if not userdata.available_flights:
            return json_response("error", 3, "No flight list available. Search again first.")

        # Map option → DB record
        try:
            flight_record: dict = userdata.available_flights[option - 1]
            print(flight_record)
        except IndexError:
            return json_response("error", 3,
                                 f"Option {option} does not exist. Choose from 1-{len(userdata.available_flights)}.")

        userdata.selected_flight = flight_record

        total_passengers = sum(p["count"] for p in userdata.passengers)
        msg = (
            f"Selected: {flight_record['airline']} "
            f"{flight_record['departure_time']} → {flight_record['arrival_time']} "
            f"on {flight_record['flight_date']}. "
            f"Please give passenger details for {total_passengers} traveler(s)."
        )
        print(msg)
        res = json_response(
            "success",
            3,
            msg,
            {"selected_flight": flight_record, "passenger_count": total_passengers}
        )
        await self._publish(res)
        return res

    @function_tool()
    async def add_passenger_details(
            self,
            context: RunContext,
            passenger_details: Annotated[
                List[PassengerDetail],
                {
                    "description": "Array of passenger details",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "Full name"},
                            "age": {"type": "integer", "description": "Age in years"},
                            "type": {"type": "string", "enum": ["adult", "kid"], "description": "Passenger type"},
                            "mobile": {"type": "string", "description": "Mobile number"},
                            "passport_number": {"type": ["string", "null"], "description": "Optional passport"}
                        },
                        "required": ["name", "age", "type", "mobile"],
                        "additionalProperties": False
                    }
                }
            ]
    ):
        if not passenger_details or not isinstance(passenger_details, list):
            return json_response("error", 4,
                                 "Missing or invalid passenger_details. Provide a list of passenger info.")

        userdata = _get_userdata(context)
        expected_count = sum(p["count"] for p in userdata.passengers)

        if len(passenger_details) != expected_count:
            return json_response("error", 4,
                                 f"Passenger details count {len(passenger_details)} does not match expected {expected_count}.")

        userdata.passenger_details = passenger_details

        # Don’t calculate or publish payment summary here
        message = f"Passenger details received for {expected_count} travelers. Would you like to review the payment summary?"
        res = json_response("success", 4, message, {"passenger_details": passenger_details})
        await self._publish(res)
        return res

    @function_tool()
    async def show_payment_summary(self, context: RunContext):
        """
        Display the payment summary before confirming the booking.
        Called after passenger details are added.
        """
        userdata = _get_userdata(context)

        if not userdata.selected_flight or not userdata.passenger_details:
            return json_response("error", 5,
                                 "Missing flight or passenger details. Please complete those first.")

        expected_count = sum(p["count"] for p in userdata.passengers)
        total_price = float(userdata.selected_flight["price"]) * expected_count
        payment_summary = {
            "flight": userdata.selected_flight,
            "passengers": userdata.passenger_details,
            "class": userdata.flight_class,
            "trip_type": userdata.trip_type,
            "total_price": total_price,
            "currency": userdata.selected_flight["currency"]
        }

        userdata.payment_summary = payment_summary

        message = (
            f"Here’s your payment summary: {expected_count} passenger(s), "
            f"{userdata.flight_class.capitalize()} class, total {total_price} {userdata.selected_flight['currency']}. "
            f"Would you like to confirm this booking?"
        )

        res = json_response("success", 5, message, {"payment_summary": payment_summary})
        await self._publish(res)
        return res

    @function_tool()
    async def confirm_booking(self, context: RunContext, confirm: bool = False):
        if not confirm:
            return json_response("error", 6, "Booking not confirmed. Process aborted.")

        userdata = _get_userdata(context)
        print(self.participant)
        booking_data = {
            "booking_type": "flight",
            "user_id": str(uuid.uuid4()),
            "item_id": userdata.selected_flight["id"],
            "booking_details": json.dumps({
                "flight": userdata.selected_flight,
                "passengers": userdata.passenger_details,
                "class": userdata.flight_class,
                "trip_type": userdata.trip_type,
                "departure_date": userdata.departure_date,
                "return_date": userdata.return_date,
            }),
            "payment_status": "confirmed",
            "total_price": userdata.payment_summary["total_price"],
            "currency": userdata.selected_flight["currency"],
            "booking_date": "now()",
            "start_date": userdata.departure_date,
            "end_date": userdata.return_date if userdata.trip_type == "round-trip" else None,
        }

        result = supabase.table("bookings").insert(booking_data).execute()
        print(result)
        if not result.data:
            return json_response("error", 6, f"Failed to save booking.")

        booking_id = result.data[0]["booking_id"] if result.data else "N/A"
        userdata.payment_confirmed = True
        res = json_response("success", 6, f"Booking confirmed with booking ID {booking_id}. Thank you!", result.data[0])
        await self._publish(res)
        return res

    # ===================== FOOD ORDERING FLOW =====================

    @function_tool()
    async def collect_food_info(
        self,
        context: RunContext,
        area: str | None = None
    ):
        """Step 1: Ask for delivery area first"""
        userdata = _get_userdata(context)

        if area:
            userdata.selected_area = area.strip().title()
            await self._publish(json_response(
                "partial", 7,
                f"Got it! Looking for restaurants in {userdata.selected_area}.",
                {"selected_area": userdata.selected_area}
            ))

        if not userdata.selected_area:
            return json_response("partial", 7, "Which area do you want delivery to? (e.g., Salmiya, Hawally, Kuwait City)")

        # All required collected → proceed automatically
        return json_response("success", 7, "", {"selected_area": userdata.selected_area})

    @function_tool()
    async def search_restaurants(self, context: RunContext, area: str):
        """Step 2: Show available restaurants in the area"""
        userdata = _get_userdata(context)

        response = supabase.table("restaurants")\
            .select("*")\
            .ilike("area", area.strip())\
            .execute()

        restaurants = response.data or []

        if not restaurants:
            return json_response("error", 8, f"Sorry, no restaurants deliver to {area} right now.")

        userdata.available_restaurants = restaurants
        userdata.cart = []  # reset cart

        res = json_response(
            "success", 8,
            f"Found {len(restaurants)} restaurants in {area}. Which one would you like?",
            {"available_restaurants": restaurants}
        )
        await self._publish(res)
        return res

    @function_tool()
    async def select_restaurant_by_option(self, context: RunContext, option: int):
        """User says "option 2" → pick that restaurant and show menu"""
        userdata = _get_userdata(context)
        if not userdata.available_restaurants or option < 1 or option > len(userdata.available_restaurants):
            return json_response("error", 9, "Invalid restaurant option.")

        restaurant = userdata.available_restaurants[option - 1]
        userdata.selected_restaurant = restaurant

        # Load menu
        menu_resp = supabase.table("menu_items")\
            .select("*")\
            .eq("restaurant_id", restaurant["id"])\
            .execute()

        menu = menu_resp.data or []

        res = json_response(
            "success", 9,
            f"Menu for {restaurant['name']}. What would you like to order?",
            {
                "selected_restaurant": restaurant,
                "menu_items": menu
            }
        )
        await self._publish(res)
        return res

    @function_tool()
    async def add_to_cart(
        self,
        context: RunContext,
        item_option: int,
        quantity: int = 1
    ):
        """Add item by option number shown in menu"""
        userdata = _get_userdata(context)
        if not userdata.selected_restaurant:
            return json_response("error", 10, "No restaurant selected yet.")

        menu_resp = supabase.table("menu_items")\
            .select("*")\
            .eq("restaurant_id", userdata.selected_restaurant["id"])\
            .execute()
        menu = menu_resp.data

        if item_option < 1 or item_option > len(menu):
            return json_response("error", 10, "Invalid menu item number.")

        item = menu[item_option - 1]
        cart_item = {"menu_item": item, "quantity": quantity}

        if not userdata.cart:
            userdata.cart = []
        # Replace if same item exists
        existing = next((c for c in userdata.cart if c["menu_item"]["id"] == item["id"]), None)
        if existing:
            existing["quantity"] += quantity
        else:
            userdata.cart.append(cart_item)

        subtotal = sum(c["menu_item"]["price"] * c["quantity"] for c in userdata.cart)

        res = json_response(
            "success", 10,
            f"Added {quantity}x {item['name']}. Cart total: {subtotal:.3f} KWD",
            {"cart": userdata.cart, "subtotal": round(subtotal, 3)}
        )
        await self._publish(res)
        return res

    @function_tool()
    async def set_delivery_address(
        self,
        context: RunContext,
        full_name: str | None = None,
        phone: str | None = None,
        flat: str | None = None,
        floor: str | None = None,
        building: str | None = None,
        street: str | None = None,
        area: str | None = None,
        notes: str | None = None
    ):
        userdata = _get_userdata(context)
        address = userdata.delivery_address or {}

        updated = False
        if full_name: address["full_name"] = full_name; updated = True
        if phone: address["phone"] = phone; updated = True
        if flat: address["flat"] = flat; updated = True
        if floor: address["floor"] = floor; updated = True
        if building: address["building"] = building; updated = True
        if street: address["street"] = street; updated = True
        if area: address["area"] = area; updated = True
        if notes is not None: address["notes"] = notes; updated = True

        userdata.delivery_address = address

        required = ["full_name", "phone", "flat", "building", "street", "area"]
        missing = [f for f in required if not address.get(f)]

        if missing:
            prompts = {
                "full_name": "Your full name?",
                "phone": "Phone number?",
                "flat": "Flat/Apartment number?",
                "building": "Building name/number?",
                "street": "Street name?",
                "area": "Area (we already have it, just confirming)?",
            }
            next_q = prompts[missing[0]]
            return json_response("partial", 11, next_q, {"missing_field": missing[0]})

        await self._publish(json_response(
            "success", 11,
            "Delivery address saved.",
            {"delivery_address": address}
        ))
        return json_response("success", 11, "", {"delivery_address": address})

    @function_tool()
    async def show_payment_summary_food(self, context: RunContext):
        userdata = _get_userdata(context)
        if not userdata.cart or len(userdata.cart) == 0:
            return json_response("error", 12, "Your cart is empty.")

        subtotal = sum(c["menu_item"]["price"] * c["quantity"] for c in userdata.cart)
        delivery_fee = 0.750  # fixed
        total = subtotal + delivery_fee

        summary = {
            "subtotal": round(subtotal, 3),
            "delivery_fee": delivery_fee,
            "total": round(total, 3),
            "currency": "KWD",
            "cart": userdata.cart,
            "restaurant": userdata.selected_restaurant["name"]
        }
        userdata.food_payment_summary = summary

        msg = f"Subtotal: {subtotal:.3f} KWD + Delivery 0.750 KWD = Total {total:.3f} KWD. Confirm order?"
        res = json_response("success", 12, msg, {"payment_summary": summary})
        await self._publish(res)
        return res

    @function_tool()
    async def confirm_food_order(self, context: RunContext, confirm: bool = False):
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
                "delivery_address": userdata.delivery_address,
                "payment_summary": summary
            }),
            "payment_status": "confirmed",
            "total_price": summary["total"],
            "currency": "KWD",
            "booking_date": "now()"
        }

        result = supabase.table("bookings").insert(order_data).execute()
        if not result.data:
            return json_response("error", 13, "Failed to place order.")

        order_id = result.data[0].get("booking_id", "N/A")
        estimated = "30-45 minutes"

        res = json_response(
            "success", 13,
            f"Order #{order_id} confirmed! Estimated delivery: {estimated}",
            {"order_id": order_id, "estimated_delivery": estimated}
        )
        await self._publish(res)
        userdata.food_order_confirmed = True
        return res
