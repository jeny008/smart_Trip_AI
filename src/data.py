from datetime import date, datetime, time, timedelta
from src.models import TravelOption, TravelRequest

def get_demo_options(request: TravelRequest) -> list[TravelOption]:
    """Return explicitly fictional options for UI and comparison testing."""
    base = datetime.combine(request.travel_date, time(7, 0))
    candidates = [
        ("Demo Train A", "train", 420, 650),
        ("Demo Bus B", "bus", 510, 450),
        ("Demo Flight C", "flight", 100, 2400),
        ("Demo Train D", "train", 480, 520),
    ]
    options: list[TravelOption] = []
    for provider, mode, duration, price in candidates:
        if request.mode != "any" and request.mode != mode:
            continue
        options.append(TravelOption(
            provider=provider,
            mode=mode,
            origin=request.origin,
            destination=request.destination,
            departure=base,
            arrival=base + timedelta(minutes=duration),
            price_inr=price,
            source="DEMO DATA — fictional example; not a real schedule or fare",
            is_demo=True,
        ))
    return options
