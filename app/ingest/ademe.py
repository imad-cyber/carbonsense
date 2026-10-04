"""
Parsing of ADEME Base Carbone rows (data.ademe.fr dataset 'base-carboner').

Only 'Elément' rows of type "Facteur d'émission" that carry a total in
'Total poste non décomposé' and a 'kgCO2e/<unit>' unit are importable.
Everything else is skipped with a reason, so nothing disappears silently.
"""
import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime
from functools import lru_cache

SOURCE = "ADEME_BASE_CARBONE"

SKIP_NOT_ELEMENT = "not_an_element_row"
SKIP_NOT_FACTOR = "not_an_emission_factor"
SKIP_NO_ID = "missing_id"
SKIP_NO_NAME = "missing_name"
SKIP_NO_UNIT = "missing_unit"
SKIP_UNIT_FORMAT = "unit_not_kgco2e_per_something"
SKIP_NO_TOTAL = "missing_total"


@lru_cache(maxsize=8192)
def norm(text: str) -> str:
    """Accent-, case- and punctuation-insensitive key: "Unité_français" -> "unite_francais"."""
    text = unicodedata.normalize("NFKD", str(text))
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def clean_text(value) -> str:
    """Drop the stray quotes and tabs found in ADEME names; collapse whitespace."""
    if value is None:
        return ""
    return re.sub(r"\s+", " ", re.sub(r'["\t]+', " ", str(value))).strip()


def full_name(base, attribute, boundary) -> str:
    parts = [clean_text(p) for p in (base, attribute, boundary)]
    return " - ".join(p for p in parts if p)


_UNIT_RE = re.compile(r"^\s*kgCO2e\s*/\s*(?P<unit>.+?)\s*$", re.IGNORECASE)


def parse_factor_unit(value) -> str | None:
    """'kgCO2e/kg de poids net' -> 'kg de poids net'. None if not a kgCO2e/<unit> string."""
    match = _UNIT_RE.match(clean_text(value))
    return match.group("unit") if match else None


def parse_date(value) -> date | None:
    text = clean_text(value)
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def to_float(value) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", ".")
    try:
        return float(text) if text else None
    except ValueError:
        return None


@dataclass
class ParsedFactor:
    source_id: str
    name: str
    unit: str
    kg_co2e_per_unit: float
    uncertainty_pct: float | None
    geography: str | None
    status: str | None
    category_path: str | None
    valid_until: date | None
    raw: dict


def parse_row(row: dict) -> tuple[ParsedFactor | None, str | None]:
    """Returns (factor, None) if importable, else (None, reason)."""
    r = {norm(k): v for k, v in row.items()}

    if norm(r.get("type_ligne") or "") != "element":
        return None, SKIP_NOT_ELEMENT
    if norm(r.get("type_de_l_element") or "") != "facteur_d_emission":
        return None, SKIP_NOT_FACTOR

    source_id = clean_text(r.get("identifiant_de_l_element"))
    if not source_id:
        return None, SKIP_NO_ID

    name = full_name(
        r.get("nom_base_francais"), r.get("nom_attribut_francais"), r.get("nom_frontiere_francais")
    )
    if not name:
        return None, SKIP_NO_NAME

    raw_unit = clean_text(r.get("unite_francais"))
    if not raw_unit:
        return None, SKIP_NO_UNIT
    unit = parse_factor_unit(raw_unit)
    if unit is None:
        return None, SKIP_UNIT_FORMAT

    total = to_float(r.get("total_poste_non_decompose"))
    if total is None:
        return None, SKIP_NO_TOTAL

    return ParsedFactor(
        source_id=source_id,
        name=name,
        unit=unit,
        kg_co2e_per_unit=total,
        uncertainty_pct=to_float(r.get("incertitude")),
        geography=clean_text(r.get("localisation_geographique")) or None,
        status=clean_text(r.get("statut_de_l_element")) or None,
        category_path=clean_text(r.get("code_de_la_categorie")) or None,
        valid_until=parse_date(r.get("periode_de_validite")),
        raw={k: v for k, v in row.items() if not k.startswith("_")},
    ), None
