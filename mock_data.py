# mock_data.py
# Mock datasets for food ordering, flight booking, and ride booking (GCC-focused).

food_menu = [
    # 🇦🇪 UAE
    {"id": "f001", "name": "Chicken Shawarma Plate", "price": 28, "restaurant": "Al Mallah", "country": "UAE"},
    {"id": "f002", "name": "Mandi Lamb", "price": 45, "restaurant": "Mandi House", "country": "UAE"},
    {"id": "f003", "name": "Falafel Wrap", "price": 18, "restaurant": "Operation Falafel", "country": "UAE"},
    {"id": "f004", "name": "Butter Chicken", "price": 32, "restaurant": "Gazebo", "country": "UAE"},
    {"id": "f005", "name": "Zaatar Manakeesh", "price": 15, "restaurant": "Zaatar w Zeit", "country": "UAE"},
    {"id": "f006", "name": "Mixed Grill Platter", "price": 58, "restaurant": "Al Safadi", "country": "UAE"},

    # 🇸🇦 Saudi Arabia
    {"id": "f101", "name": "Kabsa with Chicken", "price": 40, "restaurant": "Najd Village", "country": "Saudi Arabia"},
    {"id": "f102", "name": "Mutabbaq", "price": 12, "restaurant": "Al Baik Express", "country": "Saudi Arabia"},
    {"id": "f103", "name": "Arabic Mixed Grill", "price": 55, "restaurant": "Abd El Wahab", "country": "Saudi Arabia"},
    {"id": "f104", "name": "Fattoush Salad", "price": 18, "restaurant": "Al Khayal", "country": "Saudi Arabia"},
    {"id": "f105", "name": "Broasted Chicken Meal", "price": 25, "restaurant": "Al Baik", "country": "Saudi Arabia"},

    # 🇶🇦 Qatar
    {"id": "f201", "name": "Machboos", "price": 38, "restaurant": "Al Mourjan", "country": "Qatar"},
    {"id": "f202", "name": "Beef Sambousek", "price": 16, "restaurant": "Turkey Central", "country": "Qatar"},
    {"id": "f203", "name": "Karak Chai & Samosa", "price": 12, "restaurant": "Tea Time", "country": "Qatar"},
    {"id": "f204", "name": "Mixed Mezze Platter", "price": 45, "restaurant": "Layali", "country": "Qatar"},

    # 🇰🇼 Kuwait
    {"id": "f301", "name": "Chicken Majboos", "price": 35, "restaurant": "Mais Alghanim", "country": "Kuwait"},
    {"id": "f302", "name": "Grilled Hammour", "price": 48, "restaurant": "Freej Swaileh", "country": "Kuwait"},
    {"id": "f303", "name": "Kuwaiti Shrimp Curry", "price": 42, "restaurant": "Al Boom", "country": "Kuwait"},
    {"id": "f304", "name": "Falafel Platter", "price": 22, "restaurant": "Shay Al Shami", "country": "Kuwait"},

    # 🇧🇭 Bahrain
    {"id": "f401", "name": "Grilled Chicken Tikka", "price": 30, "restaurant": "Saffron by Jena", "country": "Bahrain"},
    {"id": "f402", "name": "Beef Biryani", "price": 32, "restaurant": "Biryani Express", "country": "Bahrain"},
    {"id": "f403", "name": "Fish Machboos", "price": 38, "restaurant": "Haji Gahwa", "country": "Bahrain"},
    {"id": "f404", "name": "Paneer Masala", "price": 26, "restaurant": "Jashan", "country": "Bahrain"},

    # 🇴🇲 Oman
    {"id": "f501", "name": "Omani Shuwa", "price": 48, "restaurant": "Bait Al Luban", "country": "Oman"},
    {"id": "f502", "name": "Grilled Kingfish", "price": 44, "restaurant": "The Beach House", "country": "Oman"},
    {"id": "f503", "name": "Omani Halwa Dessert", "price": 15, "restaurant": "Al Angham", "country": "Oman"},
    {"id": "f504", "name": "Mutton Biryani", "price": 36, "restaurant": "Woodlands", "country": "Oman"},
]


flights = [
    # UAE routes
    {"id": "FL101", "from": "Dubai", "to": "Riyadh", "price": 780, "airline": "Emirates"},
    {"id": "FL102", "from": "Abu Dhabi", "to": "Doha", "price": 620, "airline": "Etihad Airways"},
    {"id": "FL103", "from": "Dubai", "to": "Kuwait City", "price": 540, "airline": "FlyDubai"},
    {"id": "FL104", "from": "Dubai", "to": "Muscat", "price": 490, "airline": "Oman Air"},

    # Saudi Arabia routes
    {"id": "FL201", "from": "Riyadh", "to": "Jeddah", "price": 410, "airline": "Saudia"},
    {"id": "FL202", "from": "Dammam", "to": "Manama", "price": 360, "airline": "Gulf Air"},
    {"id": "FL203", "from": "Riyadh", "to": "Doha", "price": 500, "airline": "Qatar Airways"},

    # Qatar routes
    {"id": "FL301", "from": "Doha", "to": "Muscat", "price": 450, "airline": "Oman Air"},
    {"id": "FL302", "from": "Doha", "to": "Abu Dhabi", "price": 580, "airline": "Qatar Airways"},
    {"id": "FL303", "from": "Doha", "to": "Cairo", "price": 990, "airline": "EgyptAir"},

    # Kuwait routes
    {"id": "FL401", "from": "Kuwait City", "to": "Dubai", "price": 520, "airline": "Kuwait Airways"},
    {"id": "FL402", "from": "Kuwait City", "to": "Jeddah", "price": 650, "airline": "Saudia"},
    {"id": "FL403", "from": "Kuwait City", "to": "Doha", "price": 590, "airline": "Qatar Airways"},
]


