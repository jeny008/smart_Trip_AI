from datetime import date

import requests

from src import rail_api
from src.models import TravelRequest


def request():
    return TravelRequest(
        origin="Valsad (BL)", destination="Surat (ST)",
        travel_date=date(2026, 10, 19), budget_inr=500, mode="train",
    )


def test_missing_api_key_returns_actionable_error(monkeypatch):
    monkeypatch.delenv("RAILRADAR_API_KEY", raising=False)
    options, error = rail_api.fetch_provider_options(request())
    assert options == []
    assert "RAILRADAR_API_KEY" in error


def test_unexpected_train_list_is_rejected(monkeypatch):
    monkeypatch.setenv("RAILRADAR_API_KEY", "test-key")
    monkeypatch.setattr(rail_api, "_get_json", lambda *args, **kwargs: {
        "success": True,
        "data": {"from": {"code": "BL"}, "to": {"code": "ST"}, "trains": {"bad": "shape"}},
    })
    options, error = rail_api.fetch_provider_options(request())
    assert options == []
    assert "unexpected trains list" in error.lower()


def test_http_401_has_clear_message(monkeypatch):
    monkeypatch.setenv("RAILRADAR_API_KEY", "test-key")
    response = requests.Response()
    response.status_code = 401
    error = requests.HTTPError(response=response)

    def raise_http_error(*args, **kwargs):
        raise error

    monkeypatch.setattr(rail_api, "_get_json", raise_http_error)
    options, message = rail_api.fetch_provider_options(request())
    assert options == []
    assert "HTTP 401" in message


def test_non_dictionary_payload_is_rejected_by_adapter(monkeypatch):
    monkeypatch.setenv("RAILRADAR_API_KEY", "test-key")
    monkeypatch.setattr(rail_api, "_get_json", lambda *args, **kwargs: {"success": True, "data": []})
    options, error = rail_api.fetch_provider_options(request())
    assert options == []
    assert "unexpected response format" in error.lower()


def test_route_metadata_mismatch_is_rejected(monkeypatch):
    monkeypatch.setenv("RAILRADAR_API_KEY", "test-key")
    monkeypatch.setattr(rail_api, "_get_json", lambda *args, **kwargs: {
        "success": True,
        "data": {
            "from": {"code": "BL"},
            "to": {"code": "BRC"},
            "trains": [],
        },
    })
    options, error = rail_api.fetch_provider_options(request())
    assert options == []
    assert "route mismatch" in error.lower()


def test_missing_station_sequence_does_not_show_unverified_train(monkeypatch):
    monkeypatch.setenv("RAILRADAR_API_KEY", "test-key")
    monkeypatch.setattr(rail_api, "_get_json", lambda *args, **kwargs: {
        "success": True,
        "data": {
            "from": {"code": "BL"},
            "to": {"code": "ST"},
            "trains": [{
                "train": {"name": "Unverified train", "number": "12345"},
                "from": {"departure": "14:50", "day": 1},
                "to": {"arrival": "15:35", "day": 1},
                "duration": 45,
            }],
        },
    })
    options, error = rail_api.fetch_provider_options(request())
    assert options == []
    assert "no validated train segments" in error.lower()
