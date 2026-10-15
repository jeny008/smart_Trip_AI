from src import rail_api


def test_station_label_with_code_skips_lookup(monkeypatch):
    def unexpected_lookup(*args, **kwargs):
        raise AssertionError("Station code selection should not call station search")

    monkeypatch.setattr(rail_api, "_get_json", unexpected_lookup)
    assert rail_api._search_station("test-key", "Dadar (Ddr)") == ("DDR", "Dadar", None)
    assert rail_api._search_station("test-key", "Dadar (DR)") == ("DR", "Dadar", None)


def test_standalone_uppercase_station_code_skips_lookup(monkeypatch):
    def unexpected_lookup(*args, **kwargs):
        raise AssertionError("Station code selection should not call station search")

    monkeypatch.setattr(rail_api, "_get_json", unexpected_lookup)
    assert rail_api._search_station("test-key", "DDR") == ("DDR", "DDR", None)


def test_route_response_mismatch_is_rejected(monkeypatch):
    from datetime import date
    from src.models import TravelRequest

    monkeypatch.setenv("RAILRADAR_API_KEY", "test-key")

    def fake_get_json(path, api_key, params=None):
        assert path == "/trains/between/BL/ST"
        return {
            "success": True,
            "data": {
                "from": {"code": "MMCT", "name": "Mumbai Central"},
                "to": {"code": "ST", "name": "Surat"},
                "trains": [],
            },
        }

    monkeypatch.setattr(rail_api, "_get_json", fake_get_json)
    request = TravelRequest(
        origin="Valsad (BL)", destination="Surat (ST)",
        travel_date=date(2026, 10, 19), budget_inr=500, mode="train"
    )
    options, error = rail_api.fetch_provider_options(request)
    assert options == []
    assert error is not None and "route mismatch" in error.lower()


def test_train_segment_dates_are_anchored_to_requested_station_date(monkeypatch):
    from datetime import date
    from src.models import TravelRequest

    monkeypatch.setenv("RAILRADAR_API_KEY", "test-key")

    def fake_get_json(path, api_key, params=None):
        if path == "/trains/between/BL/ST":
            return {
                "success": True,
                "data": {
                    "from": {"code": "BL", "name": "Valsad"},
                    "to": {"code": "ST", "name": "Surat"},
                    "trains": [{
                        "train": {"number": "12345", "name": "Test Express"},
                        "from": {"departure": "16:00", "day": 2, "sequence": 4},
                        "to": {"arrival": "16:47", "day": 2, "sequence": 5},
                        "duration": 47,
                    }],
                },
            }
        raise AssertionError(f"Unexpected path: {path}")

    monkeypatch.setattr(rail_api, "_get_json", fake_get_json)
    request = TravelRequest(
        origin="Valsad (BL)", destination="Surat (ST)",
        travel_date=date(2026, 10, 19), budget_inr=500, mode="train"
    )
    options, error = rail_api.fetch_provider_options(request)
    assert error is None
    assert len(options) == 1
    assert options[0].departure.date() == date(2026, 10, 19)
    assert options[0].arrival.date() == date(2026, 10, 19)


def test_invalid_train_segment_duration_is_rejected(monkeypatch):
    from datetime import date
    from src.models import TravelRequest

    monkeypatch.setenv("RAILRADAR_API_KEY", "test-key")

    def fake_get_json(path, api_key, params=None):
        return {
            "success": True,
            "data": {
                "from": {"code": "BL", "name": "Valsad"},
                "to": {"code": "ST", "name": "Surat"},
                "trains": [{
                    "train": {"number": "12345", "name": "Bad Row"},
                    "from": {"departure": "16:00", "day": 1, "sequence": 4},
                    "to": {"arrival": "16:47", "day": 1, "sequence": 5},
                    "duration": 150,
                }],
            },
        }

    monkeypatch.setattr(rail_api, "_get_json", fake_get_json)
    request = TravelRequest(
        origin="Valsad (BL)", destination="Surat (ST)",
        travel_date=date(2026, 10, 19), budget_inr=500, mode="train"
    )
    options, error = rail_api.fetch_provider_options(request)
    assert options == []
    assert error is not None and "no validated train segments" in error.lower()


def test_train_row_with_explicit_wrong_station_code_is_rejected(monkeypatch):
    from datetime import date
    from src.models import TravelRequest

    monkeypatch.setenv("RAILRADAR_API_KEY", "test-key")

    def fake_get_json(path, api_key, params=None):
        return {
            "success": True,
            "data": {
                "from": {"code": "BL", "name": "Valsad"},
                "to": {"code": "ST", "name": "Surat"},
                "trains": [{
                    "train": {"number": "12345", "name": "Wrong segment"},
                    "from": {"code": "MMCT", "departure": "16:00", "day": 1, "sequence": 4},
                    "to": {"code": "ST", "arrival": "16:47", "day": 1, "sequence": 5},
                    "duration": 47,
                }],
            },
        }

    monkeypatch.setattr(rail_api, "_get_json", fake_get_json)
    request = TravelRequest(
        origin="Valsad (BL)", destination="Surat (ST)",
        travel_date=date(2026, 10, 19), budget_inr=500, mode="train"
    )
    options, error = rail_api.fetch_provider_options(request)
    assert options == []
    assert error is not None and "no validated train segments" in error.lower()


def test_train_row_without_station_sequence_is_rejected(monkeypatch):
    from datetime import date
    from src.models import TravelRequest

    monkeypatch.setenv("RAILRADAR_API_KEY", "test-key")

    def fake_get_json(path, api_key, params=None):
        return {
            "success": True,
            "data": {
                "from": {"code": "BL", "name": "Valsad"},
                "to": {"code": "ST", "name": "Surat"},
                "trains": [{
                    "train": {"number": "12345", "name": "Unverified segment"},
                    "from": {"departure": "16:00", "day": 1},
                    "to": {"arrival": "16:47", "day": 1},
                    "duration": 47,
                }],
            },
        }

    monkeypatch.setattr(rail_api, "_get_json", fake_get_json)
    request = TravelRequest(
        origin="Valsad (BL)", destination="Surat (ST)",
        travel_date=date(2026, 10, 19), budget_inr=500, mode="train"
    )
    options, error = rail_api.fetch_provider_options(request)
    assert options == []
    assert error is not None and "no validated train segments" in error.lower()
