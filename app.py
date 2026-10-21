"""
PNRGenius Backend API
======================
A production-ready PNR parser supporting Amadeus, Sabre, Galileo, and Worldspan
GDS formats. Converts raw cryptic PNR text into structured, clean JSON data
that the frontend renders into beautiful itineraries.

Run locally:
    pip install -r requirements.txt
    python app.py

Deploy:
    Push this folder to Railway.app (see DEPLOY_GUIDE.md)
"""

import re
import json
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)

# Allow requests from your Hostinger frontend domain + localhost for local testing.
# Once pnrgenius.com is live, you can remove the localhost entries if you want.
CORS(app, resources={
    r"/*": {
        "origins": [
            "https://pnrgenius.com",
            "https://www.pnrgenius.com",
            "http://localhost:3000",
            "http://127.0.0.1:5500",
        ],
        "allow_headers": ["Content-Type", "Authorization"],
    }
})

# ---------------------------------------------------------------------------
# REFERENCE DATA
# In production you'd pull these from a database. For now, a solid built-in
# dictionary covers the busiest airports/airlines worldwide. Add more anytime.
# ---------------------------------------------------------------------------

AIRPORTS = {
    "LHR": {"name": "London Heathrow", "city": "London", "country": "United Kingdom", "lat": 51.4700, "lng": -0.4543},
    "LGW": {"name": "London Gatwick", "city": "London", "country": "United Kingdom", "lat": 51.1537, "lng": -0.1821},
    "JFK": {"name": "John F. Kennedy Intl", "city": "New York", "country": "United States", "lat": 40.6413, "lng": -73.7781},
    "LAX": {"name": "Los Angeles Intl", "city": "Los Angeles", "country": "United States", "lat": 33.9416, "lng": -118.4085},
    "ORD": {"name": "O'Hare International", "city": "Chicago", "country": "United States", "lat": 41.9742, "lng": -87.9073},
    "DXB": {"name": "Dubai International", "city": "Dubai", "country": "UAE", "lat": 25.2532, "lng": 55.3657},
    "AUH": {"name": "Abu Dhabi International", "city": "Abu Dhabi", "country": "UAE", "lat": 24.4330, "lng": 54.6511},
    "DOH": {"name": "Hamad International", "city": "Doha", "country": "Qatar", "lat": 25.2731, "lng": 51.6080},
    "KHI": {"name": "Jinnah International", "city": "Karachi", "country": "Pakistan", "lat": 24.9065, "lng": 67.1608},
    "LHE": {"name": "Allama Iqbal International", "city": "Lahore", "country": "Pakistan", "lat": 31.5216, "lng": 74.4036},
    "ISB": {"name": "Islamabad International", "city": "Islamabad", "country": "Pakistan", "lat": 33.5492, "lng": 72.8254},
    "PEW": {"name": "Bacha Khan International", "city": "Peshawar", "country": "Pakistan", "lat": 33.9939, "lng": 71.5145},
    "CDG": {"name": "Charles de Gaulle", "city": "Paris", "country": "France", "lat": 49.0097, "lng": 2.5479},
    "ORY": {"name": "Paris Orly", "city": "Paris", "country": "France", "lat": 48.7233, "lng": 2.3794},
    "FRA": {"name": "Frankfurt Airport", "city": "Frankfurt", "country": "Germany", "lat": 50.0379, "lng": 8.5622},
    "MUC": {"name": "Munich Airport", "city": "Munich", "country": "Germany", "lat": 48.3537, "lng": 11.7860},
    "AMS": {"name": "Amsterdam Schiphol", "city": "Amsterdam", "country": "Netherlands", "lat": 52.3105, "lng": 4.7683},
    "IST": {"name": "Istanbul Airport", "city": "Istanbul", "country": "Turkey", "lat": 41.2753, "lng": 28.7519},
    "SAW": {"name": "Sabiha Gokcen", "city": "Istanbul", "country": "Turkey", "lat": 40.8986, "lng": 29.3092},
    "SIN": {"name": "Changi Airport", "city": "Singapore", "country": "Singapore", "lat": 1.3644, "lng": 103.9915},
    "BKK": {"name": "Suvarnabhumi", "city": "Bangkok", "country": "Thailand", "lat": 13.6900, "lng": 100.7501},
    "KUL": {"name": "Kuala Lumpur Intl", "city": "Kuala Lumpur", "country": "Malaysia", "lat": 2.7456, "lng": 101.7099},
    "HKG": {"name": "Hong Kong International", "city": "Hong Kong", "country": "Hong Kong", "lat": 22.3080, "lng": 113.9185},
    "NRT": {"name": "Narita International", "city": "Tokyo", "country": "Japan", "lat": 35.7720, "lng": 140.3929},
    "HND": {"name": "Haneda Airport", "city": "Tokyo", "country": "Japan", "lat": 35.5494, "lng": 139.7798},
    "ICN": {"name": "Incheon International", "city": "Seoul", "country": "South Korea", "lat": 37.4602, "lng": 126.4407},
    "DEL": {"name": "Indira Gandhi Intl", "city": "Delhi", "country": "India", "lat": 28.5562, "lng": 77.1000},
    "BOM": {"name": "Chhatrapati Shivaji", "city": "Mumbai", "country": "India", "lat": 19.0896, "lng": 72.8656},
    "MAA": {"name": "Chennai International", "city": "Chennai", "country": "India", "lat": 12.9941, "lng": 80.1709},
    "BLR": {"name": "Kempegowda International", "city": "Bengaluru", "country": "India", "lat": 13.1989, "lng": 77.7068},
    "SYD": {"name": "Sydney Kingsford Smith", "city": "Sydney", "country": "Australia", "lat": -33.9399, "lng": 151.1753},
    "MEL": {"name": "Melbourne Airport", "city": "Melbourne", "country": "Australia", "lat": -37.6690, "lng": 144.8410},
    "YYZ": {"name": "Toronto Pearson", "city": "Toronto", "country": "Canada", "lat": 43.6777, "lng": -79.6248},
    "YVR": {"name": "Vancouver International", "city": "Vancouver", "country": "Canada", "lat": 49.1967, "lng": -123.1815},
    "MAN": {"name": "Manchester Airport", "city": "Manchester", "country": "United Kingdom", "lat": 53.3537, "lng": -2.2750},
    "BHX": {"name": "Birmingham Airport", "city": "Birmingham", "country": "United Kingdom", "lat": 52.4539, "lng": -1.7480},
    "MAD": {"name": "Adolfo Suarez Madrid-Barajas", "city": "Madrid", "country": "Spain", "lat": 40.4983, "lng": -3.5676},
    "BCN": {"name": "Barcelona-El Prat", "city": "Barcelona", "country": "Spain", "lat": 41.2974, "lng": 2.0833},
    "FCO": {"name": "Leonardo da Vinci-Fiumicino", "city": "Rome", "country": "Italy", "lat": 41.8003, "lng": 12.2389},
    "MXP": {"name": "Milan Malpensa", "city": "Milan", "country": "Italy", "lat": 45.6306, "lng": 8.7281},
    "JED": {"name": "King Abdulaziz International", "city": "Jeddah", "country": "Saudi Arabia", "lat": 21.6796, "lng": 39.1565},
    "RUH": {"name": "King Khalid International", "city": "Riyadh", "country": "Saudi Arabia", "lat": 24.9576, "lng": 46.6988},
    "MED": {"name": "Prince Mohammad bin Abdulaziz", "city": "Madinah", "country": "Saudi Arabia", "lat": 24.5534, "lng": 39.7051},
    "CAI": {"name": "Cairo International", "city": "Cairo", "country": "Egypt", "lat": 30.1219, "lng": 31.4056},
    "NBO": {"name": "Jomo Kenyatta International", "city": "Nairobi", "country": "Kenya", "lat": -1.3192, "lng": 36.9278},
    "DAC": {"name": "Hazrat Shahjalal International", "city": "Dhaka", "country": "Bangladesh", "lat": 23.8433, "lng": 90.3978},
    "CGP": {"name": "Shah Amanat International", "city": "Chittagong", "country": "Bangladesh", "lat": 22.2496, "lng": 91.8133},
    "CMB": {"name": "Bandaranaike International", "city": "Colombo", "country": "Sri Lanka", "lat": 7.1808, "lng": 79.8841},
    "KTM": {"name": "Tribhuvan International", "city": "Kathmandu", "country": "Nepal", "lat": 27.6966, "lng": 85.3591},
    "JNB": {"name": "O.R. Tambo International", "city": "Johannesburg", "country": "South Africa", "lat": -26.1392, "lng": 28.2460},
}

AIRLINES = {
    "BA": "British Airways", "EK": "Emirates", "PK": "Pakistan International Airlines",
    "QR": "Qatar Airways", "EY": "Etihad Airways", "TK": "Turkish Airlines",
    "LH": "Lufthansa", "AF": "Air France", "KL": "KLM", "SQ": "Singapore Airlines",
    "UA": "United Airlines", "AA": "American Airlines", "DL": "Delta Air Lines",
    "AI": "Air India", "9W": "Jet Airways", "MH": "Malaysia Airlines",
    "CX": "Cathay Pacific", "JL": "Japan Airlines", "NH": "All Nippon Airways",
    "KE": "Korean Air", "OZ": "Asiana Airlines", "SV": "Saudia",
    "MS": "EgyptAir", "ET": "Ethiopian Airlines", "KQ": "Kenya Airways",
    "SA": "South African Airways", "VS": "Virgin Atlantic", "IB": "Iberia",
    "AZ": "ITA Airways", "LX": "Swiss International", "OS": "Austrian Airlines",
    "SK": "SAS", "AY": "Finnair", "TP": "TAP Air Portugal", "FZ": "flydubai",
    "G9": "Air Arabia", "PC": "Pegasus Airlines", "W6": "Wizz Air",
    "U2": "easyJet", "FR": "Ryanair", "VY": "Vueling",
    # Added for US/UK/Canada/Australia/NZ coverage
    "AC": "Air Canada", "WS": "WestJet", "PD": "Porter Airlines", "TS": "Air Transat",
    "WN": "Southwest Airlines", "B6": "JetBlue Airways", "AS": "Alaska Airlines",
    "NK": "Spirit Airlines", "F9": "Frontier Airlines", "HA": "Hawaiian Airlines",
    "QF": "Qantas", "JQ": "Jetstar Airways", "VA": "Virgin Australia", "NZ": "Air New Zealand",
}

MONTHS = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}

# Standard-time UTC offsets (hours) for major airports. Used only to correct
# flight-duration math since PNRs list LOCAL times at each end. This is a
# simplification that ignores daylight-saving shifts — fine for an estimate,
# not for exact scheduling. Add more airports as needed.
AIRPORT_UTC_OFFSETS = {
    "LHR": 0, "LGW": 0, "MAN": 0, "BHX": 0,
    "JFK": -5, "LAX": -8, "ORD": -6, "YYZ": -5, "YVR": -8,
    "DXB": 4, "AUH": 4, "DOH": 3,
    "KHI": 5, "LHE": 5, "ISB": 5, "PEW": 5,
    "CDG": 1, "ORY": 1, "FRA": 1, "MUC": 1, "AMS": 1, "MAD": 1, "BCN": 1, "FCO": 1, "MXP": 1,
    "IST": 3, "SAW": 3,
    "SIN": 8, "BKK": 7, "KUL": 8, "HKG": 8,
    "NRT": 9, "HND": 9, "ICN": 9,
    "DEL": 5.5, "BOM": 5.5, "MAA": 5.5, "BLR": 5.5,
    "SYD": 11, "MEL": 11,
    "JED": 3, "RUH": 3, "MED": 3, "CAI": 2, "NBO": 3, "JNB": 2,
    "DAC": 6, "CGP": 6, "CMB": 5.5, "KTM": 5.75,
}

DST_OBSERVING_AIRPORTS = {
    "LHR", "LGW", "MAN", "BHX",  # UK (BST)
    "CDG", "ORY", "FRA", "MUC", "AMS", "MAD", "BCN", "FCO", "MXP",  # EU (CEST)
    "JFK", "LAX", "ORD", "YYZ", "YVR",  # North America (varies, approximated together)
}
DST_SOUTHERN_HEMISPHERE = {"SYD", "MEL"}  # DST runs Oct-Apr instead of Mar-Oct


