from dotenv import load_dotenv
from livekit.agents import Agent, RunContext
from livekit.agents.llm import function_tool
from dataclasses import dataclass
from supabase import create_client, Client
import os
import random

load_dotenv(".env")

# Load environment variables
SUPABASE_URL = 'https://lhfdogoefrwtnhdtibsh.supabase.co' # os.getenv("SUPABASE_URL")
SUPABASE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxoZmRvZ29lZnJ3dG5oZHRpYnNoIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjA0NTIxNzgsImV4cCI6MjA3NjAyODE3OH0.mIpn-FbyvbobjxzF_Zb5nL2yPAa61Ke3Ed78LZC5pQ0' # os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

@dataclass
class SessionData:
    pickup: str | None = None
    destination: str | None = None
    ride_type: str | None = None
    distance_km: int | None = None
    available_food: list | None = None
    to_city: str | None = None
    available_flights: list | None = None
    hotel_city: str | None = None
    available_hotels: list | None = None

def json_response(status: str, action: str, message: str = None, data=None):
    return {
        "status": status,
        "action": action,
        "message": message,
        "data": data,
    }

class Assistant(Agent):
    def __init__(self):
        super().__init__(
            instructions="You are a JSON-only assistant that connects to Supabase to fetch live data for rides, food, flights, and hotels."
        )
        self.ride_bookings = []
        self.food_orders = []
        self.flight_bookings = []
        self.hotel_bookings = []

    def _get_userdata(self, context: RunContext) -> SessionData:
        if not hasattr(context, "_userdata"):
            context._userdata = SessionData()
        return context._userdata

    # ---------------------- RIDE FLOW ----------------------
    @function_tool
    async def search_rides(self, context: RunContext, pickup: str = None, destination: str = None, ride_type: str = None):
        if not pickup or not destination or not ride_type:
            missing = [f for f in ["pickup", "destination", "ride_type"] if locals()[f] is None]
            return json_response("error", "ride_search", f"Missing fields: {', '.join(missing)}")

        # Query Supabase
        response = supabase.table("rides").select("*").eq("type", ride_type).execute()
        available_rides = response.data

        if not available_rides:
            return json_response("error", "ride_search", f"No {ride_type} rides available")

        userdata = self._get_userdata(context)
        userdata.pickup, userdata.destination, userdata.ride_type = pickup, destination, ride_type
        userdata.distance_km = random.randint(5, 20)

        rides_list = [
            {
                "id": r["id"],
                "service": r["service"],
                "type": r["type"],
                "currency": r["currency"],
                "base_fare": float(r["base_fare"]),
                "per_km": float(r["per_km"]),
                "estimated_fare": float(r["base_fare"]) + float(r["per_km"]) * userdata.distance_km,
                "city": r["city"],
                "description": r["description"],
            }
            for r in available_rides
        ]

        return json_response(
            "success",
            "ride_search",
            f"Rides found from {pickup} to {destination}",
            {
                "pickup": pickup,
                "destination": destination,
                "distance_km": userdata.distance_km,
                "options": rides_list,
            },
        )

    @function_tool
    async def book_ride(self, context: RunContext, ride_id: int = None, passenger_name: str = None, phone_number: str = None):
        if not ride_id or not passenger_name or not phone_number:
            missing = [f for f in ["ride_id", "passenger_name", "phone_number"] if locals()[f] is None]
            return json_response("error", "ride_booking", f"Missing fields: {', '.join(missing)}")

        response = supabase.table("rides").select("*").eq("id", ride_id).single().execute()
        ride = response.data
        if not ride:
            return json_response("error", "ride_booking", f"Ride ID {ride_id} not found")

        userdata = self._get_userdata(context)
        distance_km = userdata.distance_km or random.randint(5, 20)
        total_fare = float(ride["base_fare"]) + float(ride["per_km"]) * distance_km

        booking = {
            "booking_id": f"RD{len(self.ride_bookings) + 3001}",
            "type": ride["type"],
            "pickup": userdata.pickup,
            "destination": userdata.destination,
            "distance_km": distance_km,
            "fare": total_fare,
            "currency": ride["currency"],
            "passenger": passenger_name,
            "phone": phone_number,
        }
        self.ride_bookings.append(booking)
        return json_response("success", "ride_booking", "Ride booked successfully", booking)

    # ---------------------- FOOD FLOW ----------------------
    @function_tool
    async def search_food(self, context: RunContext, cuisine: str = None):
        query = supabase.table("food_items").select("*")
        if cuisine:
            query = query.ilike("name", f"%{cuisine}%")
        response = query.execute()
        food_items = response.data

        if not food_items:
            return json_response("error", "food_search", f"No items found for '{cuisine}'")

        userdata = self._get_userdata(context)
        userdata.available_food = food_items

        return json_response("success", "food_search", f"{len(food_items)} food items found", {"items": food_items})

    @function_tool
    async def order_food(self, context: RunContext, food_id: int = None, customer_name: str = None, phone_number: str = None):
        if not food_id or not customer_name or not phone_number:
            missing = [f for f in ["food_id", "customer_name", "phone_number"] if locals()[f] is None]
            return json_response("error", "food_order", f"Missing fields: {', '.join(missing)}")

        response = supabase.table("food_items").select("*").eq("id", food_id).single().execute()
        food_item = response.data
        if not food_item:
            return json_response("error", "food_order", f"Food ID {food_id} not found")

        order = {
            "order_id": f"FO{len(self.food_orders) + 1001}",
            "customer": customer_name,
            "phone": phone_number,
            "item": food_item["name"],
            "price": float(food_item["price"]),
            "currency": food_item["currency"],
            "restaurant": food_item.get("country", "Unknown"),
            "image_url": food_item.get("image_url"),
        }
        self.food_orders.append(order)
        return json_response("success", "food_order", "Food order placed successfully", order)

    # ---------------------- FLIGHT FLOW ----------------------
    @function_tool
    async def search_flights(self, context: RunContext, from_city: str = None, to_city: str = None):
        if not from_city or not to_city:
            missing = [f for f in ["from_city", "to_city"] if locals()[f] is None]
            return json_response("error", "flight_search", f"Missing fields: {', '.join(missing)}")

        response = supabase.table("flights").select("*").eq("from_city", from_city).eq("to_city", to_city).execute()
        available_flights = response.data

        if not available_flights:
            return json_response("error", "flight_search", f"No flights found from {from_city} to {to_city}")

        userdata = self._get_userdata(context)
        userdata.available_flights = available_flights
        userdata.to_city = to_city

        return json_response(
            "success",
            "flight_search",
            f"{len(available_flights)} flights found",
            {"flights": available_flights},
        )

    @function_tool
    async def book_flight(self, context: RunContext, flight_id: int = None, passenger_name: str = None, phone_number: str = None):
        if not flight_id or not passenger_name or not phone_number:
            missing = [f for f in ["flight_id", "passenger_name", "phone_number"] if locals()[f] is None]
            return json_response("error", "flight_booking", f"Missing fields: {', '.join(missing)}")

        response = supabase.table("flights").select("*").eq("id", flight_id).single().execute()
        flight = response.data
        if not flight:
            return json_response("error", "flight_booking", f"Flight ID {flight_id} not found")

        booking = {
            "booking_id": f"FL{len(self.flight_bookings) + 1001}",
            "passenger": passenger_name,
            "phone": phone_number,
            "airline": flight["airline"],
            "from_city": flight["from_city"],
            "to_city": flight["to_city"],
            "price": float(flight["price"]),
            "currency": flight["currency"],
            "flight_date": flight["flight_date"],
            "departure_time": flight["departure_time"],
            "arrival_time": flight["arrival_time"],
        }
        self.flight_bookings.append(booking)
        return json_response("success", "flight_booking", "Flight booked successfully", booking)

    # ---------------------- HOTEL FLOW ----------------------
    @function_tool
    async def search_hotels(self, context: RunContext, city: str = None, check_in: str = None, check_out: str = None):
        if not city:
            return json_response("error", "hotel_search", "Missing field: city")

        response = supabase.table("hotels").select("*").eq("city", city).execute()
        available_hotels = response.data

        if not available_hotels:
            return json_response("error", "hotel_search", f"No hotels found in {city}")

        userdata = self._get_userdata(context)
        userdata.available_hotels = available_hotels
        userdata.hotel_city = city

        return json_response("success", "hotel_search", f"{len(available_hotels)} hotels found in {city}", {"hotels": available_hotels})

    @function_tool
    async def book_hotel(self, context: RunContext, hotel_id: int = None, guest_name: str = None, phone_number: str = None, rooms: int = 1):
        if not hotel_id or not guest_name or not phone_number:
            missing = [f for f in ["hotel_id", "guest_name", "phone_number"] if locals()[f] is None]
            return json_response("error", "hotel_booking", f"Missing fields: {', '.join(missing)}")

        response = supabase.table("hotels").select("*").eq("id", hotel_id).single().execute()
        hotel = response.data
        if not hotel:
            return json_response("error", "hotel_booking", f"Hotel ID {hotel_id} not found")

        booking = {
            "booking_id": f"HT{len(self.hotel_bookings) + 1001}",
            "guest": guest_name,
            "phone": phone_number,
            "hotel": hotel["name"],
            "city": hotel["city"],
            "rooms": rooms,
            "price_per_night": float(hotel["price_per_night"]),
            "currency": hotel["currency"],
            "total_price": float(hotel["price_per_night"]) * rooms,
        }
        self.hotel_bookings.append(booking)
        return json_response("success", "hotel_booking", "Hotel booked successfully", booking)
