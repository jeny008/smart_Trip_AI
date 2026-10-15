import os
import re
from datetime import date, datetime, time
import streamlit as st
from dotenv import load_dotenv
from src.comparison import compare_options
from src.conversation import extract_fields, missing_question, build_request
from src.data import get_demo_options
from src.rail_api import fetch_provider_options, search_stations

load_dotenv()
st.set_page_config(page_title="SmartTrip AI", page_icon="🧭", layout="wide")
st.markdown("""
<style>
div[data-testid="stChatMessage"] { border-radius: 14px; padding: 0.65rem 0.85rem; margin-bottom: 0.55rem; }
div[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) { background: rgba(65, 105, 225, 0.10); }
div[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-assistant"]) { background: rgba(120, 120, 120, 0.10); }
div[data-testid="stChatMessage"] p { margin-bottom: 0.35rem; }
</style>
""", unsafe_allow_html=True)
st.title("🧭 SmartTrip AI")
st.caption("Compare travel options while keeping your budget in mind.")
st.info("Live data note: RailRadar can provide train timetables. Its trains-between-stations endpoint does not provide fares or booking availability. Bus and flight results are not live in this version.")

with st.sidebar:
    st.header("GenAI features")
    st.caption("LangChain + RAG + LangGraph")
    st.checkbox(
        "Use GenAI agent for trip summary",
        key="enable_genai_agent",
        value=False,
        help="Optional OpenAI call. Disabled by default to conserve API credits.",
    )
    st.caption("The agent retrieves local travel guidance and summarizes verified app data. It does not verify fares or book tickets.")

