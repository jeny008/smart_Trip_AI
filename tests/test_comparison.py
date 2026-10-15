from datetime import date, datetime, timedelta
from src.models import TravelOption, TravelRequest
from src.comparison import compare_options
from src.conversation import parse_date, parse_budget, parse_mode

def option(name, price, minutes, mode="train"):
    start = datetime(2026, 10, 19, 7, 0)
    return TravelOption(
        provider=name, mode=mode, origin="Valsad", destination="Vadodara",
        departure=start, arrival=start + timedelta(minutes=minutes),
        price_inr=price, source="test", is_demo=False
    )

def test_cheapest_within_budget():
    request = TravelRequest(origin="Valsad", destination="Vadodara", travel_date=date(2026, 10, 19), budget_inr=500)
    result = compare_options(request, [option("A", 650, 420), option("B", 450, 510)])
    assert result["cheapest"].provider == "B"
    assert len(result["over_budget"]) == 1

def test_parse_budget_and_mode():
    assert parse_budget("under ₹500") == 500
    assert parse_mode("I want a train") == "train"

def test_date_without_year_requires_confirmation():
    parsed, needs_confirmation = parse_date("19 October", today=date(2026, 10, 15))
    assert parsed == date(2026, 10, 19)
    assert needs_confirmation is True


def test_parse_route_with_parenthesized_station():
    from src.conversation import parse_route
    assert parse_route("valsad to mumbai(dadar) train 19 oct 2026 under 500rs") == ("Valsad", "Mumbai(Dadar)")
    assert parse_route("yes Valsad to Mumbai (Dadar)") == ("Valsad", "Mumbai (Dadar)")


def test_parse_route_from_ui_generated_station_labels():
    from src.conversation import parse_route
    assert parse_route("Valsad (BL) — Valsad to Surat (ST) — Surat train 20 october 2026 under 500") == ("Valsad (BL)", "Surat (ST)")


def test_parse_route_with_label_suffix_and_budget():
    from src.conversation import parse_route
    assert parse_route("Valsad to Surat train 20 October 2026 under ₹500") == ("Valsad", "Surat")


def test_route_parser_keeps_station_codes_from_ui_label():
    from src.conversation import parse_route
    assert parse_route("Valsad (BL) — Valsad to Surat (ST) — Surat train 20 october 2026 under 500") == ("Valsad (BL)", "Surat (ST)")


def test_plural_trains_input_parses_live_train_mode_and_route():
    from src.conversation import extract_fields

    fields = extract_fields("Find trains from Valsad to Surat on 19 October 2026 under 500rs")
    assert fields["origin"] == "Valsad"
    assert fields["destination"] == "Surat"
    assert fields["travel_date"] == date(2026, 10, 19)
    assert fields["budget_inr"] == 500
    assert fields["mode"] == "train"


def test_budget_followup_with_full_route_still_detects_train_mode():
    from src.conversation import parse_mode, parse_route, parse_budget

    message = "Find trains from Valsad to Surat on 19 October 2026 under 500rs"
    assert parse_mode(message) == "train"
    assert parse_route(message) == ("Valsad", "Surat")
    assert parse_budget(message) == 500


def test_travel_request_preserves_station_code_case():
    request = TravelRequest(
        origin="Valsad (bl)",
        destination="Surat (St)",
        travel_date=date(2026, 10, 19),
        budget_inr=500,
        mode="train",
    )
    assert request.origin == "Valsad (BL)"
    assert request.destination == "Surat (ST)"
