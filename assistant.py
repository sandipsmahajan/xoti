from livekit.agents import Agent, RunContext
from livekit.agents.llm import function_tool
from mock_data import rides, food_menu, flights, hotels
import random
from dataclasses import dataclass

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

class Assistant(Agent):
    def __init__(self):
        super().__init__(
            instructions="You are a friendly assistant. You can help users order food, book rides, and book flights."
        )
        self.ride_bookings = []
        self.food_orders = []
        self.flight_bookings = []
        self.hotel_bookings = []

    def _get_userdata(self, context: RunContext) -> SessionData:
        if not hasattr(context, "_userdata"):
            context._userdata = SessionData()
        return context._userdata

    # ----------------- Ride Flow -----------------
    @function_tool
    async def search_rides(self, context: RunContext,
                           pickup: str = None,
                           destination: str = None,
                           ride_type: str = None):
        missing_fields = []
        if not pickup:
            missing_fields.append("pickup location")
        if not destination:
            missing_fields.append("destination")
        if not ride_type:
            missing_fields.append("ride type (Sedan, SUV, Auto)")
        if missing_fields:
            return f"Please provide the following information: {', '.join(missing_fields)}"

        available_rides = [r for r in rides if r["type"].lower() == ride_type.lower()]
        if not available_rides:
            return f"Sorry, no {ride_type} rides available."

        distance_km = random.randint(5, 20)
        userdata = self._get_userdata(context)
        userdata.pickup = pickup
        userdata.destination = destination
        userdata.ride_type = ride_type
        userdata.distance_km = distance_km

        options_text = "\n".join(
            [f"{r['id']} - {r['type']} (Base ₹{r['base_fare']}, ₹{r['rate_per_km']}/km)" for r in available_rides]
        )
        return (
            f"Rides available from {pickup} to {destination} (approx. {distance_km} km):\n"
            f"{options_text}\nPlease provide the ride ID to proceed with booking."
        )

    @function_tool
    async def book_ride(self, context: RunContext,
                        ride_id: str = None,
                        passenger_name: str = None,
                        phone_number: str = None):
        userdata = self._get_userdata(context)
        distance_km = userdata.distance_km or random.randint(5, 20)
        pickup = userdata.pickup
        destination = userdata.destination

        missing_fields = []
        if not ride_id:
            missing_fields.append("ride ID")
        if not passenger_name:
            missing_fields.append("passenger name")
        if not phone_number:
            missing_fields.append("phone number")
        if missing_fields:
            return f"Please provide the following information: {', '.join(missing_fields)}"

        ride = next((r for r in rides if r["id"] == ride_id), None)
        if not ride:
            return f"Ride ID {ride_id} not found. Please search again."

        total_fare = ride["base_fare"] + ride["rate_per_km"] * distance_km
        booking = {
            "ride_id": f"RD{len(self.ride_bookings) + 3001}",
            "type": ride["type"],
            "passenger": passenger_name,
            "phone": phone_number,
            "fare": total_fare,
            "pickup": pickup,
            "destination": destination,
            "distance_km": distance_km,
        }
        self.ride_bookings.append(booking)

        return (
            f"Ride booked successfully!\n"
            f"Type: {ride['type']}\nPassenger: {passenger_name}\nPhone: {phone_number}\n"
            f"From: {pickup} To: {destination}\nDistance: {distance_km} km\nEstimated fare: ₹{total_fare:.2f}"
        )

    # ----------------- Food Flow -----------------
    @function_tool
    async def search_food(self, context: RunContext,
                          cuisine: str = None):
        available_food = food_menu
        if cuisine:
            available_food = [f for f in food_menu if cuisine.lower() in f["name"].lower()]
        if not available_food:
            return f"Sorry, no food items found for '{cuisine}'."

        userdata = self._get_userdata(context)
        userdata.available_food = available_food
        items_text = "\n".join([f"{f['id']} - {f['name']} ({f['restaurant']}) ₹{f['price']}" for f in available_food])
        return f"Available food items:\n{items_text}\nPlease provide the food ID to place your order."

    @function_tool
    async def order_food(self, context: RunContext,
                         food_id: str = None,
                         customer_name: str = None,
                         phone_number: str = None):
        missing_fields = []
        if not food_id:
            missing_fields.append("food ID")
        if not customer_name:
            missing_fields.append("customer name")
        if not phone_number:
            missing_fields.append("phone number")
        if missing_fields:
            return f"Please provide the following information: {', '.join(missing_fields)}"

        food_item = next((f for f in food_menu if f["id"] == food_id), None)
        if not food_item:
            return f"Food item ID {food_id} not found. Please search again."

        order = {
            "order_id": f"FO{len(self.food_orders)+1001}",
            "customer": customer_name,
            "phone": phone_number,
            "item": food_item["name"],
            "restaurant": food_item["restaurant"],
            "price": food_item["price"],
        }
        self.food_orders.append(order)

        return (
            f"Food order confirmed!\n"
            f"Item: {food_item['name']} from {food_item['restaurant']}\n"
            f"Customer: {customer_name}\nPhone: {phone_number}\nTotal: ₹{food_item['price']}"
        )

    # ----------------- Flight Flow -----------------
    @function_tool
    async def search_flights(self, context: RunContext,
                             from_city: str = None,
                             to_city: str = None):
        missing_fields = []
        if not from_city:
            missing_fields.append("departure city")
        if not to_city:
            missing_fields.append("destination city")
        if missing_fields:
            return f"Please provide the following information: {', '.join(missing_fields)}"

        available_flights = [f for f in flights
                             if f.get("from", "").lower() == from_city.lower() and f.get("to", "").lower() == to_city.lower()]
        if not available_flights:
            return f"Sorry, no flights found from {from_city} to {to_city}."

        userdata = self._get_userdata(context)
        userdata.to_city = to_city
        userdata.available_flights = available_flights

        flights_text = "\n".join([f"{f['id']} - {f['airline']} ₹{f['price']}" for f in available_flights])
        return f"Available flights:\n{flights_text}\nPlease provide the flight ID to book."

    @function_tool
    async def book_flight(self, context: RunContext,
                          flight_id: str = None,
                          passenger_name: str = None,
                          phone_number: str = None):
        missing_fields = []
        if not flight_id:
            missing_fields.append("flight ID")
        if not passenger_name:
            missing_fields.append("passenger name")
        if not phone_number:
            missing_fields.append("phone number")
        if missing_fields:
            return f"Please provide the following information: {', '.join(missing_fields)}"

        flight = next((f for f in flights if f["id"] == flight_id), None)
        if not flight:
            return f"Flight ID {flight_id} not found. Please search again."

        booking = {
            "booking_id": f"FLB{len(self.flight_bookings)+1001}",
            "passenger": passenger_name,
            "phone": phone_number,
            "airline": flight["airline"],
            "from_city": flight["from"],
            "to_city": flight["to"],
            "price": flight["price"],
        }
        self.flight_bookings.append(booking)

        return (
            f"Flight booked successfully!\n"
            f"Airline: {flight['airline']}\nPassenger: {passenger_name}\nPhone: {phone_number}\n"
            f"From: {flight['from']} To: {flight['to']}\nPrice: ₹{flight['price']}"
        )

    @function_tool
    async def search_hotels(self, context: RunContext,
                            city: str = None,
                            check_in: str = None,
                            check_out: str = None):
        if not city:
            return "Please provide the city for hotel search."

        # For simplicity, assume hotels is a predefined list like flights/rides
        available_hotels = [h for h in hotels if h["city"].lower() == city.lower()]
        if not available_hotels:
            return f"Sorry, no hotels found in {city}."

        userdata = self._get_userdata(context)
        userdata.hotel_city = city
        userdata.available_hotels = available_hotels

        hotels_text = "\n".join(
            [f"{h['id']} - {h['name']} ({h['stars']}⭐) ₹{h['price_per_night']}/night" for h in available_hotels])
        return f"Available hotels in {city}:\n{hotels_text}\nPlease provide the hotel ID to book."

    @function_tool
    async def book_hotel(self, context: RunContext,
                         hotel_id: str = None,
                         guest_name: str = None,
                         phone_number: str = None,
                         rooms: int = 1):
        missing_fields = []
        if not hotel_id:
            missing_fields.append("hotel ID")
        if not guest_name:
            missing_fields.append("guest name")
        if not phone_number:
            missing_fields.append("phone number")
        if missing_fields:
            return f"Please provide the following information: {', '.join(missing_fields)}"

        hotel = next((h for h in hotels if h["id"] == hotel_id), None)
        if not hotel:
            return f"Hotel ID {hotel_id} not found. Please search again."

        booking = {
            "booking_id": f"HTB{len(self.hotel_bookings) + 1001}",
            "guest": guest_name,
            "phone": phone_number,
            "hotel": hotel["name"],
            "city": hotel["city"],
            "rooms": rooms,
            "price_per_night": hotel["price_per_night"],
            "total_price": hotel["price_per_night"] * rooms
        }
        self.hotel_bookings.append(booking)

        return (
            f"Hotel booked successfully!\n"
            f"Hotel: {hotel['name']} ({hotel['stars']}⭐)\n"
            f"Guest: {guest_name}\nPhone: {phone_number}\n"
            f"City: {hotel['city']}\nRooms: {rooms}\nTotal Price: ₹{booking['total_price']}"
        )
