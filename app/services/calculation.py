from dataclasses import dataclass
from app.services.units import convert_quantity


@dataclass(frozen=True)
class Calculation:
    co2_tonnes: float
    quantity_in_factor_unit: float
    uncertainty_pct: float | None
    co2_tonnes_low: float | None
    co2_tonnes_high: float | None


def calculate_emissions(
    quantity: float,
    activity_unit: str,
    factor_kg_co2e_per_unit: float,
    factor_unit: str,
    uncertainty_pct: float | None = None,
) -> Calculation:
    """
    emissions = activity quantity x emission factor.
    The uncertainty range reflects the FACTOR's stated uncertainty only;
    error in the activity data itself is not modelled.
    """
    if quantity < 0:
        raise ValueError("Activity quantity cannot be negative")
    if factor_kg_co2e_per_unit < 0:
        raise ValueError(
            "This factor is negative (removals / avoided emissions); not supported"
        )

    q = convert_quantity(quantity, activity_unit, factor_unit)
    tonnes = q * factor_kg_co2e_per_unit / 1000.0

    low = high = None
    if uncertainty_pct is not None:
        low = max(tonnes * (1 - uncertainty_pct / 100.0), 0.0)
        high = tonnes * (1 + uncertainty_pct / 100.0)

    return Calculation(tonnes, q, uncertainty_pct, low, high)
