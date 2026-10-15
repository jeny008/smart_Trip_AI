from datetime import date

import pytest

from src.conversation import (
    build_request,
    extract_fields,
    missing_question,
    parse_budget,
    parse_date,
    parse_mode,
    parse_route,
)
from src.models import TravelRequest


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("under ₹500", 500),
        ("under 500rs", 500),
        ("budget 1,500 INR", 1500),
        ("maximum budget is 250 rupees", 250),
        ("₹0", 0),
        ("no budget mentioned", None),
    ],
)
def test_budget_variants(text, expected):
    assert parse_budget(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Find train from Valsad to Surat", "train"),
        ("Find trains from Valsad to Surat", "train"),
        ("Take a bus from Valsad to Surat", "bus"),
        ("Book a flight from Mumbai to Delhi", "flight"),
        ("Plan my trip", "any"),
    ],
)
def test_mode_variants(text, expected):
    assert parse_mode(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Find trains from Valsad to Surat on 19 October 2026 under ₹500", ("Valsad", "Surat")),
        ("Valsad to Surat train 2026-10-19", ("Valsad", "Surat")),
        ("Find trains from Valsad to Surat on 19/10/2026", ("Valsad", "Surat")),
    ],
)
def test_route_variants(text, expected):
    assert parse_route(text) == expected


def test_invalid_date_is_rejected():
    assert parse_date("31 February 2026", today=date(2026, 1, 1)) == (None, False)


def test_iso_date_is_parsed():
    assert parse_date("travel on 2026-10-19") == (date(2026, 10, 19), False)


def test_missing_question_requests_route_first():
    assert "travelling from" in missing_question({"origin": None, "destination": None})


def test_build_request_normalizes_fields():
    fields = {
        "origin": " valsad ",
        "destination": " surat ",
        "travel_date": date(2026, 10, 19),
        "budget_inr": 500,
        "mode": "train",
    }
    request = build_request(fields)
    assert request.origin == "Valsad"
    assert request.destination == "Surat"
    assert request.budget_inr == 500


def test_same_origin_and_destination_rejected():
    with pytest.raises(ValueError):
        TravelRequest(
            origin="Valsad", destination="valsad",
            travel_date=date(2026, 10, 19), budget_inr=500,
        )
