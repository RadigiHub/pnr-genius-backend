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
    "LHR": {"name": "London Heathrow", "city": "London", "country": "United Kingdom"},
    "LGW": {"name": "London Gatwick", "city": "London", "country": "United Kingdom"},
    "JFK": {"name": "John F. Kennedy Intl", "city": "New York", "country": "United States"},
    "LAX": {"name": "Los Angeles Intl", "city": "Los Angeles", "country": "United States"},
    "ORD": {"name": "O'Hare International", "city": "Chicago", "country": "United States"},
    "DXB": {"name": "Dubai International", "city": "Dubai", "country": "UAE"},
    "AUH": {"name": "Abu Dhabi International", "city": "Abu Dhabi", "country": "UAE"},
    "DOH": {"name": "Hamad International", "city": "Doha", "country": "Qatar"},
    "KHI": {"name": "Jinnah International", "city": "Karachi", "country": "Pakistan"},
    "LHE": {"name": "Allama Iqbal International", "city": "Lahore", "country": "Pakistan"},
    "ISB": {"name": "Islamabad International", "city": "Islamabad", "country": "Pakistan"},
    "PEW": {"name": "Bacha Khan International", "city": "Peshawar", "country": "Pakistan"},
    "CDG": {"name": "Charles de Gaulle", "city": "Paris", "country": "France"},
    "ORY": {"name": "Paris Orly", "city": "Paris", "country": "France"},
    "FRA": {"name": "Frankfurt Airport", "city": "Frankfurt", "country": "Germany"},
    "MUC": {"name": "Munich Airport", "city": "Munich", "country": "Germany"},
    "AMS": {"name": "Amsterdam Schiphol", "city": "Amsterdam", "country": "Netherlands"},
    "IST": {"name": "Istanbul Airport", "city": "Istanbul", "country": "Turkey"},
    "SAW": {"name": "Sabiha Gokcen", "city": "Istanbul", "country": "Turkey"},
    "SIN": {"name": "Changi Airport", "city": "Singapore", "country": "Singapore"},
    "BKK": {"name": "Suvarnabhumi", "city": "Bangkok", "country": "Thailand"},
    "KUL": {"name": "Kuala Lumpur Intl", "city": "Kuala Lumpur", "country": "Malaysia"},
    "HKG": {"name": "Hong Kong International", "city": "Hong Kong", "country": "Hong Kong"},
    "NRT": {"name": "Narita International", "city": "Tokyo", "country": "Japan"},
    "HND": {"name": "Haneda Airport", "city": "Tokyo", "country": "Japan"},
    "ICN": {"name": "Incheon International", "city": "Seoul", "country": "South Korea"},
    "DEL": {"name": "Indira Gandhi Intl", "city": "Delhi", "country": "India"},
    "BOM": {"name": "Chhatrapati Shivaji", "city": "Mumbai", "country": "India"},
    "MAA": {"name": "Chennai International", "city": "Chennai", "country": "India"},
    "BLR": {"name": "Kempegowda International", "city": "Bengaluru", "country": "India"},
    "SYD": {"name": "Sydney Kingsford Smith", "city": "Sydney", "country": "Australia"},
    "MEL": {"name": "Melbourne Airport", "city": "Melbourne", "country": "Australia"},
    "YYZ": {"name": "Toronto Pearson", "city": "Toronto", "country": "Canada"},
    "YVR": {"name": "Vancouver International", "city": "Vancouver", "country": "Canada"},
    "MAN": {"name": "Manchester Airport", "city": "Manchester", "country": "United Kingdom"},
    "BHX": {"name": "Birmingham Airport", "city": "Birmingham", "country": "United Kingdom"},
    "MAD": {"name": "Adolfo Suarez Madrid-Barajas", "city": "Madrid", "country": "Spain"},
    "BCN": {"name": "Barcelona-El Prat", "city": "Barcelona", "country": "Spain"},
    "FCO": {"name": "Leonardo da Vinci-Fiumicino", "city": "Rome", "country": "Italy"},
    "MXP": {"name": "Milan Malpensa", "city": "Milan", "country": "Italy"},
    "JED": {"name": "King Abdulaziz International", "city": "Jeddah", "country": "Saudi Arabia"},
    "RUH": {"name": "King Khalid International", "city": "Riyadh", "country": "Saudi Arabia"},
    "MED": {"name": "Prince Mohammad bin Abdulaziz", "city": "Madinah", "country": "Saudi Arabia"},
    "CAI": {"name": "Cairo International", "city": "Cairo", "country": "Egypt"},
    "NBO": {"name": "Jomo Kenyatta International", "city": "Nairobi", "country": "Kenya"},
    "JNB": {"name": "O.R. Tambo International", "city": "Johannesburg", "country": "South Africa"},
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
}

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


