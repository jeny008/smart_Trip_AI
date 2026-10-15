"""RailRadar timetable adapter using documented station autocomplete and route endpoints."""
import os
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import requests
from .models import TravelOption, TravelRequest

BASE_URL = "https://api.railradar.in/v1"
IST = ZoneInfo("Asia/Kolkata")

def _get_json(path: str, api_key: str, params: dict | None = None) -> dict:
    response = requests.get(
        f"{BASE_URL}{path}",
        params=params or {},
        headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
        timeout=12,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict) or payload.get("success") is False:
        error = payload.get("error", {}) if isinstance(payload, dict) else {}
        raise ValueError(str(error.get("message", "Provider returned an unsuccessful response.")))
    return payload

def search_stations(query: str, api_key: str | None = None) -> tuple[list[dict[str, str]], str | None]:
    """Return station records from RailRadar autocomplete for dropdown selection."""
    key = (api_key or os.getenv("RAILRADAR_API_KEY", "")).strip().strip("'").strip('"')
    if not key:
        return [], "Add RAILRADAR_API_KEY in .env to search actual RailRadar station records."
    if not query.strip():
        return [], "Enter a station name or code to search."
    try:
        payload = _get_json("/lookup/search/stations", key, {"q": query.strip(), "limit": 20})
        rows = payload.get("data", [])
        if not isinstance(rows, list):
            return [], "RailRadar station search returned an unexpected response format."
        records: list[dict[str, str]] = []
        seen: set[str] = set()
        for row in rows:
            if not isinstance(row, dict) or not row.get("code") or not row.get("name"):
                continue
            code = str(row["code"]).strip().upper()
            if code in seen:
                continue
            seen.add(code)
            records.append({
                "code": code,
                "name": str(row["name"]).strip(),
                "city": str(row.get("city") or "").strip(),
            })
        if not records:
            return [], f"RailRadar returned no station records for '{query.strip()}'. Try another search term."
        return records, None
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else "unknown"
        if status == 401:
            return [], "RailRadar rejected the API key (HTTP 401). Check RAILRADAR_API_KEY."
        if status == 429:
            return [], "RailRadar API quota/rate limit reached (HTTP 429)."
        return [], f"RailRadar station search failed with HTTP {status}."
    except requests.RequestException:
        return [], "Could not reach RailRadar station search. Check your internet connection."
    except ValueError as exc:
        return [], f"RailRadar response issue: {exc}"

def _search_station(api_key: str, city: str) -> tuple[str | None, str | None, str | None]:
    # Use the selected provider station code directly when the user includes it.
    station_text = city.strip()
    code_match = re.fullmatch(r".*?\(([A-Za-z0-9]{2,6})\)", station_text)
    standalone_code = re.fullmatch(r"([A-Za-z0-9]{2,6})", station_text)
    if code_match:
        code = code_match.group(1).upper()
        display_name = station_text[:code_match.start(1) - 1].strip().rstrip("(").strip()
        return code, display_name or code, None
    if standalone_code and station_text.isupper():
        code = standalone_code.group(1).upper()
        return code, code, None

    payload = _get_json("/lookup/search/stations", api_key, {"q": city, "limit": 10})
    rows = payload.get("data", [])
    if not isinstance(rows, list):
        return None, None, "RailRadar station search returned an unexpected response format."
    if not rows:
        return None, None, f"No RailRadar station matches '{city}'. Try a station name or station code."
    city_query = city.casefold().strip()
    normalized = []
    for row in rows:
        if not isinstance(row, dict) or not row.get("code") or not row.get("name"):
            continue
        code = str(row["code"]).strip().upper()
        name = str(row["name"]).strip()
        city_name = str(row.get("city") or "").strip()
        normalized.append((code, name, city_name))
    exact = [row for row in normalized if row[1].casefold() == city_query or row[2].casefold() == city_query]
    if len(exact) == 1:
        return exact[0][0], exact[0][1], None
    if len(exact) > 1:
        options = ", ".join(f"{name} ({code})" for code, name, _ in exact[:5])
        return None, None, f"'{city}' matches multiple stations: {options}. Please use a specific station name/code."
    # Accept a single unambiguous substring result, but never arbitrarily choose among several stations.
    matching = [
        row for row in normalized
        if city_query in row[1].casefold() or city_query in row[2].casefold()
    ]
    if len(matching) == 1:
        return matching[0][0], matching[0][1], None
    if len(matching) > 1:
        options = ", ".join(f"{name} ({code})" for code, name, _ in matching[:6])
        return None, None, f"'{city}' matches multiple stations: {options}. Please enter the station name or code you want."
    options = ", ".join(f"{name} ({code})" for code, name, _ in normalized[:6])
    return None, None, f"Could not uniquely match '{city}'. Search results: {options or 'none'}."

