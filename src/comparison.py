from src.models import TravelOption, TravelRequest

def compare_options(request: TravelRequest, options: list[TravelOption]) -> dict:
    known = [option for option in options if option.price_inr is not None]
    within_budget = [
        option for option in known
        if request.budget_inr is None or option.price_inr <= request.budget_inr
    ]
    ranked = sorted(within_budget, key=lambda option: (option.price_inr, option.duration_minutes))
    fastest = min(within_budget, key=lambda option: option.duration_minutes, default=None)
    return {
        "options": sorted(options, key=lambda option: (
            option.price_inr is None,
            option.price_inr if option.price_inr is not None else float("inf"),
            option.duration_minutes,
        )),
        "within_budget": ranked,
        "cheapest": ranked[0] if ranked else None,
        "fastest_affordable": fastest,
        "over_budget": [
            option for option in known
            if request.budget_inr is not None and option.price_inr > request.budget_inr
        ],
        "missing_prices": [option for option in options if option.price_inr is None],
    }