# ---------------------------------------------------------------------------
# PARSING HELPERS
# ---------------------------------------------------------------------------

def parse_pnr_date(date_str, reference_year=None):
    """Convert '15JUL' style PNR date into ISO format. Assumes current/next year."""
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
        # If the date already passed this year by more than a few months,
        # assume it refers to next year (PNRs are usually for future travel).
        if candidate < datetime.now().replace(hour=0, minute=0, second=0, microsecond=0):
            candidate = datetime(reference_year + 1, month, int(day))
        return candidate.strftime("%Y-%m-%d"), candidate.strftime("%d %b %Y")
    except ValueError:
        return None, date_str


def format_time(raw_time):
    """Normalize times like '1120A', '215P', '0830' into 'HH:MM' 24-hour format."""
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


def calculate_duration(dep_time, arr_time, day_offset=0, origin_code=None, dest_code=None):
    """
    Returns flight duration string e.g. '7h 25m' given HH:MM local times.

    IMPORTANT: GDS PNRs show LOCAL departure and LOCAL arrival times, which
    are in different timezones for international flights. A raw subtraction
    of clock times does NOT equal real flight duration unless we account
    for the timezone offset between origin and destination.

    We use a small built-in UTC-offset table for major airports to correct
    the calculation. If either airport isn't in the table, we fall back to
    the raw elapsed-clock-time figure.
    """
    if not dep_time or not arr_time:
        return None
    try:
        dh, dm = map(int, dep_time.split(":"))
        ah, am = map(int, arr_time.split(":"))
        dep_minutes = dh * 60 + dm
        arr_minutes = ah * 60 + am + (day_offset * 1440)

        tz_correction = 0
        if origin_code and dest_code:
            origin_offset = AIRPORT_UTC_OFFSETS.get(origin_code.upper())
            dest_offset = AIRPORT_UTC_OFFSETS.get(dest_code.upper())
            if origin_offset is not None and dest_offset is not None:
                tz_correction = (dest_offset - origin_offset) * 60

        diff = (arr_minutes - tz_correction) - dep_minutes
        if diff < 0:
            diff += 1440
        # Sanity cap: durations beyond 20h usually mean a missing day_offset
        # rather than a real nonstop flight.
        if diff > 1200:
            diff = diff % 1440
        hours, mins = divmod(int(diff), 60)
        return f"{hours}h {mins:02d}m"
    except (ValueError, AttributeError, TypeError):
        return None


def get_airport_info(code):
    code = code.upper()
    return AIRPORTS.get(code, {"name": code, "city": code, "country": ""})


def get_airline_info(code):
    code = code.upper()
    return AIRLINES.get(code, code)


def get_cabin_class(code):
    return CABIN_CODES.get(code.upper(), "Economy Class")


def get_status_label(code):
    return STATUS_CODES.get(code.upper(), code)


# ---------------------------------------------------------------------------
# CORE PARSER
# Handles the common GDS line formats used across Amadeus, Sabre, Galileo
# and Worldspan. PNR formatting differs slightly between systems but the
# core flight-segment line structure is similar enough to share one parser
# with small tolerances built into the regex patterns.
# ---------------------------------------------------------------------------

# Matches passenger name lines like:  "1.SMITH/JOHN MR" or "1.SMITH/JOHNMR   2.BROWN/ANNAMS"
PASSENGER_PATTERN = re.compile(
    r"\d+\.([A-Z\-]+)/([A-Z\s]+?)(MR|MRS|MS|MISS|MSTR|DR|CHD|INF)?(?=\s{2,}|\d+\.|$)",
    re.IGNORECASE,
)