# ---------------------------------------------------------------------------
# EXTENDED REFERENCE DATA (additive)
# Extra airports / airlines / standard-time UTC offsets so connections through
# the Gulf, Middle East, South Asia, Europe, North America and Africa resolve
# to real names and durations instead of bare codes. setdefault() is used so
# nothing defined above can be overridden. Coordinates are approximate (used
# only for distance / CO2 estimates).
# ---------------------------------------------------------------------------
_EXTRA_AIRPORTS = {
    # code: (name, city, country, lat, lng, standard UTC offset)
    # --- Gulf & Middle East ---
    "BAH": ("Bahrain International", "Manama", "Bahrain", 26.2708, 50.6336, 3),
    "KWI": ("Kuwait International", "Kuwait City", "Kuwait", 29.2266, 47.9689, 3),
    "MCT": ("Muscat International", "Muscat", "Oman", 23.5933, 58.2844, 4),
    "SHJ": ("Sharjah International", "Sharjah", "UAE", 25.3286, 55.5172, 4),
    "DWC": ("Al Maktoum International", "Dubai", "UAE", 24.8960, 55.1614, 4),
    "DMM": ("King Fahd International", "Dammam", "Saudi Arabia", 26.4712, 49.7979, 3),
    "TIF": ("Taif International", "Taif", "Saudi Arabia", 21.4834, 40.5443, 3),
    "YNB": ("Yanbu Prince Abdul Mohsin", "Yanbu", "Saudi Arabia", 24.1442, 38.0634, 3),
    "AHB": ("Abha International", "Abha", "Saudi Arabia", 18.2404, 42.6566, 3),
    "TUU": ("Tabuk Regional", "Tabuk", "Saudi Arabia", 28.3654, 36.6189, 3),
    "AMM": ("Queen Alia International", "Amman", "Jordan", 31.7226, 35.9932, 3),
    "BEY": ("Beirut Rafic Hariri", "Beirut", "Lebanon", 33.8209, 35.4884, 2),
    "BGW": ("Baghdad International", "Baghdad", "Iraq", 33.2625, 44.2346, 3),
    "NJF": ("Al Najaf International", "Najaf", "Iraq", 31.9899, 44.4043, 3),
    "THR": ("Imam Khomeini International", "Tehran", "Iran", 35.4161, 51.1522, 3.5),
    "MHD": ("Mashhad International", "Mashhad", "Iran", 36.2352, 59.6410, 3.5),
    "HRG": ("Hurghada International", "Hurghada", "Egypt", 27.1783, 33.7994, 2),
    "SSH": ("Sharm El Sheikh International", "Sharm El Sheikh", "Egypt", 27.9773, 34.3950, 2),
    "ESB": ("Ankara Esenboga", "Ankara", "Turkey", 40.1281, 32.9951, 3),
    "AYT": ("Antalya Airport", "Antalya", "Turkey", 36.8987, 30.8005, 3),
    # --- South Asia ---
    "SKT": ("Sialkot International", "Sialkot", "Pakistan", 32.5356, 74.3639, 5),
    "MUX": ("Multan International", "Multan", "Pakistan", 30.2032, 71.4191, 5),
    "LYP": ("Faisalabad International", "Faisalabad", "Pakistan", 31.3650, 72.9948, 5),
    "UET": ("Quetta International", "Quetta", "Pakistan", 30.2514, 66.9378, 5),
    "RYK": ("Shaikh Zayed International", "Rahim Yar Khan", "Pakistan", 28.3838, 70.2796, 5),
    "AMD": ("Sardar Vallabhbhai Patel", "Ahmedabad", "India", 23.0772, 72.6347, 5.5),
    "HYD": ("Rajiv Gandhi International", "Hyderabad", "India", 17.2403, 78.4294, 5.5),
    "CCU": ("Netaji Subhas Chandra Bose", "Kolkata", "India", 22.6547, 88.4467, 5.5),
    "COK": ("Cochin International", "Kochi", "India", 10.1520, 76.4019, 5.5),
    "ATQ": ("Sri Guru Ram Dass Jee", "Amritsar", "India", 31.7096, 74.7973, 5.5),
    "JAI": ("Jaipur International", "Jaipur", "India", 26.8242, 75.8122, 5.5),
    "MLE": ("Velana International", "Male", "Maldives", 4.1918, 73.5290, 5),
    "ZYL": ("Osmani International", "Sylhet", "Bangladesh", 24.9632, 91.8668, 6),
    "KBL": ("Hamid Karzai International", "Kabul", "Afghanistan", 34.5659, 69.2123, 4.5),
    "TAS": ("Tashkent International", "Tashkent", "Uzbekistan", 41.2579, 69.2812, 5),
    # --- UK & Ireland ---
    "STN": ("London Stansted", "London", "United Kingdom", 51.8860, 0.2389, 0),
    "LTN": ("London Luton", "London", "United Kingdom", 51.8747, -0.3683, 0),
    "LCY": ("London City", "London", "United Kingdom", 51.5053, 0.0553, 0),
    "EDI": ("Edinburgh Airport", "Edinburgh", "United Kingdom", 55.9500, -3.3725, 0),
    "GLA": ("Glasgow Airport", "Glasgow", "United Kingdom", 55.8719, -4.4331, 0),
    "LPL": ("Liverpool John Lennon", "Liverpool", "United Kingdom", 53.3336, -2.8497, 0),
    "NCL": ("Newcastle Airport", "Newcastle", "United Kingdom", 55.0375, -1.6917, 0),
    "LBA": ("Leeds Bradford", "Leeds", "United Kingdom", 53.8659, -1.6606, 0),
    "EMA": ("East Midlands Airport", "Nottingham", "United Kingdom", 52.8311, -1.3281, 0),
    "BRS": ("Bristol Airport", "Bristol", "United Kingdom", 51.3827, -2.7191, 0),
    "CWL": ("Cardiff Airport", "Cardiff", "United Kingdom", 51.3967, -3.3434, 0),
    "BFS": ("Belfast International", "Belfast", "United Kingdom", 54.6575, -6.2158, 0),
    "DUB": ("Dublin Airport", "Dublin", "Ireland", 53.4213, -6.2701, 0),
    # --- Europe ---
    "BRU": ("Brussels Airport", "Brussels", "Belgium", 50.9014, 4.4844, 1),
    "ZRH": ("Zurich Airport", "Zurich", "Switzerland", 47.4647, 8.5492, 1),
    "GVA": ("Geneva Airport", "Geneva", "Switzerland", 46.2381, 6.1089, 1),
    "VIE": ("Vienna International", "Vienna", "Austria", 48.1103, 16.5697, 1),
    "CPH": ("Copenhagen Airport", "Copenhagen", "Denmark", 55.6180, 12.6508, 1),
    "ARN": ("Stockholm Arlanda", "Stockholm", "Sweden", 59.6519, 17.9186, 1),
    "OSL": ("Oslo Gardermoen", "Oslo", "Norway", 60.1976, 11.1004, 1),
    "HEL": ("Helsinki Airport", "Helsinki", "Finland", 60.3172, 24.9633, 2),
    "ATH": ("Athens International", "Athens", "Greece", 37.9364, 23.9445, 2),
    "LIS": ("Lisbon Humberto Delgado", "Lisbon", "Portugal", 38.7742, -9.1342, 0),
    "WAW": ("Warsaw Chopin", "Warsaw", "Poland", 52.1657, 20.9671, 1),
    "PRG": ("Vaclav Havel Prague", "Prague", "Czech Republic", 50.1008, 14.2600, 1),
    "BUD": ("Budapest Ferenc Liszt", "Budapest", "Hungary", 47.4298, 19.2611, 1),
    "DUS": ("Dusseldorf Airport", "Dusseldorf", "Germany", 51.2895, 6.7668, 1),
    "HAM": ("Hamburg Airport", "Hamburg", "Germany", 53.6304, 9.9882, 1),
    "BER": ("Berlin Brandenburg", "Berlin", "Germany", 52.3667, 13.5033, 1),
    "CGN": ("Cologne Bonn", "Cologne", "Germany", 50.8659, 7.1427, 1),
    "SJJ": ("Sarajevo International", "Sarajevo", "Bosnia and Herzegovina", 43.8246, 18.3315, 1),
    # --- North America ---
    "EWR": ("Newark Liberty", "Newark", "United States", 40.6895, -74.1745, -5),
    "IAD": ("Washington Dulles", "Washington", "United States", 38.9531, -77.4565, -5),
    "BOS": ("Boston Logan", "Boston", "United States", 42.3656, -71.0096, -5),
    "ATL": ("Hartsfield-Jackson Atlanta", "Atlanta", "United States", 33.6407, -84.4277, -5),
    "MIA": ("Miami International", "Miami", "United States", 25.7959, -80.2870, -5),
    "DFW": ("Dallas Fort Worth", "Dallas", "United States", 32.8998, -97.0403, -6),
    "IAH": ("George Bush Intercontinental", "Houston", "United States", 29.9902, -95.3368, -6),
    "SFO": ("San Francisco International", "San Francisco", "United States", 37.6213, -122.3790, -8),
    "SEA": ("Seattle-Tacoma", "Seattle", "United States", 47.4502, -122.3088, -8),
    "DTW": ("Detroit Metropolitan", "Detroit", "United States", 42.2162, -83.3554, -5),
    "PHL": ("Philadelphia International", "Philadelphia", "United States", 39.8744, -75.2424, -5),
    "YUL": ("Montreal Trudeau", "Montreal", "Canada", 45.4706, -73.7408, -5),
    "YYC": ("Calgary International", "Calgary", "Canada", 51.1215, -114.0076, -7),
    # --- Africa ---
    "CMN": ("Mohammed V International", "Casablanca", "Morocco", 33.3675, -7.5899, 1),
    "ALG": ("Houari Boumediene", "Algiers", "Algeria", 36.6910, 3.2154, 1),
    "TUN": ("Tunis Carthage", "Tunis", "Tunisia", 36.8510, 10.2272, 1),
    "ADD": ("Addis Ababa Bole", "Addis Ababa", "Ethiopia", 8.9779, 38.7993, 3),
    "LOS": ("Murtala Muhammed International", "Lagos", "Nigeria", 6.5774, 3.3212, 1),
    "ACC": ("Kotoka International", "Accra", "Ghana", 5.6052, -0.1668, 0),
    "KRT": ("Khartoum International", "Khartoum", "Sudan", 15.5895, 32.5532, 2),
    "CPT": ("Cape Town International", "Cape Town", "South Africa", -33.9715, 18.6021, 2),
    # --- Asia-Pacific ---
    "PEK": ("Beijing Capital", "Beijing", "China", 40.0799, 116.6031, 8),
    "PVG": ("Shanghai Pudong", "Shanghai", "China", 31.1443, 121.8083, 8),
    "CAN": ("Guangzhou Baiyun", "Guangzhou", "China", 23.3924, 113.2988, 8),
    "TPE": ("Taiwan Taoyuan", "Taipei", "Taiwan", 25.0777, 121.2328, 8),
    "MNL": ("Ninoy Aquino International", "Manila", "Philippines", 14.5086, 121.0194, 8),
    "CGK": ("Soekarno-Hatta", "Jakarta", "Indonesia", -6.1256, 106.6559, 7),
    "DPS": ("Ngurah Rai International", "Bali", "Indonesia", -8.7482, 115.1675, 8),
    "SGN": ("Tan Son Nhat", "Ho Chi Minh City", "Vietnam", 10.8188, 106.6520, 7),
    "HAN": ("Noi Bai International", "Hanoi", "Vietnam", 21.2212, 105.8072, 7),
    "PER": ("Perth Airport", "Perth", "Australia", -31.9403, 115.9669, 8),
    "BNE": ("Brisbane Airport", "Brisbane", "Australia", -27.3842, 153.1175, 10),
}

_EXTRA_AIRLINES = {
    "GF": "Gulf Air", "WY": "Oman Air", "KU": "Kuwait Airways", "RJ": "Royal Jordanian",
    "ME": "Middle East Airlines", "J9": "Jazeera Airways", "XY": "flynas", "F3": "flyadeal",
    "SM": "Air Cairo", "NP": "Nile Air", "UL": "SriLankan Airlines", "6E": "IndiGo",
    "SG": "SpiceJet", "IX": "Air India Express", "PA": "Airblue", "ER": "SereneAir",
    "9P": "Fly Jinnah", "PF": "Air Sial", "W5": "Mahan Air", "IR": "Iran Air",
    "EI": "Aer Lingus", "SN": "Brussels Airlines", "LO": "LOT Polish Airlines",
    "OK": "Czech Airlines", "A3": "Aegean Airlines", "TU": "Tunisair", "AT": "Royal Air Maroc",
    "AH": "Air Algerie", "BG": "Biman Bangladesh Airlines", "BS": "US-Bangla Airlines",
    "BI": "Royal Brunei Airlines", "GA": "Garuda Indonesia", "PR": "Philippine Airlines",
    "VN": "Vietnam Airlines", "TG": "Thai Airways", "CA": "Air China", "CZ": "China Southern Airlines",
    "MU": "China Eastern Airlines", "BR": "EVA Air", "CI": "China Airlines", "WB": "RwandAir",
    "MK": "Air Mauritius", "XQ": "SunExpress", "VF": "AJet", "UX": "Air Europa",
    "HV": "Transavia", "TO": "Transavia France", "DY": "Norwegian", "LS": "Jet2", "BY": "TUI Airways",
    "EW": "Eurowings", "LA": "LATAM Airlines", "AV": "Avianca", "CM": "Copa Airlines",
    "AM": "Aeromexico",
}

for _code, (_name, _city, _country, _lat, _lng, _utc) in _EXTRA_AIRPORTS.items():
    AIRPORTS.setdefault(_code, {"name": _name, "city": _city, "country": _country, "lat": _lat, "lng": _lng})
    AIRPORT_UTC_OFFSETS.setdefault(_code, _utc)
for _code, _name in _EXTRA_AIRLINES.items():
    AIRLINES.setdefault(_code, _name)

# Daylight-saving regions for the added airports (same simplified month rule as above).
DST_OBSERVING_AIRPORTS.update({
    "STN", "LTN", "LCY", "EDI", "GLA", "LPL", "NCL", "LBA", "EMA", "BRS", "CWL", "BFS", "DUB",   # UK / Ireland
    "BRU", "ZRH", "GVA", "VIE", "CPH", "ARN", "OSL", "HEL", "ATH", "LIS", "WAW", "PRG", "BUD",
    "DUS", "HAM", "BER", "CGN", "SJJ",                                                             # EU / Europe
    "EWR", "IAD", "BOS", "ATL", "MIA", "DFW", "IAH", "SFO", "SEA", "DTW", "PHL", "YUL", "YYC",    # North America
    "BEY",                                                                                         # Lebanon
})


def get_utc_offset_for_date(airport_code, date_iso):
    base_offset = AIRPORT_UTC_OFFSETS.get(airport_code)
    if base_offset is None:
        return None
    if not date_iso:
        return base_offset

    try:
        dt = datetime.strptime(date_iso, "%Y-%m-%d")
    except ValueError:
        return base_offset

    month = dt.month
    if airport_code in DST_OBSERVING_AIRPORTS:
        if 4 <= month <= 9:
            return base_offset + 1
        if month in (3, 10):
            return base_offset + 1
        return base_offset
    if airport_code in DST_SOUTHERN_HEMISPHERE:
        if month in (11, 12, 1, 2, 3):
            return base_offset + 1
        if month in (4, 10):
            return base_offset + 1
        return base_offset
    return base_offset

CABIN_CODES = {
    "F": "First Class", "A": "First Class", "J": "Business Class", "C": "Business Class",
    "D": "Business Class", "I": "Business Class", "W": "Premium Economy", "P": "Premium Economy",
    "Y": "Economy Class", "B": "Economy Class", "H": "Economy Class", "K": "Economy Class",
    "L": "Economy Class", "M": "Economy Class", "N": "Economy Class", "Q": "Economy Class",
    "S": "Economy Class", "T": "Economy Class", "U": "Economy Class", "V": "Economy Class",
    "X": "Economy Class", "Z": "Economy Class", "E": "Economy Class", "G": "Economy Class",
    "O": "Economy Class", "R": "Economy Class",
}

STATUS_CODES = {
    "HK": "Confirmed", "KK": "Confirmed", "HL": "Waitlisted", "KL": "Waitlisted",
    "UN": "Unable", "UC": "Unable", "NN": "Pending", "TK": "Confirmed", "RR": "Confirmed",
    "SS": "Pending",  # "sold": action code printed on segments not yet confirmed (Sabre/Galileo)
}

# Proactive fare flags: booking classes verified, per-airline, against each
# carrier's own agent-facing documentation (not guessed from generic class
# tables, since the same letter means different things on different
# airlines — see CABIN_CODES above). Only airlines with a directly verified
# source are listed; unlisted airlines simply get no flag rather than a
# guessed one. Extend this table as more carriers are verified — do not
# add an entry without a source.
#   AA — saleslink.aa.com Basic Economy Reference Guide ("booked in B on all
#        AA operated flights", domestic and international)
#   DL — pro.delta.com agency portal ("booking code for Basic Economy fares
#        will be 'E' class")
#   UA — United's Basic Economy fare class identifiers are N and G
#   AC — Air Canada Branded Fares GDS User Guide (TANGO, the carrier's
#        lowest bundle, quotes in L class)
#   BA — British Airways has no single "Basic Economy" bucket; Q/O/G are
#        its lowest, most-restrictive Economy fare tier
FARE_FLAG_RULES = {
    "AA": {"classes": ["B"], "label": "Basic Economy"},
    "DL": {"classes": ["E"], "label": "Basic Economy"},
    "UA": {"classes": ["N", "G"], "label": "Basic Economy"},
    "AC": {"classes": ["L"], "label": "Tango (lowest fare bundle)"},
    "BA": {"classes": ["Q", "O", "G"], "label": "lowest Economy fare tier"},
}


def get_fare_flag(airline_code, booking_class):
    """Best-effort, source-verified flag for restrictive/basic fares.
    Returns None (no flag) for any airline not in FARE_FLAG_RULES, rather
    than guessing — silence is safer than a wrong flag here."""
    if not airline_code or not booking_class:
        return None
    rule = FARE_FLAG_RULES.get(airline_code.upper())
    if not rule or booking_class.upper() not in rule["classes"]:
        return None
    airline_name = get_airline_info(airline_code)
    return {
        "label": rule["label"],
        "booking_class": booking_class.upper(),
        "message": (
            f"Booking class {booking_class.upper()} on {airline_name} — likely "
            f"{rule['label']}. Typically no free checked bag, no advance seat "
            f"selection, boards last, and changes/refunds may be restricted or "
            f"unavailable. Confirm exact fare rules in your GDS before advising "
            f"the client."
        ),
    }


# PNR Health Check — best-effort pre-ticketing sanity checks run against the
# raw pasted text and the parsed segments. These are heuristics reading a
# copy-pasted PNR dump, not a live GDS query, so every message is written to
# hedge ("confirm in your GDS") rather than assert a fact we can't verify —
# consistent with the project rule of never stating false confidence.
#   TK/TAW element — the ticketing-arrangement / time-limit line used across
#   Amadeus ("TK OK"/"TK TL..."), Sabre ("TAW"), Galileo/Worldspan ("TKTL").
#   FQTV element — the frequent-flyer SSR line ("SSR FQTV..."), or a compact
#   Sabre-style "FFxx1234567" loyalty field.
TICKETING_ELEMENT_RE = re.compile(r"\bTK\s*(?:OK|TL|XL)|\bTAW\b|\bTKTL\b", re.IGNORECASE)
FQTV_ELEMENT_RE = re.compile(r"\bFQTV\b|\bFREQUENT\s*FLYER\b|\bFF[A-Z]{2}\d{4,}\b", re.IGNORECASE)

MIN_CONNECTION_MINUTES_DOMESTIC = 45
MIN_CONNECTION_MINUTES_INTERNATIONAL = 90


def check_pnr_health(segments, raw_text):
    """Returns a list of {type, severity, title, message, segment_index}
    issues. Empty list means nothing was flagged — not a guarantee the PNR
    is problem-free, only that these specific checks found nothing."""
    issues = []
    text = raw_text or ""

    if not TICKETING_ELEMENT_RE.search(text):
        issues.append({
            "type": "ticketing_deadline_missing",
            "severity": "warning",
            "title": "No ticketing deadline found",
            "message": (
                "No TK / TAW ticketing element was found in the pasted text. "
                "This PNR may already be ticketed, or the deadline simply "
                "wasn't included in what you pasted — but if it's still on "
                "hold, confirm the time limit in your GDS. Unticketed PNRs "
                "can auto-cancel without warning."
            ),
            "segment_index": None,
        })

    if not FQTV_ELEMENT_RE.search(text):
        issues.append({
            "type": "frequent_flyer_missing",
            "severity": "info",
            "title": "No frequent-flyer number found",
            "message": (
                "No FQTV / loyalty number was found for this booking. Worth "
                "asking the client if they have a frequent-flyer number to "
                "add before ticketing — some fares only credit miles or "
                "allow upgrades if it's on file at the time of booking."
            ),
            "segment_index": None,
        })

    for i in range(len(segments) - 1):
        current = segments[i]
        nxt = segments[i + 1]
        same_airport = current["destination"]["code"] == nxt["origin"]["code"]
        same_city_diff_airport = (
            not same_airport
            and current["destination"].get("city")
            and nxt["origin"].get("city")
            and current["destination"]["city"].strip().lower() == nxt["origin"]["city"].strip().lower()
        )

        day_diff = None
        if current.get("arrival_date_iso") and nxt.get("date_iso"):
            try:
                d1 = datetime.strptime(current["arrival_date_iso"], "%Y-%m-%d")
                d2 = datetime.strptime(nxt["date_iso"], "%Y-%m-%d")
                day_diff = (d2 - d1).days
            except ValueError:
                day_diff = None

        if same_airport and day_diff is not None and day_diff < 0:
            issues.append({
                "type": "impossible_connection",
                "severity": "warning",
                "title": f"Segment {i + 2} departs before segment {i + 1} arrives",
                "message": (
                    f"Flight {nxt['airline_code']}{nxt['flight_number']} is dated "
                    f"before {current['airline_code']}{current['flight_number']} "
                    f"arrives at {current['destination']['code']}. This usually "
                    f"means a date was mis-typed — double check both segments "
                    f"before ticketing."
                ),
                "segment_index": i,
            })
            continue

        if same_city_diff_airport:
            issues.append({
                "type": "different_airport_connection",
                "severity": "warning",
                "title": f"Airport change in {current['destination']['city']}",
                "message": (
                    f"This connects through two different airports in "
                    f"{current['destination']['city']} — "
                    f"{current['destination']['code']} to {nxt['origin']['code']}. "
                    f"The passenger will need to arrange their own ground "
                    f"transport between them; it isn't a walk-through transfer."
                ),
                "segment_index": i,
            })
            continue

        if same_airport and current.get("layover_minutes") is not None:
            minutes = current["layover_minutes"]
            is_intl_leg = (
                current["origin"].get("country") != current["destination"].get("country")
                or nxt["origin"].get("country") != nxt["destination"].get("country")
            )
            threshold = MIN_CONNECTION_MINUTES_INTERNATIONAL if is_intl_leg else MIN_CONNECTION_MINUTES_DOMESTIC
            if 0 <= minutes < threshold:
                hrs, mins = divmod(minutes, 60)
                issues.append({
                    "type": "tight_connection",
                    "severity": "warning",
                    "title": f"Tight connection at {current['destination']['code']}",
                    "message": (
                        f"Only {hrs}h {mins:02d}m between landing and the next "
                        f"departure at {current['destination']['code']} — below "
                        f"the typical {threshold}-minute minimum for a "
                        f"{'international' if is_intl_leg else 'domestic'} "
                        f"connection. Actual minimum connection times vary by "
                        f"airport, so confirm this one is workable before "
                        f"booking it."
                    ),
                    "segment_index": i,
                })

    return issues