def _append_genai_summary(question: str, trip_data: str) -> str:
    """Optionally enrich the deterministic result with a LangGraph/RAG summary."""
    if not st.session_state.get("enable_genai_agent", False):
        return trip_data
    if not os.getenv("OPENAI_API_KEY"):
        return trip_data + "\n\n**GenAI agent:** Add `OPENAI_API_KEY` to `.env` to enable the optional LangChain/LangGraph summary. RAG retrieval remains available in the project tests."
    try:
        from src.genai_workflow import run_langgraph_trip_agent
        summary = run_langgraph_trip_agent(question=question, trip_data=trip_data, model_name=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"))
        return trip_data + "\n\n### GenAI travel assistant summary\n\n" + summary
    except Exception as exc:
        # Keep the verified deterministic result visible if the optional LLM workflow fails.
        return trip_data + f"\n\n**GenAI agent unavailable:** {type(exc).__name__}. The timetable results above are unchanged."


def format_results(request, options, is_live: bool) -> str:
    result = compare_options(request, options)
    lines = [
        f"### Trip: {request.origin} → {request.destination}",
        f"- Date: {request.travel_date.strftime('%d %B %Y')}",
        f"- Mode: {request.mode.title()}",
        f"- Budget target: ₹{request.budget_inr:,} per person (fare not available from live API)" if request.budget_inr is not None and is_live else (f"- Budget: ₹{request.budget_inr:,} per person" if request.budget_inr is not None else "- Budget: Not specified"),
        "",
        "**LIVE PROVIDER TIMETABLE — fares are not supplied by this API.**" if is_live else "**DEMO DATA ONLY — fictional examples, not real schedules or fares.**",
    ]
    if is_live:
        lines.extend([
            "",
            "**Budget warning:** RailRadar does not return ticket fares. These timetable results are NOT confirmed to be under your budget.",
            "",
            "Train names can show the train's full route. Each result below labels the requested station segment and shows the segment's departure and arrival times. Results are only shown when the provider confirms the requested route pair and a forward station sequence. Fare and seat availability are not provided by this endpoint.",
        ])
    if not result["options"]:
        lines.append("No options were returned for the selected mode.")
    for option in result["options"]:
        price = f"₹{option.price_inr:,}" if option.price_inr is not None else "Fare unavailable from this source"
        duration = f"{option.duration_minutes // 60}h {option.duration_minutes % 60}m"
        departure = option.departure.strftime("%d %b, %I:%M %p")
        arrival = option.arrival.strftime("%d %b, %I:%M %p")
        lines.append(f"- **{option.provider}** ({option.mode.title()}): {price} · {duration}")
        if is_live and option.mode == "train":
            lines.append(f"  - Requested segment: **{request.origin} → {request.destination}** · {departure} → {arrival}")
        else:
            lines.append(f"  - Route: {option.origin} → {option.destination} · {departure} → {arrival}")
        lines.append(f"  - Source: {option.source}")
    if result["cheapest"]:
        lines.extend(["", f"**Cheapest option within budget:** {result['cheapest'].provider} — ₹{result['cheapest'].price_inr:,}."])
    elif is_live:
        lines.extend(["", "The live timetable contains no fare values, so budget affordability cannot be verified. Check the fare with the official booking provider."])
    elif result["options"]:
        lines.extend(["", "No option with a known demo price is within this budget."])
    lines.extend(["", "No booking has been made. Verify details with the official travel provider before paying."])
    rendered = "\n".join(lines)
    question = f"Plan {request.mode} travel from {request.origin} to {request.destination} on {request.travel_date}; budget target INR {request.budget_inr}."
    return _append_genai_summary(question, rendered)


if "messages" not in st.session_state:
    st.session_state.messages = []
if "travel_fields" not in st.session_state:
    st.session_state.travel_fields = {
        "origin": None, "destination": None, "travel_date": None,
        "needs_date_confirmation": False, "budget_inr": None, "mode": "any"
    }
if "pending_date_confirmation" not in st.session_state:
    st.session_state.pending_date_confirmation = False

def respond(user_text: str) -> str:
    fields = st.session_state.travel_fields
    extracted = extract_fields(user_text)
    if st.session_state.pending_date_confirmation:
        answer = user_text.strip().lower()
        if answer in {"yes", "yes please", "correct", "confirm", "y", "haan", "ha", "yes, confirm"}:
            st.session_state.pending_date_confirmation = False
            fields["needs_date_confirmation"] = False
        else:
            replacement = extract_fields(user_text)
            if replacement["travel_date"] is not None and not replacement["needs_date_confirmation"]:
                fields["travel_date"] = replacement["travel_date"]
                fields["needs_date_confirmation"] = False
                st.session_state.pending_date_confirmation = False
            else:
                return "Please send the full date including the year, for example: 19 October 2026."
    for key in ("origin", "destination", "travel_date", "budget_inr"):
        if extracted.get(key) is not None:
            fields[key] = extracted[key]
    if extracted.get("travel_date") is not None:
        fields["needs_date_confirmation"] = extracted.get("needs_date_confirmation", False)
    if extracted.get("mode") != "any":
        fields["mode"] = extracted["mode"]
    question = missing_question(fields)
    if question:
        if fields.get("needs_date_confirmation"):
            st.session_state.pending_date_confirmation = True
        return question
    try:
        request = build_request(fields)
    except Exception as exc:
        return f"I couldn't validate those trip details: {exc}. Please check the city names, date, and budget."
    if request.mode != "train":
        return "Live provider integration currently supports train timetables only. Choose Train for live results, or use the form tab's demo comparison for bus/flight examples."
    live_options, error = fetch_provider_options(request)
    if live_options:
        st.session_state.pop("pending_chat_station_selection", None)
        return format_results(request, live_options, True)
    if error and "matches multiple stations" in error.lower():
        match = re.search(r"'([^']+)' matches multiple stations", error, flags=re.I)
        if match:
            station_query = match.group(1).strip()
            side = "origin" if station_query.casefold() in str(fields.get("origin", "")).casefold() else "destination"
            records, lookup_error = search_stations(station_query)
            if records:
                st.session_state.pending_chat_station_selection = {
                    "side": side,
                    "query": station_query,
                    "records": records,
                }
                return f"I found multiple stations for **{station_query}**. Please select the exact station from the dropdown below; I won't guess which one you mean."
            if lookup_error:
                return f"{error} I couldn't load the station choices: {lookup_error}"
    if st.session_state.get("allow_demo_fallback", False):
        demo_options = get_demo_options(request)
        return format_results(request, demo_options, False) + f"\n\n**Live API status:** {error or 'No live results.'}"
    return f"**Live train data is not available right now.** {error or 'No live options returned.'}\n\nI have not substituted fictional data. Check the API key and provider response, then try again."

tab_chat, tab_form, tab_setup = st.tabs(["AI Travel Assistant", "Form-based Comparison", "API Setup"])

with tab_chat:
    st.subheader("Plan your trip through conversation")
    st.caption("Example: Valsad to Vadodara, train, 19 October 2026, under ₹500. Chat messages remain in chronological order.")
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    prompt = st.chat_input("Tell me your route, date, mode and budget", key="chat_input")
    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        answer = respond(prompt)
        st.session_state.messages.append({"role": "assistant", "content": answer})
        st.rerun()

    pending_station = st.session_state.get("pending_chat_station_selection")
    if pending_station:
        st.markdown(f"**Choose the exact {pending_station['side']} station for {pending_station['query']}:**")
        station_records = pending_station["records"]
        station_labels = [
            f"{record['name']} ({record['code']})" + (f" — {record['city']}" if record.get("city") else "")
            for record in station_records
        ]
        selected_label = st.selectbox(
            "Station options", station_labels, key="chat_station_choice"
        )
        if st.button("Use selected station and continue", type="primary", key="confirm_chat_station"):
            selected_index = station_labels.index(selected_label)
            selected_record = station_records[selected_index]
            fields = st.session_state.travel_fields
            fields[pending_station["side"]] = f"{selected_record['name']} ({selected_record['code']})"
            st.session_state.pending_chat_station_selection = None
            try:
                request = build_request(fields)
                live_options, error = fetch_provider_options(request) if request.mode == "train" else ([], "Live provider integration currently supports train timetables only.")
                if live_options:
                    answer = format_results(request, live_options, True)
                elif error and "matches multiple stations" in error.lower():
                    match = re.search(r"'([^']+)' matches multiple stations", error, flags=re.I)
                    if match:
                        query = match.group(1).strip()
                        side = "origin" if query.casefold() in str(fields.get("origin", "")).casefold() else "destination"
                        records, lookup_error = search_stations(query)
                        if records:
                            st.session_state.pending_chat_station_selection = {"side": side, "query": query, "records": records}
                            answer = f"I found multiple stations for **{query}**. Please select the exact station from the dropdown below."
                        else:
                            answer = lookup_error or error
                    else:
                        answer = error
                else:
                    answer = f"**Live train data is not available right now.** {error or 'No live options returned.'}"
            except Exception as exc:
                answer = f"I couldn't validate those trip details: {exc}"
            # Replace the pending station prompt with the resolved result instead of
            # leaving a stale ambiguity warning immediately above the final results.
            if (
                st.session_state.messages
                and st.session_state.messages[-1].get("role") == "assistant"
                and any(phrase in st.session_state.messages[-1].get("content", "").lower() for phrase in ("matches multiple stations", "found multiple stations"))
            ):
                st.session_state.messages[-1]["content"] = answer
            else:
                st.session_state.messages.append({"role": "assistant", "content": answer})
            st.rerun()

with tab_form:
    st.subheader("Compare using a form")
    st.caption("Load station choices from RailRadar first. The dropdown stores the actual station code, not a guessed city name.")

    if "origin_station_records" not in st.session_state:
        st.session_state.origin_station_records = []
    if "destination_station_records" not in st.session_state:
        st.session_state.destination_station_records = []
    if "station_search_error" not in st.session_state:
        st.session_state.station_search_error = None

    with st.expander("Find stations from RailRadar", expanded=not bool(st.session_state.origin_station_records and st.session_state.destination_station_records)):
        with st.form("station_search_form"):
            s1, s2 = st.columns(2)
            with s1:
                origin_query = st.text_input("Search departure station", value="Valsad", help="Example: Valsad")
            with s2:
                destination_query = st.text_input("Search destination station", value="Dadar", help="Example: Dadar")
            search_clicked = st.form_submit_button("Load station dropdowns", type="secondary")
        if search_clicked:
            origin_rows, origin_error = search_stations(origin_query)
            destination_rows, destination_error = search_stations(destination_query)
            st.session_state.origin_station_records = origin_rows
            st.session_state.destination_station_records = destination_rows
            errors = [error for error in (origin_error, destination_error) if error]
            st.session_state.station_search_error = " ".join(errors) if errors else None
            st.rerun()
        if st.session_state.station_search_error:
            st.warning(st.session_state.station_search_error)

    origin_records = st.session_state.origin_station_records
    destination_records = st.session_state.destination_station_records
    with st.form("trip_form"):
        c1, c2 = st.columns(2)
        with c1:
            if origin_records:
                origin_labels = [f"{r['name']} ({r['code']})" + (f" — {r['city']}" if r['city'] else "") for r in origin_records]
                origin_choice = st.selectbox("From station", options=origin_labels, key="origin_station_choice")
                origin_index = origin_labels.index(origin_choice)
                origin = f"{origin_records[origin_index]['name']} ({origin_records[origin_index]['code']})"
            else:
                origin = st.text_input("From city or station", value="Valsad")
            travel_date = st.date_input("Travel date", value=date.today())
            mode = st.selectbox("Travel mode", ["train", "bus", "flight", "any"], index=0)
        with c2:
            if destination_records:
                destination_labels = [f"{r['name']} ({r['code']})" + (f" — {r['city']}" if r['city'] else "") for r in destination_records]
                destination_choice = st.selectbox("To station", options=destination_labels, key="destination_station_choice")
                destination_index = destination_labels.index(destination_choice)
                destination = f"{destination_records[destination_index]['name']} ({destination_records[destination_index]['code']})"
            else:
                destination = st.text_input("To city or station", value="Dadar")
            budget = st.number_input("Maximum budget per person (INR)", min_value=0, max_value=1000000, value=500, step=100)
            use_live = st.checkbox("Use live RailRadar train timetable when available", value=True)
        submit = st.form_submit_button("Find options", type="primary")
    if submit:
        from src.models import TravelRequest
        try:
            request = TravelRequest(origin=origin, destination=destination, travel_date=travel_date, budget_inr=int(budget), mode=mode)
            live_options, error = fetch_provider_options(request) if use_live and mode in {"train", "any"} else ([], None)
            if live_options:
                st.markdown(format_results(request, live_options, True))
            elif st.session_state.get("allow_demo_fallback", False):
                st.warning(error or "Live data not available; showing fictional demo examples.")
                st.markdown(format_results(request, get_demo_options(request), False))
            else:
                st.warning(error or "No live train data available. No demo data was substituted.")
                if mode in {"bus", "flight", "any"}:
                    st.info("Live bus/flight integrations are not configured. Select Train for RailRadar timetable results.")
        except Exception as exc:
            st.error(f"Please check your trip details: {exc}")

with tab_setup:
    st.subheader("API status and setup")
    openai_configured = bool(os.getenv("OPENAI_API_KEY", "").strip())
    rail_configured = bool(os.getenv("RAILRADAR_API_KEY", "").strip())
    st.write("OpenAI API key:", "Configured (not called for normal trip parsing)" if openai_configured else "Not configured (optional in this version)")
    st.write("RailRadar API key:", "Configured" if rail_configured else "Not configured")
    st.markdown("1. Create/edit `.env` in the project root.\n2. Set `OPENAI_API_KEY=...` for conversational rewriting.\n3. Set `RAILRADAR_API_KEY=...` from the RailRadar account for live train timetable search.\n4. Restart Streamlit after changing `.env`.")
    st.markdown("RailRadar docs: https://railradar.in/docs/trains-between-stations")
    st.markdown("OpenAI usage: https://platform.openai.com/usage")
    st.warning("The live train timetable endpoint does not return fares or seat availability. This app does not invent those values.")
    st.session_state.allow_demo_fallback = st.checkbox(
        "Allow clearly labelled fictional demo data if live API fails",
        value=st.session_state.get("allow_demo_fallback", False)
    )

with st.sidebar:
    st.header("Trip details")
    fields = st.session_state.travel_fields
    st.write("**From:**", fields.get("origin") or "Not provided")
    st.write("**To:**", fields.get("destination") or "Not provided")
    st.write("**Date:**", fields["travel_date"].strftime("%d %B %Y") if fields.get("travel_date") else "Not provided")
    st.write("**Budget:**", f"₹{fields['budget_inr']:,}" if fields.get("budget_inr") is not None else "Not provided")
    st.write("**Mode:**", fields.get("mode", "any").title())
    if st.button("Start a new trip"):
        st.session_state.messages = []
        st.session_state.travel_fields = {
            "origin": None, "destination": None, "travel_date": None,
            "needs_date_confirmation": False, "budget_inr": None, "mode": "any"
        }
        st.session_state.pending_date_confirmation = False
        st.rerun()
    st.caption("Chat route parsing is deterministic in this version to prevent the model from changing station names or inventing travel details. It does not call OpenAI for every message.")
