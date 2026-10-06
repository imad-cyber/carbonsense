"""
Allocation of an emission factor's posts to GHG Protocol scopes.

ADEME publishes fuel and electricity factors as a total made of posts (e.g.
'Combustion' + 'Amont'). The total includes upstream emissions (extraction,
refining, transport; grid losses) that are not Scope 1 or 2. In the V23.6
snapshot, booking the whole total as Scope 1 overstates it by about 1.2x (gas),
1.25x (road diesel) and 3x (E85).

Policy (change it here and nowhere else):
  Scope 1 fuel   : 'Combustion'                 -> Scope 1
  Scope 2 power  : 'Combustion à la centrale'   -> Scope 2 (location-based)
  Both           : 'Amont', 'Transport et distribution' (grid losses)
                                                -> Scope 3, fuel- and energy-related
Unknown post types are refused, never guessed.
"""
from dataclasses import dataclass

from app.ingest.ademe import norm
from app.models.emission import EmissionCategory, EmissionScope

S1, S2, S3 = EmissionScope.SCOPE_1, EmissionScope.SCOPE_2, EmissionScope.SCOPE_3

# Normalised post types (see app.ingest.ademe.norm)
DIRECT_POSTS = {S1: {"combustion"}, S2: {"combustion_a_la_centrale"}}
ENERGY_RELATED_POSTS = {"amont", "transport_et_distribution"}

_SPLIT = {
    (S1, EmissionCategory.STATIONARY_COMBUSTION),
    (S1, EmissionCategory.MOBILE_COMBUSTION),
    (S2, EmissionCategory.PURCHASED_ELECTRICITY),
}
_UNREVIEWED = {(S2, EmissionCategory.PURCHASED_HEAT)}
_TOLERANCE = 0.02


class AllocationError(ValueError):
    pass


@dataclass(frozen=True)
class Slice:
    scope: EmissionScope
    category: EmissionCategory
    post_type: str
    kg_co2e_per_unit: float


@dataclass(frozen=True)
class AllocationPlan:
    slices: list[Slice]
    warnings: list[str]


def plan_allocation(scope, category, total_kg_per_unit, components) -> AllocationPlan:
    """components: objects with .post_type and .kg_co2e_per_unit."""
    key = (scope, category)
    components = list(components)
    whole = Slice(scope, category, "total", total_kg_per_unit)

    if key in _UNREVIEWED and components:
        raise AllocationError(
            "District heat/cold factors with a breakdown are not supported yet: "
            "their posts have not been reviewed for scope allocation."
        )
    if key not in _SPLIT:
        return AllocationPlan([whole], [])
    if not components:
        return AllocationPlan([whole], [
            "This factor has no published breakdown, so its total is booked as given. "
            "It may include upstream emissions that belong in Scope 3."
        ])

    direct, related, unknown = [], [], []
    for c in components:
        k = norm(c.post_type)
        if k in DIRECT_POSTS[scope]:
            direct.append(c)
        elif k in ENERGY_RELATED_POSTS:
            related.append(c)
        else:
            unknown.append(c.post_type)
    if unknown:
        raise AllocationError(
            f"Cannot allocate this factor: unhandled post type(s) {sorted(set(unknown))}. "
            "Choose another factor or extend the allocation policy."
        )
    if not direct:
        raise AllocationError("Cannot allocate this factor: it has no direct (combustion) post.")

    parts = sum(c.kg_co2e_per_unit for c in components)
    if abs(parts - total_kg_per_unit) > _TOLERANCE * abs(total_kg_per_unit) + 1e-9:
        raise AllocationError(
            f"The factor's posts ({parts:g}) do not add up to its total ({total_kg_per_unit:g})."
        )

    slices = [Slice(scope, category, c.post_type, c.kg_co2e_per_unit) for c in direct]
    slices += [
        Slice(S3, EmissionCategory.FUEL_ENERGY_RELATED, c.post_type, c.kg_co2e_per_unit)
        for c in related if c.kg_co2e_per_unit != 0
    ]
    return AllocationPlan(slices, [])