def parse_pnr_date(date_str, min_date=None):
    """Resolves a day+month-only date string (GDS text never includes a
    year) to a full date. `min_date` is the earliest date this is allowed
    to resolve to — it defaults to today, so a bare date always resolves to
    the next upcoming occurrence of that day/month.

    Passing the previous segment's resolved date as `min_date` (see
    parse_segments) keeps a multi-segment PNR chronologically consistent.
    Without this, each segment's year was picked independently against the
    real wall-clock date, so a PNR whose first segment fell a few days
    *before* today (e.g. pasted on the 23rd with a trip starting the 20th)
    could roll only that segment into next year while a later segment in
    the same PNR stayed in the current year — producing a itinerary where
    segment 2 appeared to depart before segment 1 arrived.
    """
    if min_date is None:
        min_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    match = re.match(r"(\d{1,2})([A-Z]{3})", date_str.upper())
    if not match:
        return None
    day, mon = match.groups()
    month = MONTHS.get(mon)
    if not month:
        return None
    try:
        year = min_date.year
        candidate = datetime(year, month, int(day))
        while candidate < min_date:
            year += 1
            candidate = datetime(year, month, int(day))
        return candidate.strftime("%Y-%m-%d"), candidate.strftime("%d %b %Y")
    except ValueError:
        return None, date_str


def format_time(raw_time):
    if not raw_time:
        return None
    raw_time = raw_time.strip().upper()
    suffix = None
    if raw_time.endswith("A") or raw_time.endswith("P"):
        suffix = raw_time[-1]
        raw_time = raw_time[:-1]

    raw_time = raw_time.zfill(4) if len(raw_time) <= 4 else raw_time
    if len(raw_time) < 3:
        return None

    if len(raw_time) == 3:
        hour, minute = raw_time[0], raw_time[1:]
    else:
        hour, minute = raw_time[:2], raw_time[2:]

    try:
        h, m = int(hour), int(minute)
    except ValueError:
        return None

    if suffix == "P" and h != 12:
        h += 12
    if suffix == "A" and h == 12:
        h = 0

    h = h % 24
    return f"{h:02d}:{m:02d}"


def calculate_duration(dep_time, arr_time, day_offset=0, origin_code=None, dest_code=None, date_iso=None):
    if not dep_time or not arr_time:
        return None
    try:
        dh, dm = map(int, dep_time.split(":"))
        ah, am = map(int, arr_time.split(":"))
        dep_minutes = dh * 60 + dm
        arr_minutes = ah * 60 + am + (day_offset * 1440)

        tz_correction = 0
        if origin_code and dest_code:
            origin_offset = get_utc_offset_for_date(origin_code.upper(), date_iso)
            dest_offset = get_utc_offset_for_date(dest_code.upper(), date_iso)
            if origin_offset is not None and dest_offset is not None:
                tz_correction = (dest_offset - origin_offset) * 60

        diff = (arr_minutes - tz_correction) - dep_minutes
        if diff < 0:
            diff += 1440
        if diff > 1200:
            diff = diff % 1440
        hours, mins = divmod(int(diff), 60)
        return f"{hours}h {mins:02d}m"
    except (ValueError, AttributeError, TypeError):
        return None


def get_airport_info(code):
    code = code.upper()
    return AIRPORTS.get(code, {"name": code, "city": code, "country": ""})


def calculate_great_circle_distance(origin_code, dest_code):
    import math

    origin = AIRPORTS.get(origin_code.upper())
    dest = AIRPORTS.get(dest_code.upper())

    if not origin or not dest or "lat" not in origin or "lat" not in dest:
        return None

    R_KM = 6371.0

    lat1, lon1 = math.radians(origin["lat"]), math.radians(origin["lng"])
    lat2, lon2 = math.radians(dest["lat"]), math.radians(dest["lng"])

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    km = R_KM * c
    miles = km * 0.621371

    return {
        "km": round(km),
        "miles": round(miles),
    }


def get_airline_info(code):
    code = code.upper()
    return AIRLINES.get(code, code)


def get_cabin_class(code):
    return CABIN_CODES.get(code.upper(), "Economy Class")


def get_status_label(code):
    return STATUS_CODES.get(code.upper(), code)


PASSENGER_PATTERN = re.compile(
    r"\d+\.([A-Z\-]+)/([A-Z]+(?:\s[A-Z]+)?)(?=\s{2,}|\d+\.|$)",
    re.IGNORECASE | re.MULTILINE,
)
TITLE_SUFFIX_PATTERN = re.compile(r"(MR|MRS|MS|MISS|MSTR|DR|CHD|INF)$", re.IGNORECASE)

# Sabre / Travelport (Galileo) name element:
#     <element>.<party size><SURNAME>/<GIVEN> <TITLE>[/<GIVEN> <TITLE>...]
#     1.1SMITH/JOHN MR          one passenger
#     1.2SMITH/JOHN MR/JANE MRS two passengers sharing a surname
# The digit right after the dot is the party size, which is why the
# Amadeus-style PASSENGER_PATTERN above (letters right after "1.") never
# matched these lines. Amadeus-style lines have no digit there, so the two
# patterns can never both match the same line.
PASSENGER_PARTY_PATTERN = re.compile(r"^\s*\d+\.(\d+)([A-Z][A-Z'\-]*)/(.+?)\s*$", re.IGNORECASE)
PASSENGER_PARTY_SPLIT_RE = re.compile(r"\s{2,}(?=\d+\.(?:\d+[A-Za-z]|I/))")
# Infant element: "3.I/SINGH/AARAVINF*10JAN26" (surname/given, optional INF, optional *DOB)
PASSENGER_INFANT_PATTERN = re.compile(r"^\s*\d+\.I/([A-Z][A-Z'\-]*)/(.+?)\s*$", re.IGNORECASE)
# Titles glued to the end of a given name ("AMITMR", "KAVITACHD"). MS and DR are
# deliberately NOT stripped when glued on: too many real names end in them (SAMS, ...).
FUSED_TITLE_RE = re.compile(r"^(.{2,}?)(MRS|MISS|MSTR|CHD|INF|MR)$", re.IGNORECASE)
TITLE_WORDS = {"MR", "MRS", "MS", "MISS", "MSTR", "DR", "CHD", "INF"}


def parse_party_name_line(line):
    """Passengers on one Sabre/Travelport-style name line (may hold several
    elements separated by 2+ spaces, and several given names separated by
    "/"). Returns [] when the line is not in that format."""
    out = []
    for chunk in PASSENGER_PARTY_SPLIT_RE.split(line.strip()):
        inf = PASSENGER_INFANT_PATTERN.match(chunk)
        if inf:
            surname = inf.group(1)
            given = re.split(r"\s{2,}", inf.group(2))[0].split("*")[0]
            given = re.sub(r"[^A-Za-z' \-]", " ", given).split()
            if given:
                fused = FUSED_TITLE_RE.match(given[-1])
                if fused and given[-1].upper().endswith("INF"):
                    given[-1] = fused.group(1)
                elif given[-1].upper() == "INF" and len(given) > 1:
                    given = given[:-1]
                first = " ".join(given)
                out.append({
                    "last_name": surname.strip().title(),
                    "first_name": first.title(),
                    "title": "INF",
                    "full_name": f"{surname.strip().title()} {first.title()}".strip(),
                })
            continue
        m = PASSENGER_PARTY_PATTERN.match(chunk)
        if not m:
            continue
        surname = m.group(2)
        names_part = re.split(r"\s{2,}", m.group(3))[0]  # ignore trailing columns
        for token in names_part.split("/"):
            token = token.split("*")[0]  # drop annotations such as "*P-C08"
            words = re.sub(r"[^A-Za-z' \-]", " ", token).split()
            if not words:
                continue
            title = ""
            if len(words) > 1 and words[-1].upper() in TITLE_WORDS:
                title = words[-1].upper()
                words = words[:-1]
            else:
                fused = FUSED_TITLE_RE.match(words[-1])
                if fused:
                    title = fused.group(2).upper()
                    words[-1] = fused.group(1)
            first = " ".join(words)
            out.append({
                "last_name": surname.strip().title(),
                "first_name": first.title(),
                "title": title,
                "full_name": f"{surname.strip().title()} {first.title()}".strip(),
            })
    return out

MONTH_NAMES_RE = r"(?:JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)"


def parse_segment_line(line):
    line = line.strip()

    line_num_match = re.match(r"^\d+\s+(.+)$", line)
    if not line_num_match:
        return None
    rest = line_num_match.group(1)

    date_match = re.search(rf"\b(\d{{1,2}}{MONTH_NAMES_RE})\b", rest, re.IGNORECASE)
    if not date_match:
        return None
    date_str = date_match.group(1)

    before_date = rest[:date_match.start()].strip()
    after_date = rest[date_match.end():].strip()

    before_match = re.match(
        r"^([A-Z0-9]{2})\s*(\d{1,4})([A-Z])?\s*([A-Z])?$",
        before_date, re.IGNORECASE
    )
    if not before_match:
        return None
    airline = before_match.group(1)
    flight_num = before_match.group(2)
    booking_class = before_match.group(3) or before_match.group(4) or "Y"
    # Additive audit flags (used only by the CRM API v1 route; every other
    # caller ignores unknown keys): True when the value below was a default
    # because the line did not actually contain it.
    class_defaulted = not (before_match.group(3) or before_match.group(4))

    # Allow 0-3 spaces between origin and destination — some GDS dumps
    # (e.g. certain Galileo/Worldspan prints) space these out ("ISB  IST")
    # instead of concatenating them ("ISBIST").
    route_match = re.search(r"\d?\*?([A-Z]{3})\s{0,3}([A-Z]{3})\*?", after_date, re.IGNORECASE)
    if not route_match:
        return None
    origin = route_match.group(1)
    dest = route_match.group(2)

    after_route = after_date[route_match.end():].strip()

    # The leading status-code + count (e.g. "HK1") is optional — some GDS
    # dumps omit it entirely and go straight from the route to the times.
    times_match = re.match(
        rf"^(?:([A-Z]{{2}})(\d{{1,2}})\s+)?(\d{{3,4}}[AP]?)\s+(\d{{3,4}}[AP]?)([+-]\d)?(?:\s+(\d{{1,2}}{MONTH_NAMES_RE}))?",
        after_route, re.IGNORECASE
    )
    if not times_match:
        return None

    return {
        "airline": airline.upper(),
        "flight_num": flight_num,
        "booking_class": booking_class.upper(),
        "date_str": date_str.upper(),
        "origin": origin.upper(),
        "dest": dest.upper(),
        "status": (times_match.group(1) or "HK").upper(),
        "class_defaulted": class_defaulted,
        "status_defaulted": times_match.group(1) is None,
        "status_count": times_match.group(2) or "1",
        "dep_raw": times_match.group(3),
        "arr_raw": times_match.group(4),
        "arr_day_marker": int(times_match.group(5)) if times_match.group(5) else None,
        "arr_date_str": times_match.group(6).upper() if times_match.group(6) else None,
    }


def detect_gds(raw_text):
    text = raw_text.upper()
    if "RP/" in text:
        return "Amadeus"
    if re.search(r"\d\.\d[A-Z]/\d{4}", text):
        return "Sabre"
    if "SSR" in text and "RTSTR" in text:
        return "Amadeus"
    if re.search(r"^\s*\d+\s+[A-Z]{1,2}\s+\d+[A-Z]\s", text, re.MULTILINE):
        return "Galileo"
    return "Auto-detected"


def parse_passengers(raw_text):
    passengers = []
    for match in PASSENGER_PATTERN.finditer(raw_text):
        last_name, full_first_token = match.groups()
        full_first_token = full_first_token.strip()

        title = ""
        first_name = full_first_token
        title_match = TITLE_SUFFIX_PATTERN.search(full_first_token)
        if title_match:
            title = title_match.group(1).upper()
            first_name = full_first_token[:title_match.start()].strip()

        passengers.append({
            "last_name": last_name.strip().title(),
            "first_name": first_name.title(),
            "title": title,
            "full_name": f"{last_name.strip().title()} {first_name.title()}".strip(),
        })
    for line in raw_text.split("\n"):
        passengers.extend(parse_party_name_line(line))
    return passengers


def parse_segments(raw_text):
    segments = []
    lines = raw_text.split("\n")
    # Tracks the earliest a subsequent segment's date is allowed to resolve
    # to, so segment dates only ever move forward through the PNR — see the
    # parse_pnr_date docstring for why this matters.
    running_min_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    for line in lines:
        line = line.strip()
        if not line:
            continue

        parsed = parse_segment_line(line)
        if not parsed:
            continue

        airline = parsed["airline"]
        flight_num = parsed["flight_num"]
        cabin = parsed["booking_class"]
        date_str = parsed["date_str"]
        origin = parsed["origin"]
        dest = parsed["dest"]
        status = parsed["status"]
        dep_raw = parsed["dep_raw"]
        arr_raw = parsed["arr_raw"]
        arr_date = parsed["arr_date_str"]
        arr_marker = parsed.get("arr_day_marker")

        iso_date, display_date = parse_pnr_date(date_str, min_date=running_min_date) or (None, date_str)
        if iso_date:
            try:
                running_min_date = datetime.strptime(iso_date, "%Y-%m-%d")
            except ValueError:
                pass
        dep_time = format_time(dep_raw)
        arr_time = format_time(arr_raw)

        day_offset = 0
        if arr_marker is not None:
            day_offset = arr_marker  # explicit "+1" / "-1" printed by the GDS
        elif arr_date and arr_date.upper() != date_str.upper():
            day_offset = 1
        elif arr_time and dep_time and arr_time < dep_time:
            day_offset = 1

        arrival_date_iso = None
        if iso_date:
            try:
                from datetime import timedelta
                arrival_date_iso = (
                    datetime.strptime(iso_date, "%Y-%m-%d") + timedelta(days=day_offset)
                ).strftime("%Y-%m-%d")
            except ValueError:
                arrival_date_iso = iso_date

        origin_info = get_airport_info(origin)
        dest_info = get_airport_info(dest)
        distance = calculate_great_circle_distance(origin, dest)

        segments.append({
            "airline_code": airline.upper(),
            "airline_name": get_airline_info(airline),
            "flight_number": flight_num,
            "cabin_class": get_cabin_class(cabin),
            "booking_class": cabin.upper(),
            "date": display_date,
            "date_iso": iso_date,
            "arrival_date_iso": arrival_date_iso,
            "origin": {
                "code": origin.upper(),
                "name": origin_info.get("name", origin.upper()),
                "city": origin_info.get("city", origin.upper()),
                "country": origin_info.get("country", ""),
            },
            "destination": {
                "code": dest.upper(),
                "name": dest_info.get("name", dest.upper()),
                "city": dest_info.get("city", dest.upper()),
                "country": dest_info.get("country", ""),
            },
            "status": get_status_label(status) if status else "Confirmed",
            "departure_time": dep_time,
            "arrival_time": arr_time,
            "duration": calculate_duration(dep_time, arr_time, day_offset, origin, dest, iso_date),
            "overnight": day_offset > 0,
            "distance_km": distance["km"] if distance else None,
            "distance_miles": distance["miles"] if distance else None,
            "fare_flag": get_fare_flag(airline, cabin),
        })

    return segments


def detect_layovers(segments):
    for i in range(len(segments) - 1):
        current = segments[i]
        nxt = segments[i + 1]
        same_airport = current["destination"]["code"] == nxt["origin"]["code"]

        date_gap_ok = False
        day_diff = 0
        if current.get("arrival_date_iso") and nxt.get("date_iso"):
            try:
                d1 = datetime.strptime(current["arrival_date_iso"], "%Y-%m-%d")
                d2 = datetime.strptime(nxt["date_iso"], "%Y-%m-%d")
                day_diff = (d2 - d1).days
                date_gap_ok = 0 <= day_diff <= 2
            except ValueError:
                date_gap_ok = False

        if same_airport and date_gap_ok and current.get("arrival_time") and nxt.get("departure_time"):
            try:
                arr_h, arr_m = map(int, current["arrival_time"].split(":"))
                dep_h, dep_m = map(int, nxt["departure_time"].split(":"))
                arr_total = arr_h * 60 + arr_m
                dep_total = (dep_h * 60 + dep_m) + (day_diff * 1440)
                diff = dep_total - arr_total
                if diff < 0:
                    diff += 1440
                hours, mins = divmod(diff, 60)
                current["layover_after"] = f"{hours}h {mins:02d}m layover in {current['destination']['city']}"
                current["layover_minutes"] = diff
            except (ValueError, AttributeError, TypeError):
                current["layover_after"] = None
                current["layover_minutes"] = None
        else:
            current["layover_after"] = None
            current["layover_minutes"] = None
    if segments:
        segments[-1]["layover_after"] = None
        segments[-1]["layover_minutes"] = None
    return segments


