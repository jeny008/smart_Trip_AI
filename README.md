# SmartTrip AI — travel planner

## Features
- AI Travel Assistant chat with follow-up questions for missing route/date/budget.
- Form-based comparison tab.
- Optional RailRadar train timetable integration using the documented station lookup and trains-between-stations endpoints.
- Honest source labels: live timetable data is distinct from fictional demo data.
- Budget comparison works for options with actual prices. RailRadar's timetable endpoint does not supply fares or seat availability, so live options show fare unavailable rather than made-up prices.
- No booking is performed.
  
- ## Live Demo
**Try SmartTrip AI:** https://smarttripai-dmdtoxcmyctzfwopjqcp7t.streamlit.app/

**GitHub Repository:** https://github.com/jeny008/smart_Trip_AI

## Setup
Python 3.10+ recommended.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env`:
```env
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=gpt-4.1-mini
RAILRADAR_API_KEY=your_railradar_api_key
```

Start the app from the project root:
```bash
python -m streamlit run src/main.py
```

Tests:
```bash
pytest -q
```

## API details
- OpenAI: the API key and API credits are separate from a ChatGPT subscription. Each chat message may make one API request.
- RailRadar: sign up and obtain a key through the provider's official site. The app calls `/v1/lookup/search/stations?q=...` and `/v1/trains/between/{from}/{to}` using the documented response shapes. Ambiguous city matches are reported instead of choosing a random station. API quotas and availability depend on the provider's current plan.
- The train timetable endpoint does not provide fare/seat availability. Verify fares and bookings with an official booking provider.
- Live bus and flight integrations are not implemented in this version.
- If no RailRadar key is set, the app does not silently claim demo options are live. Demo fallback is opt-in from the API Setup tab.

## RailRadar station dropdowns

Open the **Form-based Comparison** tab and expand **Find stations from RailRadar**. Search for the departure and destination stations, then click **Load station dropdowns**. The form dropdowns are populated from RailRadar's station autocomplete response and display the returned station name/code (and city when provided). The selected code is sent to the trains-between-stations endpoint.

The station search uses two API requests per search action, so avoid repeatedly clicking the button. A working `RAILRADAR_API_KEY` is required. The timetable endpoint does not supply ticket fares or seat availability.

## Version 7 reliability fixes

- The chat uses deterministic route parsing for trip details, preserving station codes copied from the station selector. This avoids an LLM rewrite changing route names or adding unsupported travel facts.
- Chat messages are appended to session history and rerendered in chronological order, one message below the previous message.
- Train API results are checked against the provider's returned origin and destination station codes before any train rows are displayed. Mismatched or incomplete route metadata is rejected rather than showing unrelated trains.
- Station dropdowns use records returned by RailRadar's station autocomplete endpoint; the selected station code is passed to the trains-between-stations endpoint.
- The RailRadar timetable endpoint does not provide ticket fares or booking availability. Budget affordability is not asserted when fares are missing.
- Bus and flight integrations remain demo-only/not live. No booking is made by this app.

## Run and test

From the project root:

```bash
python -m pip install -r requirements.txt
python -m streamlit run src/main.py
```

Run tests with:

```bash
PYTHONPATH=. pytest -q
```

The test suite mocks provider responses. Passing tests do not verify your live RailRadar credentials, quota, or provider uptime.


## v8 update

- When chat route lookup returns multiple matching stations, the app now loads actual RailRadar station records into a dropdown instead of stopping with an ambiguity error.
- After a station is selected, the app retries the same route using the selected station code. If the other end is also ambiguous, it asks for that station too.
- Live API behavior still depends on the configured RailRadar key, quota, and provider endpoint availability. Fares and booking availability are not supplied by the timetable endpoint.


## Version 9 fixes

- Anchors train departure times to the requested date at the selected origin station, matching RailRadar's documented date-filter semantics.
- Calculates arrival dates using the segment's arrival-day minus departure-day offset.
- Rejects malformed timetable rows when the advertised duration conflicts materially with the displayed times or station sequence is invalid.
- Keeps strict validation of the provider's top-level origin/destination station codes.

The live provider API was not called during local tests; live results still depend on the user's RailRadar key, plan, and provider response.


## v10 chat parsing fix

The chat parser recognizes singular and plural travel-mode terms such as `train` and `trains`, and strips common request prefixes such as `Find trains from` before extracting the origin station. Regression tests cover route, date, budget, and train-mode extraction for a full natural-language request.


## v11 station-selection UX fix

- Once a user chooses an ambiguous station, the previous assistant ambiguity prompt is replaced by the resolved response rather than leaving a stale warning immediately above the timetable results.
- Station codes in labels such as `Surat (ST)` remain uppercase in the trip summary.
- Regression tests cover station-code casing.

## Optional GenAI workflow (LangChain + RAG + LangGraph)

The app includes an optional GenAI summary workflow. In the sidebar, enable **Use GenAI agent for trip summary** to invoke it after live timetable results are returned. It is disabled by default to avoid unnecessary OpenAI API usage.

- **LangChain tools:** retrieve local travel guidance and explain timetable/fare limitations.
- **RAG:** `knowledge/travel_guidance.md` is retrieved using TF-IDF relevance scoring before the LLM writes its summary. This is a lightweight local retrieval implementation; it does not require a paid embedding API or a vector database.
- **LangGraph:** orchestrates retrieval, tool execution, and grounded answer generation as a state graph.
- **Grounding:** the LLM is instructed to use the app/provider results for schedule facts and never invent fares or booking availability. Deterministic route/date parsing and the RailRadar API remain separate from the LLM.

Configure `OPENAI_API_KEY` and optionally `OPENAI_MODEL` in `.env` to use the optional LLM summary. Keep the feature disabled if you want to conserve API credits. RAG retrieval tests can run without an OpenAI key.

The workflow does not provide live bus/flight integration, ticket booking, or fare lookup. A passing automated test suite does not substitute for testing the configured live RailRadar API.
