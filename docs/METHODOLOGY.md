# Methodology

## Calculation
Emissions = activity quantity x emission factor (kg CO2e per unit).
Factors come from ADEME Base Carbone, version V23.6 (snapshot of 2025-07-03), Licence Ouverte 2.0.
Every record stores the factor id, its version, the value actually used, and which post of the
factor it came from, so figures stay reproducible if factors are later updated.

## Allocation of factor posts to scopes
See `app/services/allocation.py` (the single place to change it):
- Scope 1 fuel: "Combustion" is Scope 1.
- Scope 2 electricity: "Combustion à la centrale" is Scope 2, location-based.
- "Amont" (upstream) and "Transport et distribution" (grid losses) are Scope 3,
  category "fuel- and energy-related" (not in Scope 1 or 2).
- Unreviewed post types and district heat/cold factors with posts are refused.
Booking a factor's total as Scope 1 would overstate it by about 1.2x (gas), 1.25x (diesel), 3x (E85).

## Known limitations
- Location-based Scope 2 only; market-based Scope 2 is not supported.
- Biogenic CO2 is outside ADEME's totals and is not recorded.
- Uncertainty is the factor's published value, applied to each post. Activity-data error is not
  modelled, and about half of the factors publish no uncertainty.
- Allocation of grid losses to Scope 3 follows secondary sources; confirm against ADEME's guidance.
- The factor snapshot is V23.6 (July 2025); newer releases are imported as new versions.

- The organisational boundary (operational control) is the user's responsibility. Sites outside it should not be booked as Scope 1/2; a published filing books such a site's electricity at the factor's full value under "other indirect".
- Refrigerant factors depend on the GWP vintage of the Base Carbone version (IPCC report); results can differ from filings that used an older version.