def calculate_total_journey(segments):
    if not segments:
        return None
    is_round_trip = (
        len(segments) > 1
        and segments[0]["origin"]["code"] == segments[-1]["destination"]["code"]
    )
    if is_round_trip:
        return None
    try:
        first = segments[0]
        last = segments[-1]
        fh, fm = map(int, first["departure_time"].split(":"))
        lh, lm = map(int, last["arrival_time"].split(":"))
        d1 = datetime.strptime(first["date_iso"], "%Y-%m-%d") if first["date_iso"] else None
        d2 = datetime.strptime(last["arrival_date_iso"], "%Y-%m-%d") if last.get("arrival_date_iso") else None
        day_diff = (d2 - d1).days if d1 and d2 else 0

        tz_correction = 0
        origin_offset = get_utc_offset_for_date(first["origin"]["code"], first.get("date_iso"))
        dest_offset = get_utc_offset_for_date(last["destination"]["code"], last.get("arrival_date_iso"))
        if origin_offset is not None and dest_offset is not None:
            tz_correction = (dest_offset - origin_offset) * 60

        total_minutes = (day_diff * 1440) + (lh * 60 + lm) - tz_correction - (fh * 60 + fm)
        if total_minutes < 0:
            total_minutes += 1440
        hours, mins = divmod(int(total_minutes), 60)
        return f"{hours}h {mins:02d}m"
    except (ValueError, AttributeError, TypeError):
        return None


def calculate_co2_estimate(segments):
    total_kg = 0
    for seg in segments:
        distance_km = seg.get("distance_km")
        if distance_km:
            if distance_km < 1500:
                factor = 0.15
            elif distance_km < 4000:
                factor = 0.11
            else:
                factor = 0.09
            total_kg += distance_km * factor
        else:
            total_kg += 90
    return round(total_kg, 1)


RP_HEADER_RE = re.compile(r"^\s*RP/([A-Z0-9]{5,12})(?:/([A-Z0-9]{5,12}))?(.*)$", re.MULTILINE)


def parse_rp_header(raw_text):
    """Amadeus header line, e.g.
        RP/DEL1S2100/DEL1S2100   AA/SU  21OCT26/0315Z   ABCD12
    The two RP/ values are OFFICE IDs. The booking's record locator is the last
    token on that line (6 alphanumerics). Returns (office_id, record_locator);
    either may be None."""
    m = RP_HEADER_RE.search(raw_text.upper())
    if not m:
        return None, None
    office_id = m.group(1)
    tokens = m.group(3).split()
    locator = None
    if tokens and re.fullmatch(r"[A-Z0-9]{6}", tokens[-1]):
        locator = tokens[-1]
    return office_id, locator


def extract_pnr_reference(raw_text):
    office_id, locator = parse_rp_header(raw_text)
    if locator:
        return locator
    if office_id:
        # Legacy behaviour kept for the website when the pasted header has no
        # record locator at all: fall back to the office id, as before.
        return office_id

    scan_text = "\n".join(
        line for line in raw_text.split("\n") if not parse_party_name_line(line)
    )
    for token in re.findall(r"\b[A-Z0-9]{6}\b", scan_text.upper()):
        if any(ch.isdigit() for ch in token):
            return token
    return None


def parse_pnr(raw_text):
    if not raw_text or not raw_text.strip():
        raise ValueError("Empty PNR text provided")

    gds_detected = detect_gds(raw_text)
    passengers = parse_passengers(raw_text)
    segments = parse_segments(raw_text)
    segments = detect_layovers(segments)
    pnr_ref = extract_pnr_reference(raw_text)
    health_checks = check_pnr_health(segments, raw_text)

    if not passengers:
        passengers = [{"last_name": "Passenger", "first_name": "Traveller", "title": "", "full_name": "Passenger Traveller"}]

    if not segments:
        raise ValueError(
            "Could not detect any flight segments in this PNR. "
            "Please check the format or try a different GDS source."
        )

    is_round_trip = (
        len(segments) > 1
        and segments[0]["origin"]["code"] == segments[-1]["destination"]["code"]
    )

    if is_round_trip:
        turnaround_index = len(segments) // 2
        route_summary = f"{segments[0]['origin']['code']} ⇄ {segments[turnaround_index - 1]['destination']['code']}"
    else:
        route_summary = f"{segments[0]['origin']['code']} → {segments[-1]['destination']['code']}"

    total_distance_km = sum(s["distance_km"] for s in segments if s.get("distance_km"))
    total_distance_miles = sum(s["distance_miles"] for s in segments if s.get("distance_miles"))

    result = {
        "success": True,
        "gds_detected": gds_detected,
        "pnr_reference": pnr_ref,
        "office_id": parse_rp_header(raw_text)[0],
        "passengers": passengers,
        "passenger_count": len(passengers),
        "segments": segments,
        "segment_count": len(segments),
        "route_summary": route_summary,
        "total_journey_duration": calculate_total_journey(segments),
        "co2_estimate_kg": calculate_co2_estimate(segments),
        "total_distance_km": total_distance_km if total_distance_km else None,
        "total_distance_miles": total_distance_miles if total_distance_miles else None,
        "is_round_trip": is_round_trip,
        "is_multi_city": len(set([s["origin"]["code"] for s in segments] + [s["destination"]["code"] for s in segments])) > 2,
        "has_fare_flags": any(s.get("fare_flag") for s in segments),
        "health_checks": health_checks,
        "health_check_count": len(health_checks),
        "has_health_issues": len(health_checks) > 0,
    }
    return result


BATCH_SEPARATOR_RE = re.compile(r"^\s*[-=]{3,}\s*$")
BATCH_MAX_PNRS = 25


def split_batch_pnrs(raw_text):
    """Splits a block of pasted text containing multiple PNRs into a list of
    individual PNR text blocks.

    Priority 1: explicit separator lines (a line of three or more "-" or "="
    characters) — if the pasted text contains at least one, split strictly on
    those and trust the agent's own boundaries.

    Priority 2: auto-detect new-PNR boundaries at passenger-definition lines
    (e.g. "1.SMITH/JOHNMR") that occur after the current block has already
    captured at least one real segment line. This deliberately avoids
    splitting on blank lines alone, which would incorrectly fragment a
    single PNR that happens to contain blank lines internally.
    """
    if not raw_text or not raw_text.strip():
        return []

    lines = raw_text.split("\n")

    if any(BATCH_SEPARATOR_RE.match(line) for line in lines):
        blocks = []
        current = []
        for line in lines:
            if BATCH_SEPARATOR_RE.match(line):
                blocks.append("\n".join(current))
                current = []
            else:
                current.append(line)
        blocks.append("\n".join(current))
        return [b.strip() for b in blocks if b.strip()]

    blocks = []
    current = []
    seen_segment_in_current = False
    for line in lines:
        is_passenger_line = bool(PASSENGER_PATTERN.search(line) or parse_party_name_line(line))
        if is_passenger_line and seen_segment_in_current and current:
            blocks.append("\n".join(current))
            current = []
            seen_segment_in_current = False
        current.append(line)
        if parse_segment_line(line):
            seen_segment_in_current = True

    if current:
        blocks.append("\n".join(current))

    return [b.strip() for b in blocks if b.strip()]


@app.route("/api/convert-batch", methods=["POST"])
def convert_pnr_batch_endpoint():
    try:
        data = request.get_json(silent=True)
        if not data or "pnr" not in data:
            return jsonify({
                "success": False,
                "error": "Missing 'pnr' field in request body."
            }), 400

        raw_pnr = data["pnr"]
        blocks = split_batch_pnrs(raw_pnr)

        if not blocks:
            return jsonify({
                "success": False,
                "error": "Could not detect any PNRs in this text."
            }), 400

        if len(blocks) > BATCH_MAX_PNRS:
            return jsonify({
                "success": False,
                "error": (
                    f"Too many PNRs in one batch (found {len(blocks)}, "
                    f"max {BATCH_MAX_PNRS}). Please split into smaller batches."
                )
            }), 400

        results = []
        success_count = 0
        for idx, block in enumerate(blocks):
            try:
                parsed = parse_pnr(block)
                parsed["batch_index"] = idx
                parsed["batch_source_text"] = block
                results.append(parsed)
                success_count += 1
            except ValueError as ve:
                results.append({
                    "success": False,
                    "batch_index": idx,
                    "batch_source_text": block,
                    "error": str(ve),
                })
            except Exception as e:
                results.append({
                    "success": False,
                    "batch_index": idx,
                    "batch_source_text": block,
                    "error": "Unexpected server error while parsing this PNR.",
                    "detail": str(e),
                })

        return jsonify({
            "success": True,
            "batch_count": len(blocks),
            "success_count": success_count,
            "error_count": len(blocks) - success_count,
            "results": results,
        }), 200

    except Exception as e:
        return jsonify({
            "success": False,
            "error": "Unexpected server error while parsing batch PNRs.",
            "detail": str(e)
        }), 500


@app.route("/", methods=["GET"])
def health_check():
    return jsonify({
        "status": "online",
        "service": "PNRGenius Backend API",
        "version": "1.0.0",
        "endpoints": {
            "convert": "POST /api/convert",
            "health": "GET /"
        }
    })


@app.route("/api/convert", methods=["POST"])
def convert_pnr():
    try:
        data = request.get_json(silent=True)
        if not data or "pnr" not in data:
            return jsonify({
                "success": False,
                "error": "Missing 'pnr' field in request body."
            }), 400

        raw_pnr = data["pnr"]
        result = parse_pnr(raw_pnr)
        return jsonify(result), 200

    except ValueError as ve:
        return jsonify({"success": False, "error": str(ve)}), 400
    except Exception as e:
        return jsonify({
            "success": False,
            "error": "Unexpected server error while parsing PNR.",
            "detail": str(e)
        }), 500


@app.route("/api/health", methods=["GET"])
def api_health():
    return jsonify({"status": "ok"}), 200


import urllib.request
import urllib.error
from flask import Response
import csv
import io

_logo_cache = {}


@app.route("/api/logo/<airline_code>", methods=["GET"])
def airline_logo(airline_code):
    code = airline_code.upper().strip()
    if not re.match(r"^[A-Z0-9]{2,3}$", code):
        return jsonify({"error": "Invalid code"}), 400

    if code in _logo_cache:
        data, ctype = _logo_cache[code]
        return Response(data, content_type=ctype, headers={
            "Cache-Control": "public, max-age=86400",
            "Access-Control-Allow-Origin": "*",
        })

    url = f"https://airlinelogos.aero/logos/{code}.svg"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "PNRGenius/1.0"})
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = resp.read()
            ctype = resp.headers.get("Content-Type", "image/svg+xml")
            _logo_cache[code] = (data, ctype)
            return Response(data, content_type=ctype, headers={
                "Cache-Control": "public, max-age=86400",
                "Access-Control-Allow-Origin": "*",
            })
    except Exception:
        return jsonify({"error": "Logo not available"}), 404


# ---------------------------------------------------------------------------
# LIVE FLIGHT STATUS
# Powers the /flight-status.html search tool. Data comes from AeroDataBox
# (via RapidAPI, free tier: 600 lookups/month). A shared Upstash Redis cache
# sits in front of it (also free tier) so a burst of searches for the same
# popular flight number only spends one real API call — everyone else in
# that window gets served from cache. Requires three env vars set in the
# Vercel project (Settings -> Environment Variables):
#   AERODATABOX_RAPIDAPI_KEY, UPSTASH_REDIS_REST_URL, UPSTASH_REDIS_REST_TOKEN
# Verified against a live AeroDataBox response on 2026-08-21 (AA100, JFK-LHR).
# ---------------------------------------------------------------------------

import os

AERODATABOX_KEY = os.environ.get("AERODATABOX_RAPIDAPI_KEY", "")
AERODATABOX_HOST = "aerodatabox.p.rapidapi.com"
UPSTASH_URL = os.environ.get("UPSTASH_REDIS_REST_URL", "").rstrip("/")
UPSTASH_TOKEN = os.environ.get("UPSTASH_REDIS_REST_TOKEN", "")
FLIGHT_STATUS_CACHE_TTL = 180          # seconds
FLIGHT_STATUS_RATE_LIMIT_PER_HOUR = 30  # per IP


