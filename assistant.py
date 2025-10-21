from livekit.agents import Agent, RunContext
from livekit.agents.llm import function_tool
from dataclasses import dataclass
from mock_data import rides, food_menu, flights, hotels
import random


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
    """Unified JSON structure for all responses"""
    return {
        "status": status,  # "success" | "error"
        "action": action,  # "ride_search", "ride_booking", etc.
        "message": message,
        "data": data,
    }


class Assistant(Agent):
    def __init__(self):
        super().__init__(
            instructions="You are a friendly assistant that returns JSON responses only. You can help users order food, book rides, flights, and hotels."
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
            missing = []
            if not pickup: missing.append("pickup")
            if not destination: missing.append("destination")
            if not ride_type: missing.append("ride_type")
            return json_response("error", "ride_search", f"Missing fields: {', '.join(missing)}")

        available_rides = [r for r in rides if r["type"].lower() == ride_type.lower()]
        if not available_rides:
            return json_response("error", "ride_search", f"No {ride_type} rides available")

        userdata = self._get_userdata(context)
        userdata.pickup, userdata.destination, userdata.ride_type = pickup, destination, ride_type
        userdata.distance_km = random.randint(5, 20)

        rides_list = [
            {
                "id": r["id"],
                "type": r["type"],
                "base_fare": r["base_fare"],
                "rate_per_km": r["rate_per_km"],
                "estimated_fare": r["base_fare"] + r["rate_per_km"] * userdata.distance_km,
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
    async def book_ride(self, context: RunContext, ride_id: str = None, passenger_name: str = None, phone_number: str = None):
        userdata = self._get_userdata(context)
        distance_km = userdata.distance_km or random.randint(5, 20)
        pickup, destination = userdata.pickup, userdata.destination

        if not ride_id or not passenger_name or not phone_number:
            missing = [f for f in ["ride_id", "passenger_name", "phone_number"] if locals()[f] is None]
            return json_response("error", "ride_booking", f"Missing fields: {', '.join(missing)}")

        ride = next((r for r in rides if r["id"] == ride_id), None)
        if not ride:
            return json_response("error", "ride_booking", f"Ride ID {ride_id} not found")

        total_fare = ride["base_fare"] + ride["rate_per_km"] * distance_km
        booking = {
            "booking_id": f"RD{len(self.ride_bookings) + 3001}",
            "type": ride["type"],
            "pickup": pickup,
            "destination": destination,
            "distance_km": distance_km,
            "fare": total_fare,
            "passenger": passenger_name,
            "phone": phone_number,
        }
        self.ride_bookings.append(booking)

        return json_response("success", "ride_booking", "Ride booked successfully", booking)

    # ---------------------- FOOD FLOW ----------------------
    @function_tool
    async def search_food(self, context: RunContext, cuisine: str = None):
        available_food = food_menu if not cuisine else [f for f in food_menu if cuisine.lower() in f["name"].lower()]
        if not available_food:
            return json_response("error", "food_search", f"No items found for '{cuisine}'")

        userdata = self._get_userdata(context)
        userdata.available_food = available_food

        food_items = [
            {"id": f["id"], "name": f["name"], "restaurant": f["restaurant"], "price": f["price"]}
            for f in available_food
        ]

        return json_response("success", "food_search", f"{len(food_items)} food items found", {"items": food_items})

    @function_tool
    async def order_food(self, context: RunContext, food_id: str = None, customer_name: str = None, phone_number: str = None):
        if not food_id or not customer_name or not phone_number:
            missing = [f for f in ["food_id", "customer_name", "phone_number"] if locals()[f] is None]
            return json_response("error", "food_order", f"Missing fields: {', '.join(missing)}")

        food_item = next((f for f in food_menu if f["id"] == food_id), None)
        if not food_item:
            return json_response("error", "food_order", f"Food ID {food_id} not found")

        order = {
            "order_id": f"FO{len(self.food_orders) + 1001}",
            "customer": customer_name,
            "phone": phone_number,
            "item": food_item["name"],
            "restaurant": food_item["restaurant"],
            "price": food_item["price"],
        }
        self.food_orders.append(order)

        return json_response("success", "food_order", "Food order placed successfully", order)

    # ---------------------- FLIGHT FLOW ----------------------
    @function_tool
    async def search_flights(self, context: RunContext, from_city: str = None, to_city: str = None):
        if not from_city or not to_city:
            missing = [f for f in ["from_city", "to_city"] if locals()[f] is None]
            return json_response("error", "flight_search", f"Missing fields: {', '.join(missing)}")

        available_flights = [f for f in flights if f["from"].lower() == from_city.lower() and f["to"].lower() == to_city.lower()]
        if not available_flights:
            return json_response("error", "flight_search", f"No flights found from {from_city} to {to_city}")

        userdata = self._get_userdata(context)
        userdata.available_flights = available_flights
        userdata.to_city = to_city

        flight_list = [
            {"id": f["id"], "airline": f["airline"], "price": f["price"], "departure": f["from"], "arrival": f["to"]}
            for f in available_flights
        ]

        return json_response("success", "flight_search", f"{len(flight_list)} flights found", {"flights": flight_list})

    @function_tool
    async def book_flight(self, context: RunContext, flight_id: str = None, passenger_name: str = None, phone_number: str = None):
        if not flight_id or not passenger_name or not phone_number:
            missing = [f for f in ["flight_id", "passenger_name", "phone_number"] if locals()[f] is None]
            return json_response("error", "flight_booking", f"Missing fields: {', '.join(missing)}")

        flight = next((f for f in flights if f["id"] == flight_id), None)
        if not flight:
            return json_response("error", "flight_booking", f"Flight ID {flight_id} not found")

        booking = {
            "booking_id": f"FL{len(self.flight_bookings) + 1001}",
            "passenger": passenger_name,
            "phone": phone_number,
            "airline": flight["airline"],
            "from_city": flight["from"],
            "to_city": flight["to"],
            "price": flight["price"],
        }
        self.flight_bookings.append(booking)

        return json_response("success", "flight_booking", "Flight booked successfully", booking)

    # ---------------------- HOTEL FLOW ----------------------
    @function_tool
    async def search_hotels(self, context: RunContext, city: str = None, check_in: str = None, check_out: str = None):
        if not city:
            return json_response("error", "hotel_search", "Missing field: city")

        available_hotels = [h for h in hotels if h["city"].lower() == city.lower()]
        if not available_hotels:
            return json_response("error", "hotel_search", f"No hotels found in {city}")

        userdata = self._get_userdata(context)
        userdata.available_hotels = available_hotels
        userdata.hotel_city = city

        hotels_list = [
            {
                "id": h["id"],
                "name": h["name"],
                "stars": h["stars"],
                "city": h["city"],
                "price_per_night": h["price_per_night"],
            }
            for h in available_hotels
        ]

        return json_response("success", "hotel_search", f"{len(hotels_list)} hotels found in {city}", {"hotels": hotels_list})

    @function_tool
    async def book_hotel(self, context: RunContext, hotel_id: str = None, guest_name: str = None, phone_number: str = None, rooms: int = 1):
        if not hotel_id or not guest_name or not phone_number:
            missing = [f for f in ["hotel_id", "guest_name", "phone_number"] if locals()[f] is None]
            return json_response("error", "hotel_booking", f"Missing fields: {', '.join(missing)}")

        hotel = next((h for h in hotels if h["id"] == hotel_id), None)
        if not hotel:
            return json_response("error", "hotel_booking", f"Hotel ID {hotel_id} not found")

        booking = {
            "booking_id": f"HT{len(self.hotel_bookings) + 1001}",
            "guest": guest_name,
            "phone": phone_number,
            "hotel": hotel["name"],
            "city": hotel["city"],
            "rooms": rooms,
            "price_per_night": hotel["price_per_night"],
            "total_price": hotel["price_per_night"] * rooms,
        }
        self.hotel_bookings.append(booking)

        return json_response("success", "hotel_booking", "Hotel booked successfully", booking)
