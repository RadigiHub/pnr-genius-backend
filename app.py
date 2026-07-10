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
        ]
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
}


def parse_pnr_date(date_str, reference_year=None):
    if reference_year is None:
        reference_year = datetime.now().year
    match = re.match(r"(\d{1,2})([A-Z]{3})", date_str.upper())
    if not match:
        return None
    day, mon = match.groups()
    month = MONTHS.get(mon)
    if not month:
        return None
    try:
        candidate = datetime(reference_year, month, int(day))
        if candidate < datetime.now().replace(hour=0, minute=0, second=0, microsecond=0):
            candidate = datetime(reference_year + 1, month, int(day))
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

    route_match = re.search(r"\d?\*?([A-Z]{3})([A-Z]{3})\*?", after_date, re.IGNORECASE)
    if not route_match:
        return None
    origin = route_match.group(1)
    dest = route_match.group(2)

    after_route = after_date[route_match.end():].strip()

    times_match = re.match(
        rf"^([A-Z]{{2}})(\d{{1,2}})\s+(\d{{3,4}}[AP]?)\s+(\d{{3,4}}[AP]?)(?:\s+(\d{{1,2}}{MONTH_NAMES_RE}))?",
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
        "status": times_match.group(1).upper(),
        "status_count": times_match.group(2),
        "dep_raw": times_match.group(3),
        "arr_raw": times_match.group(4),
        "arr_date_str": times_match.group(5).upper() if times_match.group(5) else None,
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
    return passengers


def parse_segments(raw_text):
    segments = []
    lines = raw_text.split("\n")

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

        iso_date, display_date = parse_pnr_date(date_str) or (None, date_str)
        dep_time = format_time(dep_raw)
        arr_time = format_time(arr_raw)

        day_offset = 0
        if arr_date and arr_date.upper() != date_str.upper():
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
            except (ValueError, AttributeError, TypeError):
                current["layover_after"] = None
        else:
            current["layover_after"] = None
    if segments:
        segments[-1]["layover_after"] = None
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


def extract_pnr_reference(raw_text):
    match = re.search(r"RP/([A-Z0-9]{5,12})/", raw_text.upper())
    if match:
        return match.group(1)

    for token in re.findall(r"\b[A-Z0-9]{6}\b", raw_text.upper()):
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
        route_summary = f"{segments[0]['origin']['code']} \u21c4 {segments[turnaround_index - 1]['destination']['code']}"
    else:
        route_summary = f"{segments[0]['origin']['code']} \u2192 {segments[-1]['destination']['code']}"

    total_distance_km = sum(s["distance_km"] for s in segments if s.get("distance_km"))
    total_distance_miles = sum(s["distance_miles"] for s in segments if s.get("distance_miles"))

    result = {
        "success": True,
        "gds_detected": gds_detected,
        "pnr_reference": pnr_ref,
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
    }
    return result


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


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
