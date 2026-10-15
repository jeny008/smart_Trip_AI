from src.genai_workflow import retrieve_travel_context


def test_rag_retrieves_fare_limitation_for_budget_question():
    result = retrieve_travel_context("Can I find a train under ₹500? fare budget")
    assert "fare" in result.lower()
    assert "budget" in result.lower()


def test_rag_retrieves_route_validation_guidance():
    result = retrieve_travel_context("validate station codes and train route segment")
    assert "station" in result.lower() or "route" in result.lower()


def test_rag_has_fallback_for_unknown_query():
    result = retrieve_travel_context("xyzzy qqqq unrelated query")
    assert isinstance(result, str)
    assert result
