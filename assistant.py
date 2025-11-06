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

    def __init__(self, participant=LocalParticipant):
        self.participant = participant
        super().__init__(
            instructions="""
                You are a JSON-only assistant for booking flights, hotels, rides, and food.

                1. ALWAYS use `collect_flight_info` to gather required fields one by one.
                2. When all fields are collected, call `search_flights`.
                3. After a successful search, **read the option list aloud** and ask the user for the **option number**.
                4. Use `select_flight_by_option` with that number – **never** ask for a raw DB id.
                5. Continue with `add_passenger_details` → `confirm_booking`.
                
                Required fields for a flight search:
                - from_city
                - to_city
                - departure_date
                - flight_class
                - adults
                - kids

                Use natural language to ask for missing info. 
                """
        )
        self.ride_bookings = []
        self.food_orders = []
        self.flight_bookings = []
        self.hotel_bookings = []

    async def _publish(self, payload: dict):
        await self.participant.publish_data(
            payload=json.dumps(payload).encode("utf-8"),
            reliable=True
        )
        print(payload)

    async def fetch_city_code(self, city_name: str, field: str):
        """
        Generic helper to fetch city code from Supabase flights table.
        field = 'from_city' or 'to_city'
        Returns tuple: (canonical_city_name, city_code)
        or None if not found.
        """
        if not city_name:
            return None

        city_name = city_name.strip().lower()

        # Query both columns, but prioritize whichever field was specified
        response = supabase.table("flights") \
            .select("from_city, from_city_code, to_city, to_city_code") \
            .or_(f"from_city.ilike.%{city_name}%,to_city.ilike.%{city_name}%") \
            .limit(1) \
            .execute()

        if not response.data or len(response.data) == 0:
            return None

        record = response.data[0]

        # If the field we expect matches, return that directly
        if field == "from_city":
            if record["from_city"].lower() == city_name:
                return record["from_city"], record["from_city_code"]
            elif record["to_city"].lower() == city_name:
                # fallback if user used a destination city as departure
                return record["to_city"], record["to_city_code"]

        elif field == "to_city":
            if record["to_city"].lower() == city_name:
                return record["to_city"], record["to_city_code"]
            elif record["from_city"].lower() == city_name:
                # fallback if user swapped direction
                return record["from_city"], record["from_city_code"]

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
            "from_city": "Where are you flying from?",
            "to_city": "What’s your destination?",
            "departure_date": "When do you plan to depart?",
            "flight_class": "Which class would you like to travel in — economy, premium economy, or business?",
            "adults": "How many adults are flying?",
            "kids": "How many kids are flying?",
            "trip_type": "Is this a one-way trip or a round trip?"
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
        res = json_response("success", 6, f"Booking confirmed with booking ID {booking_id}. Thank you!")
        await self._publish(res)
        return res