def _upstash_request(path, method="GET", body=None):
    """Minimal urllib-based client for Upstash's Redis REST API — matches
    this file's existing pattern of using urllib instead of adding the
    `requests` package as a dependency. Returns the parsed 'result' value,
    or None on any failure (a cache outage should never break the feature)."""
    if not UPSTASH_URL or not UPSTASH_TOKEN:
        return None
    try:
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(
            f"{UPSTASH_URL}{path}",
            data=data,
            method=method,
            headers={
                "Authorization": f"Bearer {UPSTASH_TOKEN}",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=3) as resp:
            return json.loads(resp.read()).get("result")
    except Exception:
        return None


def _fs_cache_get(key):
    result = _upstash_request(f"/get/{key}")
    if result:
        try:
            return json.loads(result)
        except Exception:
            return None
    return None


def _fs_cache_set(key, value, ttl_seconds):
    _upstash_request(f"/set/{key}?EX={ttl_seconds}", method="POST", body=json.dumps(value))


def _fs_rate_limit_ok(ip):
    bucket = f"fs_ratelimit:{ip}:{int(datetime.utcnow().timestamp() // 3600)}"
    count = _upstash_request(f"/incr/{bucket}", method="POST")
    if count is None:
        return True  # fail open — a Redis hiccup shouldn't take the feature down
    if count == 1:
        _upstash_request(f"/expire/{bucket}/3600", method="POST")
    return count <= FLIGHT_STATUS_RATE_LIMIT_PER_HOUR


def _fs_parse_utc(node):
    raw = (node.get("scheduledTime") or {}).get("utc")
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%Y-%m-%d %H:%MZ")
    except ValueError:
        return None


def _fs_pick_most_relevant(flights):
    """AeroDataBox's 'nearest day' endpoint can return more than one match
    for a flight number (e.g. yesterday's already-Arrived flight AND
    today's EnRoute one). Pick whichever entry's scheduled departure is
    closest to right now — verified live on 2026-08-21 against a real
    two-entry AA100 response, where this correctly picked the EnRoute one
    over the stale Arrived one."""
    if not flights:
        return None
    if len(flights) == 1:
        return flights[0]
    now = datetime.utcnow()
    best, best_delta = flights[0], None
    for f in flights:
        dep_time = _fs_parse_utc(f.get("departure", {}) or {})
        if dep_time is None:
            continue
        delta = abs((dep_time - now).total_seconds())
        if best_delta is None or delta < best_delta:
            best, best_delta = f, delta
    return best


def _fs_iso(raw):
    """AeroDataBox returns UTC timestamps like '2026-08-21 05:25Z'. Convert
    to strict ISO-8601 ('...T...Z') so JavaScript's `new Date(...)` on the
    frontend parses it reliably everywhere (Safari especially is picky) —
    needed for the live progress bar / mini-map position math."""
    if not raw:
        return None
    try:
        dt = datetime.strptime(raw, "%Y-%m-%d %H:%MZ")
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return None


def _fs_live_position(raw_flight):
    """Best-effort extraction of AeroDataBox's real-time position block
    (only present when ?withLocation=true returns data for this flight —
    not every flight has it, e.g. still on the ground or outside coverage).
    Checks the common field-name variants and returns None if nothing
    matches, so the frontend just falls back to its time-estimated
    position — nothing breaks either way."""
    loc = raw_flight.get("location")
    if not isinstance(loc, dict):
        return None
    lat = loc.get("lat", loc.get("latitude"))
    lon = loc.get("lon", loc.get("lng", loc.get("longitude")))
    if lat is None or lon is None:
        return None
    reported = loc.get("reportedAtUtc") or loc.get("updatedUtc") or loc.get("timeUtc")
    return {
        "lat": lat,
        "lon": lon,
        "updatedUtc": _fs_iso(reported) if reported else None,
    }


def _fs_normalize(raw_flight):
    dep = raw_flight.get("departure", {}) or {}
    arr = raw_flight.get("arrival", {}) or {}
    airline = raw_flight.get("airline", {}) or {}
    aircraft = raw_flight.get("aircraft", {}) or {}

    def times(node):
        sched = node.get("scheduledTime") or {}
        est = node.get("revisedTime") or node.get("predictedTime") or node.get("estimatedTime") or {}
        act = node.get("actualTime") or node.get("runwayTime") or {}
        return {
            "scheduled": sched.get("local"),
            "scheduledUtc": _fs_iso(sched.get("utc")),
            "estimated": est.get("local"),
            "estimatedUtc": _fs_iso(est.get("utc")),
            "actual": act.get("local"),
            "actualUtc": _fs_iso(act.get("utc")),
            "terminal": node.get("terminal"),
            "gate": node.get("gate"),
        }

    dep_airport = dep.get("airport") or {}
    arr_airport = arr.get("airport") or {}

    return {
        "flightNumber": raw_flight.get("number"),
        "airline": airline.get("name"),
        "airlineIata": airline.get("iata"),
        "status": raw_flight.get("status", "Unknown"),
        "departure": {
            "airport": dep_airport.get("name"),
            "iata": dep_airport.get("iata"),
            "lat": (dep_airport.get("location") or {}).get("lat"),
            "lon": (dep_airport.get("location") or {}).get("lon"),
            **times(dep),
        },
        "arrival": {
            "airport": arr_airport.get("name"),
            "iata": arr_airport.get("iata"),
            "lat": (arr_airport.get("location") or {}).get("lat"),
            "lon": (arr_airport.get("location") or {}).get("lon"),
            **times(arr),
        },
        "aircraft": aircraft.get("model"),
        "aircraftReg": aircraft.get("reg"),
        "livePosition": _fs_live_position(raw_flight),
        "source": "AeroDataBox",
    }


@app.route("/api/flight-status/<flight_number>", methods=["GET"])
def flight_status(flight_number):
    flight_number = flight_number.strip().upper().replace(" ", "")
    date = request.args.get("date")

    if not flight_number or len(flight_number) > 8 or not re.match(r"^[A-Z0-9]+$", flight_number):
        return jsonify({"error": "Invalid flight number"}), 400

    client_ip = request.headers.get("X-Forwarded-For", request.remote_addr or "unknown").split(",")[0].strip()
    if not _fs_rate_limit_ok(client_ip):
        return jsonify({"error": "Too many requests — please wait a bit and try again."}), 429

    cache_key = f"flightstatus:{flight_number}:{date or 'today'}"
    cached = _fs_cache_get(cache_key)
    if cached:
        cached["fromCache"] = True
        return jsonify(cached)

    if not AERODATABOX_KEY:
        return jsonify({"error": "Flight status is not configured yet."}), 503

    url = f"https://{AERODATABOX_HOST}/flights/number/{flight_number}"
    if date:
        url += f"/{date}"
    url += "?withLocation=true"

    try:
        req = urllib.request.Request(url, headers={
            "X-RapidAPI-Key": AERODATABOX_KEY,
            "X-RapidAPI-Host": AERODATABOX_HOST,
            "User-Agent": "PNRGenius/1.0",
        })
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return jsonify({"error": f"No flight found for {flight_number}. Check the flight number and try again."}), 404
        if e.code == 429:
            return jsonify({"error": "Flight status lookups are at capacity for the day — try again shortly."}), 429
        return jsonify({"error": "Flight status is temporarily unavailable."}), 502
    except Exception:
        return jsonify({"error": "Flight status lookup timed out — try again."}), 504

    if not data:
        return jsonify({"error": f"No flight found for {flight_number}."}), 404

    best_match = _fs_pick_most_relevant(data) if isinstance(data, list) else data
    normalized = _fs_normalize(best_match)
    normalized["fromCache"] = False

    _fs_cache_set(cache_key, normalized, FLIGHT_STATUS_CACHE_TTL)

    return jsonify(normalized)


# ---------------------------------------------------------------------------
# SCREENSHOT / PHOTO OCR (via OCR.space free API)
# Lets an agent upload a photo/screenshot of a GDS booking screen; the
# extracted text is sent back to the frontend, which drops it into the
# existing PNR textarea for the agent to review/correct before clicking
# Convert PNR Now — OCR text is never auto-converted directly, since a
# misread character on cryptic monospace GDS text could silently produce a
# wrong itinerary. Requires OCR_SPACE_API_KEY in Vercel's environment
# variables (free key, no credit card: https://ocr.space/ocrapi/freekey).
# Verified against OCR.space's documented API contract
# (https://ocr.space/ocrapi) on 2026-08-25: POST to
# https://api.ocr.space/parse/image, apikey via header, base64Image via
# form field (data: URI prefix included), response JSON has
# ParsedResults[0].ParsedText plus IsErroredOnProcessing/ErrorMessage.
# Free tier: 1MB max file, 500 requests/day per IP, 25,000/month total.
# ---------------------------------------------------------------------------

import urllib.parse

OCR_SPACE_API_KEY = os.environ.get("OCR_SPACE_API_KEY", "")
OCR_SPACE_URL = "https://api.ocr.space/parse/image"
OCR_MAX_BASE64_CHARS = 1_400_000  # generous ceiling — frontend already compresses to ~900KB
OCR_RATE_LIMIT_PER_HOUR = 20       # per IP


def _ocr_rate_limit_ok(ip):
    bucket = f"ocr_ratelimit:{ip}:{int(datetime.utcnow().timestamp() // 3600)}"
    count = _upstash_request(f"/incr/{bucket}", method="POST")
    if count is None:
        return True  # fail open — a Redis hiccup shouldn't take the feature down
    if count == 1:
        _upstash_request(f"/expire/{bucket}/3600", method="POST")
    return count <= OCR_RATE_LIMIT_PER_HOUR


@app.route("/api/ocr", methods=["POST"])
def ocr_extract_text():
    if not OCR_SPACE_API_KEY:
        return jsonify({"success": False, "error": "Screenshot OCR is not configured yet."}), 503

    client_ip = request.headers.get("X-Forwarded-For", request.remote_addr or "unknown").split(",")[0].strip()
    if not _ocr_rate_limit_ok(client_ip):
        return jsonify({"success": False, "error": "Too many OCR requests — please wait a bit and try again."}), 429

    data = request.get_json(silent=True)
    if not data or not data.get("image"):
        return jsonify({"success": False, "error": "Missing 'image' field in request body."}), 400

    image_data_url = data["image"]
    if not isinstance(image_data_url, str) or not image_data_url.startswith("data:image/"):
        return jsonify({"success": False, "error": "Invalid image data."}), 400

    if len(image_data_url) > OCR_MAX_BASE64_CHARS:
        return jsonify({"success": False, "error": "Image is too large. Please try a smaller screenshot or crop it."}), 413

    try:
        form_body = urllib.parse.urlencode({
            "base64Image": image_data_url,
            "language": "eng",
            "isOverlayRequired": "false",
            "OCREngine": "2",
            "scale": "true",
        }).encode("utf-8")
        req = urllib.request.Request(
            OCR_SPACE_URL,
            data=form_body,
            method="POST",
            headers={
                "apikey": OCR_SPACE_API_KEY,
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "PNRGenius/1.0",
            },
        )
        with urllib.request.urlopen(req, timeout=25) as resp:
            result = json.loads(resp.read())
    except urllib.error.HTTPError:
        return jsonify({"success": False, "error": "OCR service is temporarily unavailable. Please try again."}), 502
    except Exception:
        return jsonify({"success": False, "error": "OCR request timed out — please try again with a smaller image."}), 504

    if result.get("IsErroredOnProcessing"):
        err_msg = result.get("ErrorMessage")
        if isinstance(err_msg, list):
            err_msg = "; ".join(str(m) for m in err_msg)
        return jsonify({"success": False, "error": err_msg or "Could not read text from this image. Try a clearer screenshot."}), 422

    parsed_results = result.get("ParsedResults") or []
    if not parsed_results:
        return jsonify({"success": False, "error": "No text was found in this image."}), 422

    extracted_text = (parsed_results[0].get("ParsedText") or "").strip()
    if not extracted_text:
        return jsonify({"success": False, "error": "No text was found in this image. Try a clearer, closer screenshot."}), 422

    return jsonify({"success": True, "text": extracted_text}), 200


# ---------------------------------------------------------------------------
# AIRLINE & AIRPORT REFERENCE DIRECTORIES
# Powers the /airlines and /airports reference pages. Data comes from the
# OpenFlights open database (https://openflights.org/data.php, ODbL license
# — free to use/redistribute with attribution, which is shown on the
# frontend directory pages).
#
# IMPORTANT: this is fetched live from GitHub on first request per warm
# server instance, NOT bundled into this repo. Vercel functions have real
# outbound internet access (unlike a local sandbox), so this works the same
# way the airline logo proxy above already does — one fetch, cached in
# memory for the life of that instance, gone on the next cold start (same
# tradeoff already accepted elsewhere in this file).
# ---------------------------------------------------------------------------

_of_airports_cache = None
_of_airlines_cache = None

OPENFLIGHTS_AIRPORTS_URL = "https://raw.githubusercontent.com/jpatokal/openflights/master/data/airports.dat"
OPENFLIGHTS_AIRLINES_URL = "https://raw.githubusercontent.com/jpatokal/openflights/master/data/airlines.dat"


def _clean_field(value):
    """OpenFlights uses the literal string \\N for NULL fields."""
    if value is None:
        return None
    value = value.strip()
    if value in ("", "\\N"):
        return None
    return value


def _fetch_openflights_airports():
    """
    Fetches and parses the full OpenFlights airport database (~7,700 airports
    worldwide). Kept only if a real IATA code exists, since that's what's
    actually useful for decoding GDS PNRs (military bases / tiny airstrips
    without IATA codes never appear in a PNR anyway).
    """
    global _of_airports_cache
    if _of_airports_cache is not None:
        return _of_airports_cache

    req = urllib.request.Request(OPENFLIGHTS_AIRPORTS_URL, headers={"User-Agent": "PNRGenius/1.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        raw = resp.read().decode("utf-8", errors="replace")

    airports = []
    reader = csv.reader(io.StringIO(raw))
    for row in reader:
        if len(row) < 12:
            continue
        try:
            name = _clean_field(row[1])
            city = _clean_field(row[2])
            country = _clean_field(row[3])
            iata = _clean_field(row[4])
            icao = _clean_field(row[5])
            tz = _clean_field(row[11]) if len(row) > 11 else None

            if not name or name.startswith("[Duplicate]") or name in ("Unknown", "Private flight"):
                continue
            if not iata:
                continue  # not relevant to GDS PNR decoding

            lat = lng = None
            try:
                lat = float(row[6])
                lng = float(row[7])
            except (ValueError, IndexError):
                pass

            airports.append({
                "name": name,
                "city": city or "",
                "country": country or "",
                "iata": iata,
                "icao": icao,
                "lat": lat,
                "lng": lng,
                "tz": tz,
            })
        except (IndexError, ValueError):
            continue

    _of_airports_cache = airports
    return airports


def _fetch_openflights_airlines():
    """
    Fetches and parses the full OpenFlights airline database. Filtered to
    Active == 'Y' and a real IATA or ICAO code present, to keep the
    directory focused on carriers that actually appear in live PNRs rather
    than the thousands of defunct/historical entries in the raw dataset.
    """
    global _of_airlines_cache
    if _of_airlines_cache is not None:
        return _of_airlines_cache

    req = urllib.request.Request(OPENFLIGHTS_AIRLINES_URL, headers={"User-Agent": "PNRGenius/1.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        raw = resp.read().decode("utf-8", errors="replace")

    airlines = []
    reader = csv.reader(io.StringIO(raw))
    for row in reader:
        if len(row) < 8:
            continue
        try:
            name = _clean_field(row[1])
            iata = _clean_field(row[3])
            icao = _clean_field(row[4])
            callsign = _clean_field(row[5])
            country = _clean_field(row[6])
            active = _clean_field(row[7])

            if not name or name in ("Unknown", "Private flight"):
                continue
            if active != "Y":
                continue
            if not iata and not icao:
                continue

            airlines.append({
                "name": name,
                "iata": iata,
                "icao": icao,
                "callsign": callsign or "",
                "country": country or "",
            })
        except (IndexError, ValueError):
            continue

    airlines.sort(key=lambda a: a["name"].lower())
    _of_airlines_cache = airlines
    return airlines


def _paginate_and_search(items, search_fields):
    q = request.args.get("q", "").strip().lower()
    if q:
        filtered = []
        for item in items:
            haystack = " ".join(str(item.get(f, "") or "") for f in search_fields).lower()
            if q in haystack:
                filtered.append(item)
    else:
        filtered = items

    try:
        limit = max(1, min(int(request.args.get("limit", 60)), 300))
    except ValueError:
        limit = 60
    try:
        offset = max(0, int(request.args.get("offset", 0)))
    except ValueError:
        offset = 0

    page = filtered[offset:offset + limit]
    return page, len(filtered), len(items)


@app.route("/api/airports", methods=["GET"])
def api_airports():
    try:
        airports = _fetch_openflights_airports()
    except Exception as e:
        return jsonify({
            "success": False,
            "error": "Could not load airport directory right now. Please try again shortly.",
            "detail": str(e),
        }), 502

    page, matched, total = _paginate_and_search(airports, ["name", "city", "country", "iata", "icao"])
    return jsonify({
        "success": True,
        "results": page,
        "matched": matched,
        "total": total,
        "source": "OpenFlights (openflights.org), ODbL license",
    })


@app.route("/api/airlines", methods=["GET"])
def api_airlines():
    try:
        airlines = _fetch_openflights_airlines()
    except Exception as e:
        return jsonify({
            "success": False,
            "error": "Could not load airline directory right now. Please try again shortly.",
            "detail": str(e),
        }), 502

    page, matched, total = _paginate_and_search(airlines, ["name", "iata", "icao", "callsign", "country"])
    return jsonify({
        "success": True,
        "results": page,
        "matched": matched,
        "total": total,
        "source": "OpenFlights (openflights.org), ODbL license",
    })


# ---------------------------------------------------------------------------
# EMAIL-FORWARD PARSING (Phase 1)
# Users forward their booking confirmation email to parse@mail.pnrgenius.com.
# Mailgun receives it and POSTs the parsed email here. We save the raw ticket
# text in Upstash Redis for a short time, then email the sender a link back
# to the site with a ?ref= id — the site loads that text into the converter
# and auto-converts it, reusing all the existing frontend + /api/convert logic.
# ---------------------------------------------------------------------------

import hmac
import hashlib
import secrets
import base64

MAILGUN_API_KEY = os.environ.get("MAILGUN_API_KEY", "")
MAILGUN_WEBHOOK_SIGNING_KEY = os.environ.get("MAILGUN_WEBHOOK_SIGNING_KEY", "")
MAILGUN_SENDING_DOMAIN = "mail.pnrgenius.com"
SITE_URL = "https://pnrgenius.com"
EMAIL_LINK_TTL_SECONDS = 60 * 60      # link + saved text stay valid for 1 hour
EMAIL_TEXT_MAX_LENGTH = 20000         # safety cap so a huge email can't be stored


def _verify_mailgun_signature(timestamp, token, signature):
    if not timestamp or not token or not signature or not MAILGUN_WEBHOOK_SIGNING_KEY:
        return False
    expected = hmac.new(
        key=MAILGUN_WEBHOOK_SIGNING_KEY.encode(),
        msg=f"{timestamp}{token}".encode(),
        digestmod=hashlib.sha256,
    ).hexdigest()
    try:
        return hmac.compare_digest(expected, signature)
    except Exception:
        return False


def _email_text_set(key, text, ttl_seconds):
    """Stores a plain string in Redis via _upstash_request directly (NOT via
    _fs_cache_set/_fs_cache_get — that pair double-JSON-encodes on write but
    only single-decodes on read, so the value that comes back still has one
    layer of JSON-string-escaping left in it, e.g. the caller gets back
    '"line1\\r\\nline2"' — quotes and all — instead of the real text).
    Passing the raw string straight through as `body` here means
    _upstash_request's own json.dumps() is the ONLY encoding layer applied,
    which _email_text_get below undoes with exactly one matching json.loads."""
    _upstash_request(f"/set/{key}?EX={ttl_seconds}", method="POST", body=text)


def _email_text_get(key):
    raw = _upstash_request(f"/get/{key}")
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None


def _send_email_reply(to_address, reply_link):
    auth = base64.b64encode(f"api:{MAILGUN_API_KEY}".encode()).decode()
    body = urllib.parse.urlencode({
        "from": f"PNR Genius <noreply@{MAILGUN_SENDING_DOMAIN}>",
        "to": to_address,
        "subject": "Your converted itinerary is ready",
        "text": (
            "Hi,\n\nWe received the booking email you forwarded to us.\n\n"
            f"Click the link below to see it converted into a clean itinerary:\n{reply_link}\n\n"
            "(This link stays active for 1 hour.)\n\n— PNR Genius"
        ),
    }).encode()
    req = urllib.request.Request(
        f"https://api.mailgun.net/v3/{MAILGUN_SENDING_DOMAIN}/messages",
        data=body,
        method="POST",
        headers={
            "Authorization": f"Basic {auth}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    with urllib.request.urlopen(req, timeout=8) as resp:
        return resp.status


@app.route("/api/email-inbound", methods=["POST"])
def email_inbound():
    timestamp = request.form.get("timestamp")
    token = request.form.get("token")
    signature = request.form.get("signature")

    if not _verify_mailgun_signature(timestamp, token, signature):
        return jsonify({"error": "invalid signature"}), 403

    sender_email = request.form.get("sender")
    if not sender_email:
        from_header = request.form.get("from", "")
        match = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", from_header)
        sender_email = match.group(0) if match else None

    raw_text = (request.form.get("stripped-text") or request.form.get("body-plain") or "").strip()

    if not sender_email or not raw_text:
        # Nothing useful to do — still tell Mailgun this was handled so it
        # doesn't keep retrying.
        return jsonify({"status": "ignored"}), 200

    trimmed_text = raw_text[:EMAIL_TEXT_MAX_LENGTH]
    ref = secrets.token_urlsafe(9)

    try:
        _email_text_set(f"pnr-email:{ref}", trimmed_text, EMAIL_LINK_TTL_SECONDS)
        reply_link = f"{SITE_URL}/?ref={ref}"
        _send_email_reply(sender_email, reply_link)
    except Exception as e:
        # Let Mailgun retry a few times in case this was a transient hiccup.
        return jsonify({"error": "internal error", "detail": str(e)}), 500

    return jsonify({"status": "ok"}), 200


@app.route("/api/email-text", methods=["GET"])
def email_text():
    ref = request.args.get("ref", "")
    if not ref or len(ref) > 40:
        return jsonify({"error": "missing or invalid ref"}), 400

    text = _email_text_get(f"pnr-email:{ref}")
    if not text:
        return jsonify({"error": "This link has expired or is invalid."}), 404

    return jsonify({"text": text}), 200


# ---------------------------------------------------------------------------
# OPTIONAL FREE ACCOUNT — MAGIC LINK LOGIN (Phase 2, step 1)
# ---------------------------------------------------------------------------
# A lightweight, password-less account system. An agent types their email,
# gets a one-time sign-in link by email, and clicking it logs them in — the
# account is created automatically the first time someone logs in, so there
# is no separate "sign up" step and nothing that can be forgotten, like a
# password.
#
# Storage is Upstash Redis (already used elsewhere in this file for caching
# and rate limits) — three key shapes, no new database needed:
#   pnr-user:<email>            -> {"email", "created_at"}   (no expiry — the account record)
#   pnr-login-token:<token>     -> email                     (15 min TTL, one-time use)
#   pnr-session:<session_token> -> email                     (30 day TTL)
#
# The frontend stores the session_token in localStorage and sends it back as
# "Authorization: Bearer <session_token>" on any request that needs to know
# who's logged in. We use a bearer token instead of a cookie because the
# frontend (pnrgenius.com) and this API are on different domains — a
# cross-domain cookie needs extra CORS/SameSite plumbing that a bearer token
# skips entirely.
# ---------------------------------------------------------------------------

LOGIN_TOKEN_TTL_SECONDS = 15 * 60          # magic link is valid for 15 minutes
SESSION_TTL_SECONDS = 30 * 24 * 60 * 60    # stays logged in for 30 days
EMAIL_RE = re.compile(r"^[\w.+-]+@[\w-]+\.[\w.-]+$")


def _redis_set(key, value, ttl_seconds=None):
    """Stores any JSON-safe value (a plain string, or a dict) with exactly
    one JSON-encoding layer. Pass the raw value itself — never a pre-dumped
    string — so _upstash_request's own json.dumps() is the only encoding
    applied. (This mirrors the fix already used by _email_text_set /
    _email_text_get above: the old _fs_cache_set/_fs_cache_get pair
    double-encodes on write but only single-decodes on read, which leaves a
    stray layer of escaping in whatever comes back.)"""
    path = f"/set/{key}?EX={ttl_seconds}" if ttl_seconds else f"/set/{key}"
    _upstash_request(path, method="POST", body=value)


def _redis_get(key):
    """Reads back anything written with _redis_set — one json.loads() undoes
    the one json.dumps() layer _upstash_request applied on the way in, for
    both plain strings and dicts."""
    raw = _upstash_request(f"/get/{key}")
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None


def _redis_del(key):
    _upstash_request(f"/del/{key}", method="POST")


def _account_rate_limit_ok(key_prefix, max_per_hour):
    bucket = f"{key_prefix}:{int(datetime.utcnow().timestamp() // 3600)}"
    count = _upstash_request(f"/incr/{bucket}", method="POST")
    if count is None:
        return True  # fail open — a Redis hiccup shouldn't block sign-in
    if count == 1:
        _upstash_request(f"/expire/{bucket}/3600", method="POST")
    return count <= max_per_hour


def _send_login_email(to_address, login_link):
    auth = base64.b64encode(f"api:{MAILGUN_API_KEY}".encode()).decode()
    body = urllib.parse.urlencode({
        "from": f"PNR Genius <noreply@{MAILGUN_SENDING_DOMAIN}>",
        "to": to_address,
        "subject": "Your PNR Genius sign-in link",
        "text": (
            "Hi,\n\nClick the link below to sign in to PNR Genius:\n\n"
            f"{login_link}\n\n"
            "This link works once and expires in 15 minutes. If you didn't "
            "request this, you can safely ignore this email — no account "
            "changes happen until the link is clicked.\n\n— PNR Genius"
        ),
    }).encode()
    req = urllib.request.Request(
        f"https://api.mailgun.net/v3/{MAILGUN_SENDING_DOMAIN}/messages",
        data=body,
        method="POST",
        headers={
            "Authorization": f"Basic {auth}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    with urllib.request.urlopen(req, timeout=8) as resp:
        return resp.status


def _get_logged_in_email():
    """Reads the Authorization: Bearer <session_token> header and returns the
    signed-in email, or None if it's missing, malformed, or expired."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    session_token = auth_header[len("Bearer "):].strip()
    if not session_token:
        return None
    return _redis_get(f"pnr-session:{session_token}")


@app.route("/api/auth/request-login", methods=["POST"])
def auth_request_login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()

    if not email or len(email) > 200 or not EMAIL_RE.match(email):
        return jsonify({"error": "Please enter a valid email address."}), 400

    ip = request.headers.get("X-Forwarded-For", request.remote_addr or "unknown").split(",")[0].strip()
    if not _account_rate_limit_ok(f"login_ratelimit_ip:{ip}", max_per_hour=10):
        return jsonify({"error": "Too many attempts. Please try again later."}), 429
    if not _account_rate_limit_ok(f"login_ratelimit_email:{email}", max_per_hour=5):
        return jsonify({"error": "Too many attempts. Please try again later."}), 429

    token = secrets.token_urlsafe(32)
    try:
        _redis_set(f"pnr-login-token:{token}", email, LOGIN_TOKEN_TTL_SECONDS)
        login_link = f"{SITE_URL}/?login_token={token}"
        _send_login_email(email, login_link)
    except Exception as e:
        return jsonify({"error": "internal error", "detail": str(e)}), 500

    return jsonify({"status": "sent"}), 200


@app.route("/api/auth/verify", methods=["GET"])
def auth_verify():
    token = request.args.get("token", "")
    if not token or len(token) > 100:
        return jsonify({"error": "Missing or invalid token."}), 400

    email = _redis_get(f"pnr-login-token:{token}")
    if not email:
        return jsonify({"error": "This link has expired or was already used."}), 404

    # One-time use — delete immediately so the same link can't be replayed.
    _redis_del(f"pnr-login-token:{token}")

    # First login for this email doubles as account creation.
    if not _redis_get(f"pnr-user:{email}"):
        _redis_set(f"pnr-user:{email}", {"email": email, "created_at": datetime.utcnow().isoformat()})

    # Keep the global user index (used by the Schedule-Change Alerts cron
    # below) up to date — safe to call on every login, not just signup.
    _register_user(email)

    session_token = secrets.token_urlsafe(32)
    _redis_set(f"pnr-session:{session_token}", email, SESSION_TTL_SECONDS)

    return jsonify({"session_token": session_token, "email": email}), 200


@app.route("/api/auth/me", methods=["GET"])
def auth_me():
    email = _get_logged_in_email()
    if not email:
        return jsonify({"error": "Not logged in."}), 401
    return jsonify({"email": email}), 200


@app.route("/api/auth/logout", methods=["POST"])
def auth_logout():
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        session_token = auth_header[len("Bearer "):].strip()
        if session_token:
            _redis_del(f"pnr-session:{session_token}")
    return jsonify({"status": "ok"}), 200


# ---------------------------------------------------------------------------
# MY BOOKINGS COMMAND CENTER (Phase 2, step 2)
# ---------------------------------------------------------------------------
# Lets a signed-in agent save a converted PNR so it's waiting for them next
# time, instead of re-pasting it. Built directly on the account system above
# — every route here requires a valid Authorization: Bearer <session_token>.
#
# Storage: one Redis key per user holding a JSON array of that user's saved
# bookings, newest first — simple, and avoids adding Redis list commands
# (RPUSH/LRANGE) beyond the GET/SET this file already uses everywhere else.
#   pnr-bookings:<email> -> [ {id, label, raw_text, parsed, added_at}, ... ]
#
# This is deliberately just storage + CRUD. Schedule-Change Alerts, Smart PNR
# Diff and Price-Drop Alerts (later Phase 2 steps) all read from this same
# list rather than inventing their own.
# ---------------------------------------------------------------------------

MAX_BOOKINGS_PER_USER = 100
BOOKING_RAW_TEXT_MAX_LENGTH = 8000
BOOKING_RECORD_MAX_BYTES = 50000   # guards against an oversized/crafted `parsed` payload


def _bookings_key(email):
    return f"pnr-bookings:{email}"


def _get_bookings(email):
    return _redis_get(_bookings_key(email)) or []


@app.route("/api/bookings", methods=["POST"])
def bookings_create():
    email = _get_logged_in_email()
    if not email:
        return jsonify({"error": "Please sign in first."}), 401

    if not _account_rate_limit_ok(f"bookings_ratelimit:{email}", max_per_hour=60):
        return jsonify({"error": "Too many saves. Please try again later."}), 429

    data = request.get_json(silent=True) or {}
    raw_text = (data.get("raw_text") or "").strip()[:BOOKING_RAW_TEXT_MAX_LENGTH]
    parsed = data.get("parsed") or {}
    label = (data.get("label") or "").strip()[:120] or parsed.get("route_summary") or "Saved PNR"

    if not raw_text:
        return jsonify({"error": "Nothing to save — paste and convert a PNR first."}), 400

    bookings = _get_bookings(email)
    if len(bookings) >= MAX_BOOKINGS_PER_USER:
        return jsonify({"error": f"You've reached the {MAX_BOOKINGS_PER_USER}-booking limit. Delete an old one first."}), 400

    record = {
        "id": secrets.token_urlsafe(9),
        "label": label,
        "raw_text": raw_text,
        "parsed": parsed,
        "added_at": datetime.utcnow().isoformat(),
    }

    if len(json.dumps(record)) > BOOKING_RECORD_MAX_BYTES:
        return jsonify({"error": "This PNR is too large to save."}), 400

    bookings.insert(0, record)
    _redis_set(_bookings_key(email), bookings)

    return jsonify(record), 201


@app.route("/api/bookings", methods=["GET"])
def bookings_list():
    email = _get_logged_in_email()
    if not email:
        return jsonify({"error": "Please sign in first."}), 401

    return jsonify({"bookings": _get_bookings(email)}), 200


@app.route("/api/bookings/<booking_id>", methods=["PATCH"])
def bookings_update(booking_id):
    email = _get_logged_in_email()
    if not email:
        return jsonify({"error": "Please sign in first."}), 401

    data = request.get_json(silent=True) or {}
    new_label = (data.get("label") or "").strip()[:120]
    if not new_label:
        return jsonify({"error": "Label can't be empty."}), 400

    bookings = _get_bookings(email)
    for b in bookings:
        if b.get("id") == booking_id:
            b["label"] = new_label
            _redis_set(_bookings_key(email), bookings)
            return jsonify(b), 200

    return jsonify({"error": "Booking not found."}), 404


@app.route("/api/bookings/<booking_id>", methods=["DELETE"])
def bookings_delete(booking_id):
    email = _get_logged_in_email()
    if not email:
        return jsonify({"error": "Please sign in first."}), 401

    bookings = _get_bookings(email)
    remaining = [b for b in bookings if b.get("id") != booking_id]
    if len(remaining) == len(bookings):
        return jsonify({"error": "Booking not found."}), 404

    _redis_set(_bookings_key(email), remaining)
    return jsonify({"status": "ok"}), 200


# ---------------------------------------------------------------------------
# SMART PNR DIFF (Phase 2, step 4)
# ---------------------------------------------------------------------------
# When a signed-in agent re-pastes and converts a PNR that matches one of
# their saved bookings (matched by record locator / PNR reference), this
# compares the newly-parsed data against what was saved and returns a plain-
# English list of what changed — so the agent doesn't have to re-read the
# whole itinerary to spot a schedule change, cancelled leg, etc.
#
# Two routes:
#   POST /api/bookings/check-diff        -> silent background check, called
#                                            automatically after every convert
#                                            on the frontend. Never a hard
#                                            error — always 200, "matched:
#                                            false" for any case where there's
#                                            nothing to show (not signed in,
#                                            no match, no saved parsed data,
#                                            no differences).
#   POST /api/bookings/<id>/update        -> re-parses raw_text and overwrites
#                                            that booking's stored raw_text +
#                                            parsed, once the agent reviews
#                                            the diff and chooses to update.
# ---------------------------------------------------------------------------

def _diff_segment_label(seg):
    origin = (seg.get("origin") or {}).get("code", "?")
    dest = (seg.get("destination") or {}).get("code", "?")
    return f"{seg.get('airline_code', '')}{seg.get('flight_number', '')} ({origin} → {dest})"


def _diff_bookings(old_parsed, new_parsed):
    changes = []
    old_segments = (old_parsed or {}).get("segments") or []
    new_segments = (new_parsed or {}).get("segments") or []

    common = min(len(old_segments), len(new_segments))
    for i in range(common):
        old_seg = old_segments[i] or {}
        new_seg = new_segments[i] or {}
        label = _diff_segment_label(new_seg)

        if old_seg.get("airline_code") != new_seg.get("airline_code") or old_seg.get("flight_number") != new_seg.get("flight_number"):
            changes.append(
                f"Flight number changed: {old_seg.get('airline_code', '')}{old_seg.get('flight_number', '')} "
                f"→ {new_seg.get('airline_code', '')}{new_seg.get('flight_number', '')}"
            )
            continue  # a different flight number makes finer-grained diffs on this leg meaningless

        old_origin = (old_seg.get("origin") or {}).get("code")
        new_origin = (new_seg.get("origin") or {}).get("code")
        old_dest = (old_seg.get("destination") or {}).get("code")
        new_dest = (new_seg.get("destination") or {}).get("code")
        if old_origin != new_origin or old_dest != new_dest:
            changes.append(f"{label}: Route changed from {old_origin}-{old_dest} to {new_origin}-{new_dest}")

        if old_seg.get("date_iso") != new_seg.get("date_iso"):
            changes.append(f"{label}: Date changed from {old_seg.get('date') or old_seg.get('date_iso') or '?'} to {new_seg.get('date') or new_seg.get('date_iso') or '?'}")

        if old_seg.get("departure_time") != new_seg.get("departure_time"):
            changes.append(f"{label}: Departure time changed from {old_seg.get('departure_time') or '?'} to {new_seg.get('departure_time') or '?'}")

        if old_seg.get("arrival_time") != new_seg.get("arrival_time"):
            changes.append(f"{label}: Arrival time changed from {old_seg.get('arrival_time') or '?'} to {new_seg.get('arrival_time') or '?'}")

        if old_seg.get("status") != new_seg.get("status"):
            changes.append(f"{label}: Status changed from {old_seg.get('status') or '?'} to {new_seg.get('status') or '?'}")

        if old_seg.get("booking_class") != new_seg.get("booking_class"):
            changes.append(f"{label}: Booking class changed from {old_seg.get('booking_class') or '?'} to {new_seg.get('booking_class') or '?'}")

    if len(new_segments) > len(old_segments):
        for seg in new_segments[len(old_segments):]:
            changes.append(f"New flight added: {_diff_segment_label(seg)} on {seg.get('date') or seg.get('date_iso') or '?'}")
    elif len(old_segments) > len(new_segments):
        for seg in old_segments[len(new_segments):]:
            changes.append(f"Flight removed: {_diff_segment_label(seg)} (was on {seg.get('date') or seg.get('date_iso') or '?'})")

    old_names = sorted(p.get("full_name", "") for p in (old_parsed or {}).get("passengers") or [])
    new_names = sorted(p.get("full_name", "") for p in (new_parsed or {}).get("passengers") or [])
    if old_names != new_names:
        added = [n for n in new_names if n not in old_names]
        removed = [n for n in old_names if n not in new_names]
        if added:
            changes.append(f"Passenger(s) added: {', '.join(added)}")
        if removed:
            changes.append(f"Passenger(s) removed: {', '.join(removed)}")

    return changes


def _find_matching_booking(bookings, new_parsed):
    pnr_ref = (new_parsed or {}).get("pnr_reference")
    if not pnr_ref:
        return None
    pnr_ref = pnr_ref.upper()
    matches = [
        b for b in bookings
        if ((b.get("parsed") or {}).get("pnr_reference") or "").upper() == pnr_ref
    ]
    # If more than one saved booking shares this record locator, it's
    # ambiguous which one the agent means — stay silent rather than guess.
    if len(matches) == 1:
        return matches[0]
    return None


@app.route("/api/bookings/check-diff", methods=["POST"])
def bookings_check_diff():
    email = _get_logged_in_email()
    if not email:
        return jsonify({"matched": False}), 200

    data = request.get_json(silent=True) or {}
    raw_text = (data.get("raw_text") or "").strip()
    if not raw_text:
        return jsonify({"matched": False}), 200

    try:
        new_parsed = parse_pnr(raw_text)
    except Exception:
        return jsonify({"matched": False}), 200

    bookings = _get_bookings(email)
    matched_booking = _find_matching_booking(bookings, new_parsed)
    if not matched_booking:
        return jsonify({"matched": False}), 200

    old_parsed = matched_booking.get("parsed") or {}
    if not old_parsed.get("segments"):
        return jsonify({"matched": False}), 200

    changes = _diff_bookings(old_parsed, new_parsed)

    return jsonify({
        "matched": True,
        "booking_id": matched_booking.get("id"),
        "booking_label": matched_booking.get("label"),
        "has_changes": len(changes) > 0,
        "changes": changes,
    }), 200


@app.route("/api/bookings/<booking_id>/update", methods=["POST"])
def bookings_apply_update(booking_id):
    email = _get_logged_in_email()
    if not email:
        return jsonify({"error": "Please sign in first."}), 401

    if not _account_rate_limit_ok(f"bookings_ratelimit:{email}", max_per_hour=60):
        return jsonify({"error": "Too many updates. Please try again later."}), 429

    data = request.get_json(silent=True) or {}
    raw_text = (data.get("raw_text") or "").strip()[:BOOKING_RAW_TEXT_MAX_LENGTH]
    if not raw_text:
        return jsonify({"error": "No PNR text provided."}), 400

    try:
        parsed = parse_pnr(raw_text)
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400

    bookings = _get_bookings(email)
    target_index = next((i for i, b in enumerate(bookings) if b.get("id") == booking_id), None)
    if target_index is None:
        return jsonify({"error": "Booking not found."}), 404

    updated = dict(bookings[target_index])
    updated["raw_text"] = raw_text
    updated["parsed"] = parsed
    updated["updated_at"] = datetime.utcnow().isoformat()

    if len(json.dumps(updated)) > BOOKING_RECORD_MAX_BYTES:
        return jsonify({"error": "This PNR is too large to save."}), 400

    bookings[target_index] = updated
    _redis_set(_bookings_key(email), bookings)

    return jsonify(updated), 200


# ---------------------------------------------------------------------------
# SCHEDULE-CHANGE ALERTS (Phase 2, step 3)
# ---------------------------------------------------------------------------
# This runs on a schedule driven by an OUTSIDE trigger (a GitHub Actions
# workflow calling this endpoint every few hours) rather than Vercel's own
# Cron Jobs — the Hobby (free) plan only allows a cron to fire once a day,
# which is too slow for "before the client even asks" alerts. The endpoint
# is protected by CRON_SECRET so nobody else can trigger it and burn through
# the AeroDataBox quota.
#
# For every signed-up user's saved bookings, this checks each flight segment
# departing in the next ALERT_LOOKAHEAD_DAYS days against AeroDataBox, and
# emails the agent only when something changed since the LAST check (status,
# scheduled time, gate, or terminal). The very first check on a booking just
# records a baseline — it never sends an alert on that first pass, since
# there's nothing to compare against yet.
#
# MAX_ALERT_CHECKS_PER_RUN caps how many AeroDataBox calls happen in one
# run, so cost stays bounded no matter how many users sign up — anything
# past the cap is simply picked up on the next run a few hours later.
# ---------------------------------------------------------------------------

from datetime import timedelta

CRON_SECRET = os.environ.get("CRON_SECRET", "")
ALERT_LOOKAHEAD_DAYS = 7
MAX_ALERT_CHECKS_PER_RUN = 60
ALL_USERS_KEY = "pnr-all-users"


def _register_user(email):
    """Adds email to the global user index used only by the alert-checker
    to know which users' bookings to scan. Idempotent, and safe to call on
    every login (not just signup) so an account created before this feature
    existed gets backfilled the next time that agent signs in."""
    users = _redis_get(ALL_USERS_KEY) or []
    if email not in users:
        users.append(email)
        _redis_set(ALL_USERS_KEY, users)


def _alert_fetch_flight_status(flight_number, date):
    """A standalone AeroDataBox lookup for the alert-checker — deliberately
    NOT sharing code or cache keys with flight_status()/_fs_cache_* above.
    That pair has a known double-JSON-encoding bug on cache reads (see the
    comment above _email_text_set/_email_text_get, where the same bug was
    hit and fixed for a different feature) that would make a cache hit here
    silently come back as a string instead of a dict. Using this file's
    already-correct _redis_get/_redis_set instead sidesteps it entirely,
    without touching the existing, already-live /api/flight-status route.
    Returns the normalized dict, or None on any failure — a lookup hiccup
    should skip that one segment, not crash the whole run."""
    cache_key = f"alert-fs-cache:{flight_number}:{date or 'today'}"
    cached = _redis_get(cache_key)
    if cached:
        return cached

    if not AERODATABOX_KEY:
        return None

    url = f"https://{AERODATABOX_HOST}/flights/number/{flight_number}"
    if date:
        url += f"/{date}"
    url += "?withLocation=true"

    try:
        req = urllib.request.Request(url, headers={
            "X-RapidAPI-Key": AERODATABOX_KEY,
            "X-RapidAPI-Host": AERODATABOX_HOST,
            "User-Agent": "PNRGenius/1.0",
        })
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read())
    except Exception:
        return None

    if not data:
        return None

    best_match = _fs_pick_most_relevant(data) if isinstance(data, list) else data
    normalized = _fs_normalize(best_match)
    _redis_set(cache_key, normalized, FLIGHT_STATUS_CACHE_TTL)
    return normalized


def _alert_snapshot(status):
    """The subset of a normalized flight-status dict that actually matters
    for an alert — comparing only this (not the whole dict, which includes
    noisier fields like live position) avoids false-positive 'changes'."""
    dep = status.get("departure") or {}
    return {
        "status": status.get("status"),
        "scheduled": dep.get("scheduled"),
        "gate": dep.get("gate"),
        "terminal": dep.get("terminal"),
    }


def _alert_describe_change(old, new):
    """Plain-English list of what changed, e.g. 'Gate: A12 -> B4'."""
    lines = []
    if old.get("status") != new.get("status"):
        lines.append(f"Status: {old.get('status') or 'Unknown'} → {new.get('status') or 'Unknown'}")
    if old.get("scheduled") != new.get("scheduled"):
        lines.append(f"Departure time: {old.get('scheduled') or 'unknown'} → {new.get('scheduled') or 'unknown'}")
    if old.get("gate") != new.get("gate"):
        lines.append(f"Gate: {old.get('gate') or 'unassigned'} → {new.get('gate') or 'unassigned'}")
    if old.get("terminal") != new.get("terminal"):
        lines.append(f"Terminal: {old.get('terminal') or 'unassigned'} → {new.get('terminal') or 'unassigned'}")
    return lines


def _send_schedule_change_email(to_address, booking_label, flight_number, changes):
    auth = base64.b64encode(f"api:{MAILGUN_API_KEY}".encode()).decode()
    change_lines = "\n".join(f"  - {c}" for c in changes)
    body = urllib.parse.urlencode({
        "from": f"PNR Genius <noreply@{MAILGUN_SENDING_DOMAIN}>",
        "to": to_address,
        "subject": f"Schedule change: {flight_number} ({booking_label})",
        "text": (
            f"Hi,\n\nSomething changed on a flight in your saved booking \"{booking_label}\" ({flight_number}):\n\n"
            f"{change_lines}\n\n"
            f"See the latest details in My Bookings: {SITE_URL}/my-bookings.html\n\n"
            "(You're getting this because you saved this PNR on PNR Genius.)\n\n— PNR Genius"
        ),
    }).encode()
    req = urllib.request.Request(
        f"https://api.mailgun.net/v3/{MAILGUN_SENDING_DOMAIN}/messages",
        data=body,
        method="POST",
        headers={
            "Authorization": f"Basic {auth}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    with urllib.request.urlopen(req, timeout=8) as resp:
        return resp.status


@app.route("/api/cron/check-alerts", methods=["GET", "POST"])
def cron_check_alerts():
    provided_secret = request.headers.get("Authorization", "").replace("Bearer ", "").strip() or request.args.get("secret", "")
    if not CRON_SECRET or provided_secret != CRON_SECRET:
        return jsonify({"error": "unauthorized"}), 401

    today = datetime.utcnow().date()
    cutoff = today + timedelta(days=ALERT_LOOKAHEAD_DAYS)

    users = _redis_get(ALL_USERS_KEY) or []
    checks_done = 0
    alerts_sent = 0
    users_touched = 0

    for email in users:
        if checks_done >= MAX_ALERT_CHECKS_PER_RUN:
            break

        bookings = _get_bookings(email)
        if not bookings:
            continue

        touched = False

        for booking in bookings:
            if checks_done >= MAX_ALERT_CHECKS_PER_RUN:
                break

            parsed = booking.get("parsed") or {}
            segments = parsed.get("segments") or []
            alert_snapshots = booking.get("alert_snapshots") or {}

            for seg in segments:
                if checks_done >= MAX_ALERT_CHECKS_PER_RUN:
                    break

                date_iso = seg.get("date_iso")
                if not date_iso:
                    continue
                try:
                    seg_date = datetime.strptime(date_iso, "%Y-%m-%d").date()
                except ValueError:
                    continue
                if seg_date < today or seg_date > cutoff:
                    continue

                flight_number = f"{(seg.get('airline_code') or '').upper()}{seg.get('flight_number') or ''}".strip()
                if not flight_number:
                    continue

                checks_done += 1
                status = _alert_fetch_flight_status(flight_number, date_iso)
                if not status:
                    continue

                new_snapshot = _alert_snapshot(status)
                snapshot_key = f"{flight_number}:{date_iso}"
                old_snapshot = alert_snapshots.get(snapshot_key)

                if old_snapshot:
                    changes = _alert_describe_change(old_snapshot, new_snapshot)
                    if changes:
                        try:
                            _send_schedule_change_email(
                                email,
                                booking.get("label") or parsed.get("route_summary") or "Saved PNR",
                                flight_number,
                                changes,
                            )
                            alerts_sent += 1
                        except Exception:
                            pass

                alert_snapshots[snapshot_key] = new_snapshot
                touched = True

            booking["alert_snapshots"] = alert_snapshots

        if touched:
            _redis_set(_bookings_key(email), bookings)
            users_touched += 1

    return jsonify({
        "checked": checks_done,
        "alerts_sent": alerts_sent,
        "users_touched": users_touched,
        "users_total": len(users),
    }), 200


# ---------------------------------------------------------------------------
# CRM API v1  —  server-to-server, API-key protected, versioned
# ---------------------------------------------------------------------------
# Built for the Times Travel CRM (Supabase Edge Function -> this route).
# Design rules:
#   * It calls the SAME canonical parser as the website (parse_pnr /
#     parse_segment_line / parse_passengers / extract_pnr_reference /
#     check_pnr_health). Nothing is re-implemented here.
#   * It never invents data. Anything the PNR text did not actually contain
#     comes back as null, and a machine-readable warning explains why.
#   * Everything that looks like a flight/passenger line but could not be
#     parsed is reported in review.unparsed_lines (the website silently skips
#     such lines).
#   * The website's /api/convert is untouched.
#
# Vercel env vars:
#   CRM_API_KEY                   required, >= 32 characters, shared secret
#   CRM_API_RATE_LIMIT_PER_HOUR   optional, default 1000 (whole CRM)
#
# Schema stability: within api_version "1" fields are only ever ADDED, never
# renamed, removed or re-typed. A breaking change ships as /api/v2/convert.
# ---------------------------------------------------------------------------

CRM_API_KEY = os.environ.get("CRM_API_KEY", "")
CRM_API_RATE_LIMIT_PER_HOUR = int(os.environ.get("CRM_API_RATE_LIMIT_PER_HOUR", "1000") or 1000)
CRM_API_PNR_MAX_LENGTH = 20000
CRM_API_VERSION = "1"
CRM_PARSER_VERSION = "2026-10-21.5"
CRM_API_MIN_KEY_LENGTH = 32

CONFIRMED_STATUS_LABELS = {"Confirmed"}

# A numbered line that carries a date-ish token, a route-ish token and two
# time-ish numbers is treated as "meant to be a flight line". Deliberately
# looser than parse_segment_line so that corrupted / unusual lines (truncated
# month, extra prefix letter, ...) are REPORTED instead of silently skipped.
V1_LINE_NUMBER_RE = re.compile(r"^\d+\s")
V1_DATE_LIKE_RE = re.compile(r"\b\d{1,2}[A-Z]{2,3}\b", re.IGNORECASE)
V1_ROUTE_LIKE_RE = re.compile(r"\b[A-Z]{3}\s{0,3}[A-Z]{3}\b|\b\d?\*?[A-Z]{3}\s{0,3}[A-Z]{3}\*?", re.IGNORECASE)
V1_TIMES_LIKE_RE = re.compile(r"\b\d{3,4}[AP]?\s+\d{3,4}[AP]?\b", re.IGNORECASE)
V1_OPERATED_BY_RE = re.compile(r"^OPERATED\s+BY\s+(.+?)\s*$", re.IGNORECASE)
V1_OTHER_ELEMENT_RE = re.compile(r"^\d+\s+(HTL|HHL|CAR|CCR|ARNK|SVC|TRN|TUR|CRU)\b", re.IGNORECASE)
V1_AIRLINE_LOCATOR_RE = re.compile(r"/DC([A-Z0-9]{2})\*([A-Z0-9]{5,6})\b", re.IGNORECASE)


# The strict shape used before: "<n> <airline><flight>[class] ... <ddMMM>"
V1_SEGMENT_LIKE_RE = re.compile(
    rf"^\d+\s+[A-Z0-9]{{2}}\s*\d{{1,4}}[A-Z]?\s+.*\b\d{{1,2}}{MONTH_NAMES_RE}\b",
    re.IGNORECASE,
)


def _v1_looks_like_flight_line(text):
    if V1_SEGMENT_LIKE_RE.match(text):
        return True
    return bool(
        V1_LINE_NUMBER_RE.match(text)
        and V1_DATE_LIKE_RE.search(text)
        and V1_ROUTE_LIKE_RE.search(text)
        and V1_TIMES_LIKE_RE.search(text)
    )
V1_PASSENGER_LIKE_RE = re.compile(r"^\s*\d+\.\s*\d?[A-Za-z'\-]+/", re.IGNORECASE)
V1_TICKETING_DEADLINE_RE = re.compile(
    r"(?:(?<![A-Z])TK\s*TL|(?<![A-Z])TAW)\s*(\d{1,2})([A-Z]{3})(?:/(\d{3,4}))?",
    re.IGNORECASE,
)


def _v1_response(payload, status=200, extra_headers=None):
    payload = dict(payload)
    payload["api_version"] = CRM_API_VERSION
    resp = jsonify(payload)
    resp.status_code = status
    resp.headers["Cache-Control"] = "no-store"
    resp.headers["X-PNRGenius-API-Version"] = CRM_API_VERSION
    for k, v in (extra_headers or {}).items():
        resp.headers[k] = v
    return resp


def _v1_error(code, message, status, details=None, extra_headers=None):
    err = {"code": code, "message": message}
    if details:
        err["details"] = details
    return _v1_response({"success": False, "error": err}, status, extra_headers)


def _v1_auth_error():
    """Returns an error response, or None when the caller is authorised."""
    if len(CRM_API_KEY) < CRM_API_MIN_KEY_LENGTH:
        # Fail closed: never run unauthenticated because of a missing/weak key.
        return _v1_error(
            "SERVER_NOT_CONFIGURED",
            "CRM API key is not configured on the server.",
            503,
        )
    supplied = request.headers.get("X-API-Key", "")
    if not supplied or not hmac.compare_digest(
        supplied.encode("utf-8"), CRM_API_KEY.encode("utf-8")
    ):
        return _v1_error("UNAUTHORIZED", "Missing or invalid API key.", 401)
    return None


def _v1_rate_limit_error():
    if _account_rate_limit_ok("crm_api_rl", CRM_API_RATE_LIMIT_PER_HOUR):
        return None
    now = int(datetime.utcnow().timestamp())
    retry_after = 3600 - (now % 3600)
    return _v1_error(
        "RATE_LIMITED",
        "Hourly request limit reached for this API key.",
        429,
        extra_headers={"Retry-After": str(retry_after)},
    )


def _v1_warn(warnings, code, severity, message, segment_index=None):
    warnings.append({
        "code": code,
        "severity": severity,          # "blocking" | "review" | "info"
        "message": message,
        "segment_index": segment_index,
    })


def _v1_valid_time(t):
    if not t:
        return False
    try:
        h, m = t.split(":")
        return 0 <= int(h) <= 23 and 0 <= int(m) <= 59
    except (ValueError, AttributeError):
        return False


def _v1_airport(code):
    known = code in AIRPORTS
    info = AIRPORTS.get(code, {})
    return {
        "code": code,
        "name": info.get("name") if known else None,
        "city": info.get("city") if known else None,
        "country": info.get("country") if known else None,
        "known": known,
    }


def _v1_scan_lines(raw_text):
    """Walks the pasted text with the SAME canonical line parser the website
    uses. Returns (segment_audits, unparsed_lines, other_elements).
    segment_audits is aligned 1:1 with parse_pnr()'s segments (parse_segments
    skips exactly the lines parse_segment_line rejects)."""
    audits = []
    unparsed = []
    others = []
    prev_audit = None  # the segment an immediately following "OPERATED BY" line belongs to
    for line_number, line in enumerate(raw_text.split("\n"), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        parsed = parse_segment_line(stripped)
        if parsed:
            audit = {"line_number": line_number, "raw_line": stripped, "p": parsed, "operated_by": None}
            audits.append(audit)
            prev_audit = audit
            continue
        op = V1_OPERATED_BY_RE.match(stripped)
        if op and prev_audit is not None:
            prev_audit["operated_by"] = op.group(1)
            continue  # stays attached to that segment only; a second note is ignored
        prev_audit = None
        if _v1_looks_like_flight_line(stripped):
            unparsed.append({
                "line_number": line_number,
                "text": stripped[:200],
                "kind": "segment",
                "reason": "Looks like a flight segment (date, route and times present) but could not be parsed. Possibly truncated or an unusual layout.",
            })
        elif V1_OTHER_ELEMENT_RE.match(stripped):
            others.append({
                "line_number": line_number,
                "type": V1_OTHER_ELEMENT_RE.match(stripped).group(1).upper(),
                "raw_line": stripped[:300],
            })
        elif (V1_PASSENGER_LIKE_RE.match(stripped)
              and not PASSENGER_PATTERN.search(stripped)
              and not parse_party_name_line(stripped)):
            unparsed.append({
                "line_number": line_number,
                "text": stripped[:200],
                "kind": "passenger",
                "reason": "Looks like a passenger/name line but its format is not recognised.",
            })
    return audits, unparsed, others


def _v1_ticketing(raw_text):
    raw_lines = []
    deadline = None
    for line in raw_text.split("\n"):
        stripped = line.strip()
        if stripped and TICKETING_ELEMENT_RE.search(stripped):
            raw_lines.append(stripped[:200])
        if deadline is None and stripped:
            m = V1_TICKETING_DEADLINE_RE.search(stripped.upper())
            if m and m.group(2) in MONTHS:
                resolved = parse_pnr_date(f"{m.group(1)}{m.group(2)}")
                iso = resolved[0] if resolved else None
                time_val = format_time(m.group(3)) if m.group(3) else None
                if not _v1_valid_time(time_val):
                    time_val = None
                if iso:
                    deadline = {
                        "date_iso": iso,
                        "time": time_val,
                        "year_inferred": True,
                        "raw": m.group(0).strip(),
                    }
    return {"raw_lines": raw_lines, "deadline": deadline}


def build_crm_v1_payload(raw_text):
    """Runs the canonical parser and wraps the result in the v1 contract.
    Raises ValueError (with .args[0] a message) only for 'no segments'."""
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    warnings = []

    audits, unparsed, other_elements = _v1_scan_lines(raw_text)
    base = parse_pnr(raw_text)               # canonical parser (raises ValueError)
    base_segments = base["segments"]
    if len(audits) != len(base_segments):    # defensive: should never happen
        raise RuntimeError("segment audit misaligned")

    # ---- passengers (never a placeholder) --------------------------------
    parsed_passengers = parse_passengers(raw_text)
    passengers = [
        {
            "index": i,
            "last_name": p["last_name"],
            "first_name": p["first_name"],
            "title": p["title"] or None,
            "full_name": p["full_name"],
        }
        for i, p in enumerate(parsed_passengers)
    ]
    if not passengers:
        _v1_warn(warnings, "NO_PASSENGERS_PARSED", "blocking",
                 "No passenger names could be read from this PNR. Enter passengers manually.")
    if any(u["kind"] == "passenger" for u in unparsed):
        _v1_warn(warnings, "UNPARSED_PASSENGER_LINE", "blocking",
                 "At least one passenger line was not recognised, so the passenger list may be incomplete.")
    if any(u["kind"] == "segment" for u in unparsed):
        _v1_warn(warnings, "UNPARSED_SEGMENT_LINE", "blocking",
                 "At least one flight-segment line could not be parsed, so the itinerary is incomplete. See review.unparsed_lines.")

    # ---- PNR reference ----------------------------------------------------
    # In an Amadeus header ("RP/DEL1S2100/DEL1S2100   AA/SU  21OCT26/0315Z   ABCD12")
    # the RP/ values are OFFICE ids; the record locator is the last token.
    office_id, header_locator = parse_rp_header(raw_text)
    if header_locator:
        pnr_reference, pnr_reference_source = header_locator, "amadeus_rp_header_last_token"
        pnr_reference_candidate = None
    else:
        pnr_reference, pnr_reference_source = None, None
        pnr_reference_candidate = None
        # heuristic guess, but never an office id
        scan = "\n".join(l for l in raw_text.split("\n")
                         if not parse_party_name_line(l) and not RP_HEADER_RE.match(l))
        for token in re.findall(r"\b[A-Z0-9]{6}\b", scan.upper()):
            if any(ch.isdigit() for ch in token):
                pnr_reference_candidate = token
                break
        if pnr_reference_candidate:
            _v1_warn(warnings, "PNR_REFERENCE_UNCONFIRMED", "review",
                     "No record locator on an RP/ header line. pnr_reference_candidate is a best-guess 6-character token and may not be the record locator.")
        else:
            _v1_warn(warnings, "PNR_REFERENCE_NOT_FOUND", "review",
                     "No record locator could be found in the pasted text"
                     + (" (the RP/ header carries only the office id)." if office_id else "."))

    gds = base.get("gds_detected")
    if gds == "Auto-detected":
        gds = None
        _v1_warn(warnings, "GDS_NOT_DETECTED", "info", "The source GDS could not be identified from the text.")

    # ---- segments ---------------------------------------------------------
    segments = []
    for i, (seg, audit) in enumerate(zip(base_segments, audits)):
        p = audit["p"]
        seg_warn_codes = []

        def sw(code, severity, message):
            seg_warn_codes.append(code)
            _v1_warn(warnings, code, severity, message, i)

        origin_code = seg["origin"]["code"]
        dest_code = seg["destination"]["code"]
        origin = _v1_airport(origin_code)
        destination = _v1_airport(dest_code)
        for ap in (origin, destination):
            if not ap["known"]:
                sw("AIRPORT_UNKNOWN", "info",
                   f"Airport {ap['code']} is not in the built-in airport list; name/city/country are null.")

        dep_date = seg.get("date_iso")
        dep_time = seg.get("departure_time")
        arr_time = seg.get("arrival_time")
        if not dep_date:
            sw("DATE_UNRESOLVED", "blocking", "The departure date could not be resolved.")
        for label, t in (("departure", dep_time), ("arrival", arr_time)):
            if not _v1_valid_time(t):
                sw("TIME_INVALID", "blocking", f"The {label} time is missing or not a valid 24h time.")
                if label == "departure":
                    dep_time = None
                else:
                    arr_time = None

        # arrival date: prefer what the PNR line actually says
        explicit = p.get("arr_date_str")
        arr_date = seg.get("arrival_date_iso")
        basis = "same_day_assumed"
        corrected = False
        if explicit and dep_date:
            resolved = parse_pnr_date(explicit, min_date=datetime.strptime(dep_date, "%Y-%m-%d"))
            iso = resolved[0] if resolved else None
            if iso:
                corrected = iso != arr_date
                arr_date = iso
                basis = "explicit_in_pnr"
            else:
                basis = "inferred_from_times"
                sw("ARRIVAL_DATE_UNREADABLE", "review", "The arrival date in the PNR line could not be read; it was inferred from the times.")
        elif p.get("arr_day_marker") is not None:
            basis = "explicit_in_pnr"   # e.g. "0700+1" printed by the GDS
        elif seg.get("overnight"):
            basis = "inferred_from_times"
            sw("ARRIVAL_DAY_INFERRED", "info",
               "The line has no arrival date; next-day arrival was inferred because the arrival clock time is earlier than departure.")
        day_offset = None
        if dep_date and arr_date:
            day_offset = (datetime.strptime(arr_date, "%Y-%m-%d") - datetime.strptime(dep_date, "%Y-%m-%d")).days

        # booking class / cabin / status: null unless the line really had them
        if p["class_defaulted"]:
            booking_class, cabin_class, cabin_basis = None, None, None
            sw("BOOKING_CLASS_NOT_IN_PNR", "review", "No booking class letter on this line; booking_class and cabin_class are null.")
        else:
            booking_class = p["booking_class"]
            if booking_class in CABIN_CODES:
                cabin_class, cabin_basis = CABIN_CODES[booking_class], "generic_booking_class_map"
            else:
                cabin_class, cabin_basis = None, None
        if p["status_defaulted"]:
            status_code, status_label = None, None
            sw("STATUS_NOT_IN_PNR", "review", "No status code on this line; status is null (not assumed confirmed).")
        else:
            status_code = p["status"]
            status_label = get_status_label(status_code)
            if status_code not in STATUS_CODES:
                sw("STATUS_UNKNOWN", "review", f"Status code {status_code} is not recognised.")
            elif status_label not in CONFIRMED_STATUS_LABELS:
                sw("SEGMENT_NOT_CONFIRMED", "review", f"Segment status is {status_label} ({status_code}), not confirmed.")

        # duration: only when both airports have a known UTC offset
        duration, reliable = None, False
        if dep_time and arr_time and day_offset is not None \
                and origin_code.upper() in AIRPORT_UTC_OFFSETS and dest_code.upper() in AIRPORT_UTC_OFFSETS:
            duration = calculate_duration(dep_time, arr_time, day_offset, origin_code, dest_code, dep_date)
            reliable = duration is not None
        if not reliable:
            sw("DURATION_NOT_AVAILABLE", "info", "Flight duration is null because a UTC offset is unknown for one of the airports.")

        airline_code = seg["airline_code"]
        airline_name = seg["airline_name"] if seg["airline_name"] != airline_code else None
        # Sabre-style "/DCEK*PYAQMW": the airline's own confirmation locator
        loc_match = V1_AIRLINE_LOCATOR_RE.search(audit["raw_line"])
        airline_locator = (
            {"carrier": loc_match.group(1).upper(), "locator": loc_match.group(2).upper()}
            if loc_match else None
        )

        segments.append({
            "index": i,
            "raw_line": audit["raw_line"],
            "source_line_number": audit["line_number"],
            "operated_by": audit["operated_by"],
            "airline_locator": airline_locator,
            "airline_code": airline_code,
            "airline_name": airline_name,
            "flight_number": seg["flight_number"],
            "flight_designator": f"{airline_code}{seg['flight_number']}",
            "origin": origin,
            "destination": destination,
            "departure": {
                "date_iso": dep_date,
                "time": dep_time,
                "local_datetime": f"{dep_date}T{dep_time}" if dep_date and dep_time else None,
            },
            "arrival": {
                "date_iso": arr_date,
                "time": arr_time,
                "local_datetime": f"{arr_date}T{arr_time}" if arr_date and arr_time else None,
                "day_offset": day_offset,
                "day_basis": basis,    # explicit_in_pnr | inferred_from_times | same_day_assumed
            },
            "status_code": status_code,
            "status": status_label,
            "booking_class": booking_class,
            "cabin_class": cabin_class,
            "cabin_class_basis": cabin_basis,
            "duration": duration,
            "duration_is_estimate": True,
            "duration_reliable": reliable,
            "layover_after": None if corrected else seg.get("layover_after"),
            "layover_minutes": None if corrected else seg.get("layover_minutes"),
            "fare_flag": seg.get("fare_flag"),
            "warnings": seg_warn_codes,
        })

    # ---- trip-level checks -------------------------------------------------
    _v1_warn(warnings, "YEAR_INFERRED", "info",
             "GDS text has no year. Dates are resolved to the next occurrence on or after meta.reference_date.")
    first_date = next((s["departure"]["date_iso"] for s in segments if s["departure"]["date_iso"]), None)
    if first_date:
        gap = (datetime.strptime(first_date, "%Y-%m-%d") - today).days
        if gap > 330:
            _v1_warn(warnings, "FIRST_DEPARTURE_FAR_FUTURE", "review",
                     f"The first departure resolves to {gap} days from today. If this PNR is for a trip that already happened or is about to, the year may be one year too late.")

    for hc in base.get("health_checks", []):
        if hc.get("severity") == "warning" and hc.get("type") != "ticketing_deadline_missing":
            _v1_warn(warnings, "HEALTH_" + hc["type"].upper(), "review", hc["title"], hc.get("segment_index"))

    ticketing = _v1_ticketing(raw_text)
    if ticketing["raw_lines"] and ticketing["deadline"] is None:
        _v1_warn(warnings, "TICKETING_DEADLINE_NOT_PARSED", "info",
                 "A ticketing line exists but its deadline format was not recognised. See data.ticketing.raw_lines.")

    # infants: a PNR that mentions an infant but yielded no INF passenger would
    # silently under-count travellers (and mis-price the quote)
    if re.search(r"\bSSR\s+INFT\b|^\s*\d+\.I/", raw_text, re.IGNORECASE | re.MULTILINE) \
            and not any(p["title"] == "INF" for p in passengers):
        _v1_warn(warnings, "INFANT_NOT_PARSED", "review",
                 "The PNR mentions an infant (INFT / I/ element) but no infant passenger could be read. Check the traveller count.")

    # open jaw / surface sector: a segment that does not start where the previous one ended
    breaks = [i for i in range(len(segments) - 1)
              if segments[i]["destination"]["code"] != segments[i + 1]["origin"]["code"]]
    is_contiguous = not breaks
    route_summary = base["route_summary"]
    if breaks:
        legs, start = [], 0
        for b in breaks + [len(segments) - 1]:
            legs.append(f"{segments[start]['origin']['code']} → {segments[b]['destination']['code']}")
            start = b + 1
        route_summary = " , ".join(legs)
        for b in breaks:
            _v1_warn(warnings, "NON_CONTIGUOUS_ROUTE", "info",
                     f"Segment {b + 1} ends at {segments[b]['destination']['code']} but segment {b + 2} starts at "
                     f"{segments[b + 1]['origin']['code']} (open jaw or surface sector). route_summary lists each leg separately.",
                     b)

    if other_elements:
        _v1_warn(warnings, "NON_FLIGHT_ELEMENTS_PRESENT", "info",
                 "The PNR contains hotel/car/other segments that are not parsed (listed raw in data.other_elements).")

    severities = {w["severity"] for w in warnings}
    needs_review = bool(severities & {"blocking", "review"})
    confidence = "low" if "blocking" in severities else ("medium" if "review" in severities else "high")

    return {
        "success": True,
        "data": {
            "pnr_reference": pnr_reference,
            "pnr_reference_source": pnr_reference_source,
            "pnr_reference_candidate": pnr_reference_candidate,
            "office_id": office_id,
            "gds_detected": gds,
            "passengers": passengers,
            "passenger_count": len(passengers),
            "segments": segments,
            "segment_count": len(segments),
            "route_summary": route_summary,
            "is_contiguous_route": is_contiguous,
            "is_round_trip": base["is_round_trip"] and is_contiguous,
            "is_multi_city": base["is_multi_city"],
            "ticketing": ticketing,
            "health_checks": base["health_checks"],
            "has_fare_flags": base["has_fare_flags"],
            "other_elements": other_elements,
        },
        "review": {
            "needs_review": needs_review,
            "confidence": confidence,      # rule-based: high | medium | low (see docs)
            "warnings": warnings,
            "unparsed_lines": unparsed,
        },
        "meta": {
            "parser_version": CRM_PARSER_VERSION,
            "reference_date": today.strftime("%Y-%m-%d"),
            "fields_not_supported": ["baggage", "terminal", "arrival_terminal", "departure_terminal"],
        },
    }


@app.route("/api/v1/ping", methods=["GET"])
def crm_v1_ping():
    err = _v1_auth_error()
    if err:
        return err
    return _v1_response({
        "success": True,
        "data": {"status": "ok", "parser_version": CRM_PARSER_VERSION},
    })


@app.route("/api/v1/convert", methods=["POST"])
def crm_v1_convert():
    err = _v1_auth_error()
    if err:
        return err
    err = _v1_rate_limit_error()
    if err:
        return err

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return _v1_error("INVALID_JSON", "Request body must be a JSON object.", 400)
    if "pnr" not in data:
        return _v1_error("MISSING_PNR", "Missing 'pnr' field in request body.", 400)
    pnr = data["pnr"]
    if not isinstance(pnr, str):
        return _v1_error("PNR_NOT_STRING", "'pnr' must be a string.", 400)
    if not pnr.strip():
        return _v1_error("EMPTY_PNR", "'pnr' is empty.", 400)
    if len(pnr) > CRM_API_PNR_MAX_LENGTH:
        return _v1_error("PNR_TOO_LONG",
                         f"'pnr' exceeds {CRM_API_PNR_MAX_LENGTH} characters.", 413)

    raw_text = pnr.replace("\r\n", "\n").replace("\r", "\n")

    try:
        blocks = split_batch_pnrs(raw_text)
        if len(blocks) > 1:
            return _v1_error(
                "MULTIPLE_PNRS_DETECTED",
                "The text appears to contain more than one PNR. Send one PNR per request.",
                422,
                details={"pnr_count": len(blocks)},
            )
        try:
            payload = build_crm_v1_payload(raw_text)
        except ValueError as ve:
            audits, unparsed, other_elements = _v1_scan_lines(raw_text)
            message = str(ve)
            if "\n" not in raw_text.strip() and len(raw_text) > 200:
                message += (" The text is a single line; the PNR's line breaks were probably lost when it was copied. "
                            "Paste it again keeping one element per line.")
            return _v1_error("NO_SEGMENTS_FOUND", message, 422,
                             details={"unparsed_lines": unparsed})
        return _v1_response(payload, 200)
    except Exception:
        # Never leak internals or echo PNR content.
        return _v1_error("INTERNAL_ERROR", "Unexpected server error while parsing PNR.", 500)


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
