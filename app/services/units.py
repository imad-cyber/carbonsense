"""
Unit handling for activity data.

Rule: convert only inside a known dimension (energy, mass, volume, distance).
Everything else must match exactly. Different measurement bases are different units:
'kWh' vs 'kWh PCI' (a heating-value basis) are NOT converted, because treating
them as equal would silently bias results.
"""
import re


class UnitMismatchError(ValueError):
    pass


_DIMENSIONS = {
    "energy": {"kwh": 1.0, "mwh": 1_000.0, "gwh": 1_000_000.0},
    "mass": {"kg": 1.0, "t": 1_000.0},
    "volume": {"l": 1.0, "m3": 1_000.0},
    "distance": {"km": 1.0, "m": 0.001},
}
_ALIASES = {
    "litre": "l", "litres": "l", "liter": "l", "liters": "l",
    "m³": "m3", "tonne": "t", "tonnes": "t",
}
_LOOKUP = {
    unit: (dim, factor)
    for dim, units in _DIMENSIONS.items()
    for unit, factor in units.items()
}


def normalize_unit(unit: str) -> str:
    u = re.sub(r"\s+", " ", unit.strip().lower())
    return _ALIASES.get(u, u)


def convert_quantity(quantity: float, from_unit: str, to_unit: str) -> float:
    a, b = normalize_unit(from_unit), normalize_unit(to_unit)
    if a == b:
        return quantity
    if a in _LOOKUP and b in _LOOKUP and _LOOKUP[a][0] == _LOOKUP[b][0]:
        return quantity * _LOOKUP[a][1] / _LOOKUP[b][1]
    raise UnitMismatchError(
        f"Cannot convert '{from_unit}' to '{to_unit}'. Provide the activity in the "
        f"factor's unit or in a convertible unit of the same kind."
    )