# Matches a flight segment line. Tolerant of spacing differences across GDS systems.
# Example: " 3  BA 284 H 10APR 4*LHRJFK HK2  1120A  215P 10APR  E  BA/9XZABC"
SEGMENT_PATTERN = re.compile(
    r"""
    ^\s*\d+\s+                          # line number
    ([A-Z0-9]{2})\s*                    # airline code
    (\d{1,4})\s+                        # flight number
    ([A-Z])\s+                          # booking class / cabin code
    (\d{1,2}[A-Z]{3})\s+                # date e.g. 10APR
    \d\*?\s*                            # day of week marker
    ([A-Z]{3})([A-Z]{3})\s+             # origin + destination airports
    ([A-Z]{2})(\d{1,2})?\s+             # status code e.g. HK2
    (\d{3,4}[AP]?)\s+                   # departure time
    (\d{3,4}[AP]?)\s*                   # arrival time
    (\d{1,2}[A-Z]{3})?                  # optional arrival date (next day arrivals)
    """,
    re.IGNORECASE | re.VERBOSE,
)

# A looser fallback pattern for PNRs that don't perfectly match the strict format above.
SEGMENT_PATTERN_LOOSE = re.compile(
    r"""
    ([A-Z0-9]{2})\s+               # airline
    (\d{1,4})\s+                   # flight number
    ([A-Z])\s+                     # class
    (\d{1,2}[A-Z]{3})\s+           # date
    \d?\*?\s*
    ([A-Z]{3})([A-Z]{3})\s+        # route
    [A-Z]{2}\d?\s+                 # status
    (\d{3,4}[AP]?)\s+              # dep time
    (\d{3,4}[AP]?)                 # arr time
    """,
    re.IGNORECASE | re.VERBOSE,
)


def detect_gds(raw_text):
    """Best-effort detection of which GDS the PNR text came from."""
    text = raw_text.upper()
    if "RP/" in text and "SU " in text:
        return "Amadeus"
    if re.search(r"\d\.\d[A-Z]/\d{4}", text):
        return "Sabre"
    if "SSR" in text and "RTSTR" in text:
        return "Amadeus"
    if re.search(r"^\s*\d+\s+[A-Z]{1,2}\s+\d+[A-Z]\s", text, re.MULTILINE):
        return "Galileo"
    return "Unknown / Auto-detected"


def parse_passengers(raw_text):
    passengers = []
    for match in PASSENGER_PATTERN.finditer(raw_text):
        last_name, first_name, title = match.groups()
        first_name = first_name.strip()
        passengers.append({
            "last_name": last_name.strip().title(),
            "first_name": first_name.title(),
            "title": (title or "").upper(),
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

        match = SEGMENT_PATTERN.match(line) or SEGMENT_PATTERN_LOOSE.search(line)
        if not match:
            continue

        groups = match.groups()
        # Normalize group count between strict/loose patterns
        if len(groups) >= 11:
            airline, flight_num, cabin, date_str, origin, dest, status, status_num, dep_raw, arr_raw, arr_date = groups
        else:
            airline, flight_num, cabin, date_str, origin, dest, dep_raw, arr_raw = groups[:8]
            status, status_num, arr_date = "HK", "1", None

        iso_date, display_date = parse_pnr_date(date_str) or (None, date_str)
        dep_time = format_time(dep_raw)
        arr_time = format_time(arr_raw)

        day_offset = 0
        if arr_date and arr_date.upper() != date_str.upper():
            day_offset = 1  # arrival is next day (overnight flight)
        elif arr_time and dep_time and arr_time < dep_time:
            day_offset = 1  # crosses midnight, common for long-haul

        # Compute the actual calendar date of arrival (departure date + offset).
        # This is what later layover-gap math should use, NOT the departure date.
        arrival_date_iso = None
        if iso_date:
            try:
                from datetime import timedelta
                arrival_date_iso = (
                    datetime.strptime(iso_date, "%Y-%m-%d") + timedelta(days=day_offset)
                ).strftime("%Y-%m-%d")
            except ValueError:
                arrival_date_iso = iso_date

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
                **get_airport_info(origin),
            },
            "destination": {
                "code": dest.upper(),
                **get_airport_info(dest),
            },
            "status": get_status_label(status) if status else "Confirmed",
            "departure_time": dep_time,
            "arrival_time": arr_time,
            "duration": calculate_duration(dep_time, arr_time, day_offset, origin, dest),
            "overnight": day_offset > 0,
        })

    return segments


