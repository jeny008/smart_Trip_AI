from datetime import date, datetime
import re
from src.models import TravelRequest

MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "september": 9, "oct": 10, "october": 10,
    "nov": 11, "november": 11, "dec": 12, "december": 12,
}

def parse_date(text: str, today: date | None = None) -> tuple[date | None, bool]:
    today = today or date.today()
    text = text.lower()
    iso = re.search(r"\b(20\d{2})-(\d{1,2})-(\d{1,2})\b", text)
    if iso:
        try:
            return date(int(iso.group(1)), int(iso.group(2)), int(iso.group(3))), False
        except ValueError:
            return None, False
    numeric = re.search(r"\b(\d{1,2})[/-](\d{1,2})[/-](20\d{2})\b", text)
    if numeric:
        try:
            return date(int(numeric.group(3)), int(numeric.group(2)), int(numeric.group(1))), False
        except ValueError:
            return None, False
    month_pattern = r"\b(\d{1,2})\s+(" + "|".join(MONTHS) + r")(?:\s+(20\d{2}))?\b"
    match = re.search(month_pattern, text)
    if not match:
        return None, False
    day, month_name, year = match.groups()
    month = MONTHS[month_name]
    try:
        if year:
            return date(int(year), month, int(day)), False
        candidate = date(today.year, month, int(day))
        if candidate < today:
            return None, True
        return candidate, True
    except ValueError:
        return None, False

def parse_budget(text: str) -> int | None:
    patterns = [
        r"(?:under|below|budget(?:\s+is)?|max(?:imum)?(?:\s+budget)?|within|₹|rs\.?|inr)\s*₹?\s*([\d,]+)",
        r"([\d,]+)\s*(?:rupees|rs\.?|inr)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text.lower())
        if match:
            try:
                return int(match.group(1).replace(",", ""))
            except ValueError:
                return None
    return None

def parse_mode(text: str) -> str:
    text = text.lower()
    if re.search(r"\b(trains?|railways?|rail)\b", text):
        return "train"
    if re.search(r"\b(bus|volvo)\b", text):
        return "bus"
    if re.search(r"\b(flight|plane|airplane|air)\b", text):
        return "flight"
    return "any"

def _title_station_label(value: str) -> str:
    value = " ".join(value.strip().split())
    match = re.fullmatch(r"(.+?)(\s*)\(([A-Za-z0-9]{2,6})\)", value)
    if match:
        name, spacing, hint = match.groups()
        normalized_hint = hint.upper() if hint.isupper() else hint.title()
        return f"{name.title().strip()}{spacing}({normalized_hint})"
    if value.isupper() and re.fullmatch(r"[A-Za-z0-9]{2,6}", value):
        return value
    return value.title()


def parse_route(text: str) -> tuple[str | None, str | None]:
    """Extract a route from plain chat or labels copied from the app UI."""
    cleaned = re.sub(r"\s+", " ", text.strip())
    cleaned = re.sub(r"^(?:yes[, ]+|please\s+|haan[, ]+|ha[, ]+)", "", cleaned, flags=re.I)

    # UI-generated labels may contain selected station labels around the route text.
    # Keep the selected station codes when that structure is present.
    ui_route = re.match(
        r"^(.+?\([A-Za-z0-9]{2,6}\))\s*[—–|]\s*.+?\s+(?:to|->|→)\s*(.+?\([A-Za-z0-9]{2,6}\))\s*[—–|]",
        cleaned,
        flags=re.I,
    )
    if ui_route:
        return _title_station_label(ui_route.group(1)), _title_station_label(ui_route.group(2))

    route_matches = list(re.finditer(r"\b(.+?)\s+(?:to|->|→)\s+(.+)", cleaned, flags=re.I))
    if not route_matches:
        return None, None
    match = route_matches[-1]
    origin, destination = match.groups()

    # Strip copied UI prefixes before the origin and UI suffixes after the destination.
    origin = re.split(r"\s+[—–|]\s+", origin)[-1].strip()
    destination = re.split(r"\s+[—–|]\s+", destination)[0].strip()
    origin = re.sub(
        r"^(?:(?:find|show|search|get|check)\s+(?:me\s+)?(?:trains?|railways?|rail|buses?|flights?)\s+from\s+|from\s+)",
        "",
        origin,
        flags=re.I,
    ).strip(" ,.;")

    destination = re.split(
        r"\s+(?:on\s+|trains?\b|railways?\b|rail\b|buses?\b|bus\b|flights?\b|flight\b|under\b|below\b|budget\b|max(?:imum)?\b|₹|rs\.?\b|inr\b|\d{1,2}\s+(?:jan|january|feb|february|mar|march|apr|april|may|jun|june|jul|july|aug|august|sep|september|oct|october|nov|november|december)\b)",
        destination,
        maxsplit=1,
        flags=re.I,
    )[0].strip(" ,.;")
    origin = origin.strip(" ,.;")

    # Preserve station-code labels while removing common duplicate city suffixes.
    for value in (origin, destination):
        if len(value) > 80:
            return None, None
    if not origin or not destination or origin.casefold() == destination.casefold():
        return None, None
    return _title_station_label(origin), _title_station_label(destination)

def extract_fields(text: str) -> dict:
    origin, destination = parse_route(text)
    travel_date, needs_date_confirmation = parse_date(text)
    return {
        "origin": origin,
        "destination": destination,
        "travel_date": travel_date,
        "needs_date_confirmation": needs_date_confirmation,
        "budget_inr": parse_budget(text),
        "mode": parse_mode(text),
    }

def missing_question(fields: dict) -> str | None:
    if not fields.get("origin") or not fields.get("destination"):
        return "Which city are you travelling from, and where do you want to go? For example: Valsad to Vadodara."
    if fields.get("travel_date") is None:
        return "What is your travel date, including the year? For example: 19 October 2026."
    if fields.get("needs_date_confirmation"):
        return f"Do you mean {fields['travel_date'].strftime('%d %B %Y')}? Please confirm the year before I compare options."
    if fields.get("budget_inr") is None:
        return "What is your maximum budget per person in INR? For example: under ₹500."
    return None

def build_request(fields: dict) -> TravelRequest:
    return TravelRequest(
        origin=fields["origin"],
        destination=fields["destination"],
        travel_date=fields["travel_date"],
        budget_inr=fields["budget_inr"],
        mode=fields["mode"],
    )