rides = [
    # UAE
    {"id": "R001", "type": "Sedan", "base_fare": 12, "rate_per_km": 3.2, "currency": "AED", "country": "UAE"},
    {"id": "R002", "type": "SUV", "base_fare": 18, "rate_per_km": 4.0, "currency": "AED", "country": "UAE"},
    {"id": "R003", "type": "Luxury", "base_fare": 25, "rate_per_km": 5.5, "currency": "AED", "country": "UAE"},
    {"id": "R004", "type": "Bike", "base_fare": 6, "rate_per_km": 2.0, "currency": "AED", "country": "UAE"},

    # Saudi Arabia
    {"id": "R101", "type": "Sedan", "base_fare": 10, "rate_per_km": 2.8, "currency": "SAR", "country": "Saudi Arabia"},
    {"id": "R102", "type": "SUV", "base_fare": 16, "rate_per_km": 3.5, "currency": "SAR", "country": "Saudi Arabia"},
    {"id": "R103", "type": "Luxury", "base_fare": 22, "rate_per_km": 4.8, "currency": "SAR", "country": "Saudi Arabia"},
    {"id": "R104", "type": "Auto", "base_fare": 7, "rate_per_km": 1.5, "currency": "SAR", "country": "Saudi Arabia"},

    # Qatar
    {"id": "R201", "type": "Sedan", "base_fare": 11, "rate_per_km": 3.0, "currency": "QAR", "country": "Qatar"},
    {"id": "R202", "type": "SUV", "base_fare": 17, "rate_per_km": 3.8, "currency": "QAR", "country": "Qatar"},
    {"id": "R203", "type": "Luxury", "base_fare": 24, "rate_per_km": 5.2, "currency": "QAR", "country": "Qatar"},

    # Kuwait
    {"id": "R301", "type": "Sedan", "base_fare": 1.2, "rate_per_km": 0.4, "currency": "KWD", "country": "Kuwait"},
    {"id": "R302", "type": "SUV", "base_fare": 1.8, "rate_per_km": 0.55, "currency": "KWD", "country": "Kuwait"},
    {"id": "R303", "type": "Luxury", "base_fare": 2.5, "rate_per_km": 0.7, "currency": "KWD", "country": "Kuwait"},

    # Oman
    {"id": "R401", "type": "Sedan", "base_fare": 1.5, "rate_per_km": 0.35, "currency": "OMR", "country": "Oman"},
    {"id": "R402", "type": "SUV", "base_fare": 2.0, "rate_per_km": 0.45, "currency": "OMR", "country": "Oman"},
    {"id": "R403", "type": "Luxury", "base_fare": 2.8, "rate_per_km": 0.6, "currency": "OMR", "country": "Oman"},
]

hotels = [
    # 🇦🇪 UAE
    {"id": "H101", "name": "Grand Palace Dubai", "city": "Dubai", "stars": 5, "price_per_night": 1200},
    {"id": "H102", "name": "City Inn Dubai", "city": "Dubai", "stars": 3, "price_per_night": 400},
    {"id": "H103", "name": "Desert View Abu Dhabi", "city": "Abu Dhabi", "stars": 4, "price_per_night": 800},
    {"id": "H104", "name": "Marina Bay Hotel", "city": "Dubai", "stars": 4, "price_per_night": 650},
    {"id": "H105", "name": "Al Raha Beach Hotel", "city": "Abu Dhabi", "stars": 5, "price_per_night": 1500},

    # 🇸🇦 Saudi Arabia
    {"id": "H201", "name": "Riyadh Royal Hotel", "city": "Riyadh", "stars": 5, "price_per_night": 1000},
    {"id": "H202", "name": "Mecca Oasis", "city": "Mecca", "stars": 4, "price_per_night": 750},
    {"id": "H203", "name": "Medina Comfort Inn", "city": "Medina", "stars": 3, "price_per_night": 350},
    {"id": "H204", "name": "Jeddah Sea View Hotel", "city": "Jeddah", "stars": 5, "price_per_night": 1100},

    # 🇶🇦 Qatar
    {"id": "H301", "name": "Doha Grand Palace", "city": "Doha", "stars": 5, "price_per_night": 1300},
    {"id": "H302", "name": "West Bay Suites", "city": "Doha", "stars": 4, "price_per_night": 700},
    {"id": "H303", "name": "Corniche Comfort Inn", "city": "Doha", "stars": 3, "price_per_night": 400},

    # 🇰🇼 Kuwait
    {"id": "H401", "name": "Kuwait City Luxury Hotel", "city": "Kuwait City", "stars": 5, "price_per_night": 120},
    {"id": "H402", "name": "Gulf View Hotel", "city": "Kuwait City", "stars": 4, "price_per_night": 80},
    {"id": "H403", "name": "City Center Inn", "city": "Kuwait City", "stars": 3, "price_per_night": 50},

    # 🇧🇭 Bahrain
    {"id": "H501", "name": "Bahrain Bay Hotel", "city": "Manama", "stars": 5, "price_per_night": 140},
    {"id": "H502", "name": "Seef Comfort Inn", "city": "Manama", "stars": 3, "price_per_night": 60},
    {"id": "H503", "name": "Juffair Suites", "city": "Manama", "stars": 4, "price_per_night": 90},

    # 🇴🇲 Oman
    {"id": "H601", "name": "Muscat Grand Hotel", "city": "Muscat", "stars": 5, "price_per_night": 110},
    {"id": "H602", "name": "Corniche Inn", "city": "Muscat", "stars": 3, "price_per_night": 45},
    {"id": "H603", "name": "Sultan Qaboos Suites", "city": "Muscat", "stars": 4, "price_per_night": 80},
]