def detect_layovers(segments):
    """
    Add layover info between consecutive segments at the same connecting
    airport. Uses each segment's actual ARRIVAL date (not departure date) to
    compute the real gap before the next departure, so overnight flights
    don't get double-counted.
    """
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
                date_gap_ok = 0 <= day_diff <= 2  # allow same-day or short overnight connections
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
    """
    Total journey duration. For a simple one-way or connecting trip this is
    first-departure to last-arrival. For a round trip (where the final
    destination equals the original origin), the "total journey" as a single
    duration figure isn't meaningful — we return None and let the frontend
    show outbound/return durations separately instead.
    """
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
        d2 = datetime.strptime(last["date_iso"], "%Y-%m-%d") if last["date_iso"] else None
        day_diff = (d2 - d1).days if d1 and d2 else 0
        total_minutes = (day_diff * 1440) + (lh * 60 + lm) - (fh * 60 + fm)
        hours, mins = divmod(total_minutes, 60)
        return f"{hours}h {mins:02d}m"
    except (ValueError, AttributeError, TypeError):
        return None


def calculate_co2_estimate(segments):
    """
    Rough CO2 estimate based on great-circle-ish flat rate per segment.
    This is a simplified placeholder model — swap in a real emissions API
    (e.g. Google Travel Impact Model) for production accuracy.
    """
    # Very rough average: ~90kg CO2 per short/medium-haul segment, 250kg per long-haul.
    # Distinguish using whether countries differ a lot - simplistic heuristic.
    total_kg = 0
    for seg in segments:
        origin_country = seg["origin"].get("country", "")
        dest_country = seg["destination"].get("country", "")
        if origin_country and dest_country and origin_country != dest_country:
            total_kg += 180
        else:
            total_kg += 90
    return round(total_kg, 1)


def extract_pnr_reference(raw_text):
    """
    Try to find a booking reference / record locator in the PNR text.
    Looks specifically for GDS-style locators (e.g. after 'RP/' in Amadeus,
    or a standalone 6-character alphanumeric code on its own token) rather
    than grabbing the first 6-letter run, which could accidentally match
    part of a passenger name or address line.
    """
    match = re.search(r"RP/([A-Z0-9]{5,12})/", raw_text.upper())
    if match:
        return match.group(1)

    # Look for a standalone 6-char alphanumeric token that contains at least
    # one digit (pure record locators are rarely all-letters, which helps
    # avoid matching plain words or name fragments).
    for token in re.findall(r"\b[A-Z0-9]{6}\b", raw_text.upper()):
        if any(ch.isdigit() for ch in token):
            return token
    return None


def parse_pnr(raw_text):
    """Main entry point: takes raw PNR text, returns fully structured itinerary data."""
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
        # Find where the outbound ends and return begins (first segment whose
        # destination matches the very first origin, scanning from the end).
        turnaround_index = len(segments) // 2
        route_summary = f"{segments[0]['origin']['code']} ⇄ {segments[turnaround_index - 1]['destination']['code']}"
    else:
        route_summary = f"{segments[0]['origin']['code']} → {segments[-1]['destination']['code']}"

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
        "is_round_trip": is_round_trip,
        "is_multi_city": len(set([s["origin"]["code"] for s in segments] + [s["destination"]["code"] for s in segments])) > 2,
    }
    return result


# ---------------------------------------------------------------------------
# API ROUTES
# ---------------------------------------------------------------------------

@app.route("/", methods=["GET"])
def health_check():
    """Simple health check so Railway knows the service is alive."""
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
    """
    Main conversion endpoint.

    Expected JSON body:
        { "pnr": "raw PNR text here", "gds": "amadeus" }  (gds field optional)

    Returns:
        Structured itinerary JSON, or an error message with HTTP 400.
    """
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
        # Catch-all so the API never crashes silently in production.
        return jsonify({
            "success": False,
            "error": "Unexpected server error while parsing PNR.",
            "detail": str(e)
        }), 500


@app.route("/api/health", methods=["GET"])
def api_health():
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
