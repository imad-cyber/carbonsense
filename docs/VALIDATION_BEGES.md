# Validation against a published BEGES

**Source:** Salesforce.com France, BEGES for financial year 2023 (public filing):
https://www.salesforce.com/en-us/wp-content/uploads/sites/4/documents/legal/misc/BEGES_Salesforce_2023.pdf
Activity data, factors and results were transcribed from its two pages.
**Reproduce:** `python scripts/reproduce_beges.py` (factors from ADEME Base Carbone V23.6).

- [x] Transcription checked against the PDF by: Antigravity on 2026-10-09

## Lines reproduced with Base Carbone factors

| Line | Activity | Factor (Base Carbone V23.6) | CarbonSense | Filing |
|---|---|---|---|---|
| 1.1 Fixed combustion, natural gas | 12,978 kWh PCI | 0.201 kgCO2e/kWh PCI (combustion, id 37132) | 2.61 t | 2.61 t |
| 2.1 Electricity, operated grid sites | 5,357,920 kWh | 0.0338 kgCO2e/kWh (generation, id 42513) | 181.10 t | 181.10 t |

The loaded electricity factor has the same three components as the filing (0.0338, 0.0135, 0.00474).
The gas upstream component differs by -1.8% (0.0382 against 0.0389); it is not part of line 1.1.

## Lines checked by arithmetic only (factor as printed in the filing, not looked up)

Steam 529,437 kWh x 0.18 = 95.30 t; non-operated site 83,432 kWh x 0.05204 = 4.34 t;
refrigerants 63.261 kg x 4,800 + 18.483 kg x 1,920 = 339.14 t.

## What this shows
- Scope 1 books the combustion factor only; Scope 2 books generation only.
  Line 2.1 equals kWh x 0.0338, so upstream and grid losses are not in it.
- Biogenic CO2 is reported outside the totals; unit handling and factor import agree with the filing.

## What this does not show
- One filing is one example, not a proof that the allocation policy is right in general.
- The purchases line (4.1, about 2,270 t) and the diesel line are not reproduced (no spend data;
  diesel inputs not legible in the transcription).
- Non-operated sites (booked at the full factor under "other indirect") are not modelled.