def fetch_provider_options(request: TravelRequest) -> tuple[list[TravelOption], str | None]:
    """Fetch real train timetable rows. The endpoint does not provide ticket fares."""
    api_key = os.getenv("RAILRADAR_API_KEY", "").strip().strip("'").strip('"')
    if not api_key:
        return [], "Add RAILRADAR_API_KEY in .env to enable live train timetable results."
    try:
        from_code, from_name, from_error = _search_station(api_key, request.origin)
        if from_error:
            return [], from_error
        to_code, to_name, to_error = _search_station(api_key, request.destination)
        if to_error:
            return [], to_error
        params = {"date": request.travel_date.isoformat(), "live": "false", "byCity": "false"}
        trains_payload = _get_json(f"/trains/between/{from_code}/{to_code}", api_key, params)
        data = trains_payload.get("data", {})
        if not isinstance(data, dict):
            return [], "RailRadar train search returned an unexpected response format."

        # Never display a provider response if its route metadata does not match
        # the requested station pair. This guards against unrelated route results.
        response_from = data.get("from") or {}
        response_to = data.get("to") or {}
        returned_from_code = str(response_from.get("code") or "").strip().upper()
        returned_to_code = str(response_to.get("code") or "").strip().upper()
        if not returned_from_code or not returned_to_code:
            return [], "RailRadar response did not include route station codes, so results cannot be safely validated."
        if returned_from_code != from_code:
            return [], f"RailRadar route mismatch: requested origin {from_code}, but provider returned {returned_from_code}. No results were shown."
        if returned_to_code != to_code:
            return [], f"RailRadar route mismatch: requested destination {to_code}, but provider returned {returned_to_code}. No results were shown."
        rows = data.get("trains", [])
        if not isinstance(rows, list):
            return [], "RailRadar train search returned an unexpected trains list."
        options: list[TravelOption] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            train = row.get("train", {}) or {}
            from_data = row.get("from", {}) or {}
            to_data = row.get("to", {}) or {}
            if not isinstance(from_data, dict) or not isinstance(to_data, dict):
                continue

            # Some provider response variants may include station codes on each
            # train segment. If present, they must match the requested route.
            # The documented response usually relies on top-level route metadata
            # plus each segment's station sequence numbers.
            row_from_code = str(from_data.get("code") or "").strip().upper()
            row_to_code = str(to_data.get("code") or "").strip().upper()
            if row_from_code and row_from_code != from_code:
                continue
            if row_to_code and row_to_code != to_code:
                continue

            departure_text = from_data.get("departure")
            arrival_text = to_data.get("arrival")
            duration = row.get("duration")
            if not departure_text or not arrival_text or duration is None:
                continue
            # Station sequence is necessary to validate that this row represents
            # a forward segment between the selected stations, not just plausible times.
            from_sequence = from_data.get("sequence")
            to_sequence = to_data.get("sequence")
            if from_sequence is None or to_sequence is None:
                continue
            try:
                if int(to_sequence) <= int(from_sequence):
                    continue
            except (TypeError, ValueError):
                continue
            try:
                departure_clock = datetime.strptime(str(departure_text), "%H:%M").time()
                arrival_clock = datetime.strptime(str(arrival_text), "%H:%M").time()
                departure_day = int(from_data.get("day", 1))
                arrival_day = int(to_data.get("day", departure_day))
                # RailRadar's `date` filter is the date the train is at the
                # selected origin station, not the train's original source date.
                # Therefore, anchor departure to the requested date and use only
                # the difference between segment day numbers for the arrival date.
                if arrival_day < departure_day:
                    continue
                departure = datetime.combine(
                    request.travel_date,
                    departure_clock, tzinfo=IST
                )
                arrival = datetime.combine(
                    request.travel_date + timedelta(days=arrival_day - departure_day),
                    arrival_clock, tzinfo=IST
                )
                if arrival <= departure:
                    arrival += timedelta(days=1)
                # Reject malformed provider rows where the advertised duration
                # strongly contradicts the departure/arrival times.
                try:
                    advertised_duration = int(duration)
                except (TypeError, ValueError):
                    continue
                actual_duration = int((arrival - departure).total_seconds() // 60)
                if advertised_duration <= 0 or abs(actual_duration - advertised_duration) > 10:
                    continue
                name = str(train.get("name") or "Train")
                number = str(train.get("number") or "")
                provider = f"{name} ({number})" if number else name
                options.append(TravelOption(
                    provider=provider,
                    mode="train",
                    origin=from_name or request.origin,
                    destination=to_name or request.destination,
                    departure=departure,
                    arrival=arrival,
                    price_inr=None,
                    source="RailRadar timetable API; fare not supplied by this endpoint",
                    is_demo=False,
                ))
            except (ValueError, TypeError):
                continue
        if not options:
            return [], f"RailRadar returned no validated train segments for {from_name} → {to_name} on {request.travel_date.isoformat()}."
        options.sort(key=lambda option: option.departure)
        return options, None
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else "unknown"
        if status == 401:
            return [], "RailRadar rejected the API key (HTTP 401). Check RAILRADAR_API_KEY."
        if status == 429:
            return [], "RailRadar API quota/rate limit reached (HTTP 429)."
        if status == 404:
            return [], "RailRadar found no route results for this station pair/date (HTTP 404). Try another date or station."
        return [], f"RailRadar request failed with HTTP {status}. Check provider status and API plan."
    except requests.RequestException:
        return [], "Could not reach RailRadar. Check your internet connection and provider status."
    except ValueError as exc:
        return [], f"RailRadar response issue: {exc}"
