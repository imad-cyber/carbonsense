"""
ADEME Base Carbone import, step by step.

  python scripts/import_ademe.py fetch    # API -> data/base_carbone.jsonl (+ meta file)
  python scripts/import_ademe.py report   # analyse the saved file; writes ademe_report.txt (no DB access)
"""
import json
import os
import re
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8")

from app.ingest.ademe import (
    SKIP_NOT_ELEMENT, SKIP_UNIT_FORMAT, SOURCE,
    clean_text, norm, parse_component, parse_row, to_float,
)

API_BASE = "https://data.ademe.fr/data-fair/api/v1/datasets/base-carboner"
DATA_FILE = Path("data/base_carbone.jsonl")
META_FILE = Path("data/base_carbone.meta.json")
REPORT_FILE = Path("ademe_report.txt")
PAGE_SIZE = 1000


def fetch() -> None:
    import httpx

    DATA_FILE.parent.mkdir(exist_ok=True)
    with httpx.Client(timeout=60, follow_redirects=True) as client:
        meta = client.get(API_BASE).json()
        expected = meta.get("count")
        url, params = f"{API_BASE}/lines", {"size": PAGE_SIZE}
        n = 0
        with DATA_FILE.open("w", encoding="utf-8") as out:
            while url:
                resp = client.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()
                results = data.get("results", [])
                for row in results:
                    out.write(json.dumps(row, ensure_ascii=False) + "\n")
                n += len(results)
                print(f"fetched {n} / {expected}")
                url, params = (data.get("next") if results else None), None

    if expected is not None and n != expected:
        sys.exit(f"ERROR: fetched {n} rows but the API reports {expected}. Not trusting this file.")

    META_FILE.write_text(
        json.dumps(
            {
                "title": meta.get("title"),
                "count": expected,
                "dataUpdatedAt": meta.get("dataUpdatedAt"),
                "fetchedAt": datetime.now(timezone.utc).isoformat(),
                "api": API_BASE,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print("saved", DATA_FILE)


def _top(counter: Counter, n: int) -> list[str]:
    return [f"  {c:>6}  {v}" for v, c in counter.most_common(n)]


def _brief(v: dict) -> str:
    keys = [
        "identifiant_de_l_element", "nom_base_francais", "unite_francais", "type_poste",
        "nom_poste_francais", "total_poste_non_decompose", "co2f", "ch4f", "ch4b", "n2o",
        "co2b", "autres_ges",
    ]
    return json.dumps({k: v.get(k) for k in keys if v.get(k) not in (None, "")}, ensure_ascii=False)


def report() -> None:
    with DATA_FILE.open(encoding="utf-8") as fh:
        rows = [json.loads(line) for line in fh]
    meta = json.loads(META_FILE.read_text(encoding="utf-8"))
    views = [{norm(k): v for k, v in r.items()} for r in rows]

    out: list[str] = []
    add = out.append

    def is_element(v):
        return norm(v.get("type_ligne") or "") == "element"

    add(f"rows in file: {len(rows)} | API count: {meta['count']} | dataUpdatedAt: {meta['dataUpdatedAt']}")

    add("\n== ROW TYPES (Type_Ligne, Type de l'élément) ==")
    types = Counter((clean_text(v.get("type_ligne")), clean_text(v.get("type_de_l_element"))) for v in views)
    out += [f"  {c:>6}  {a} / {b}" for (a, b), c in types.most_common()]

    add("\n== ELEMENT+FACTOR ROWS BY STRUCTURE: is a total present? ==")
    by_struct = Counter()
    for v in views:
        if is_element(v) and norm(v.get("type_de_l_element") or "") == "facteur_d_emission":
            has = to_float(v.get("total_poste_non_decompose")) is not None
            by_struct[(clean_text(v.get("structure")), "total" if has else "NO total")] += 1
    out += [f"  {c:>6}  {s} | {t}" for (s, t), c in sorted(by_struct.items())]

    parsed, skipped, odd_units = [], Counter(), Counter()
    for r, v in zip(rows, views):
        p, reason = parse_row(r)
        if p:
            parsed.append(p)
        else:
            skipped[reason] += 1
            if reason == SKIP_UNIT_FORMAT:
                odd_units[clean_text(v.get("unite_francais"))] += 1

    add(f"\n== IMPORTABLE: {len(parsed)} of {len(rows)} rows ==")
    add("skipped, by reason:")
    out += _top(skipped, 20)
    add("skipped for unit format (top 20 raw units):")
    out += _top(odd_units, 20)

    valid = [p for p in parsed if p.status and not norm(p.status).startswith("archive")]
    add(f"\nimportable by status:")
    out += _top(Counter(p.status for p in parsed), 10)
    add("importable by geography:")
    out += _top(Counter(p.geography for p in parsed), 10)

    by_id = defaultdict(list)
    for p in parsed:
        by_id[p.source_id].append(p)
    dups = {k: v for k, v in by_id.items() if len(v) > 1}
    add(f"\ndistinct ids: {len(by_id)} | ids appearing more than once: {len(dups)}")
    for k, v in list(dups.items())[:5]:
        add(f"  id {k}: " + " | ".join(f"{p.kg_co2e_per_unit} {p.unit} [{p.status}]" for p in v))

    add(f"\nmax name length: {max(len(p.name) for p in parsed)} (over 500: {sum(len(p.name) > 500 for p in parsed)})")
    add(f"max unit length: {max(len(p.unit) for p in parsed)} (over 50: {sum(len(p.unit) > 50 for p in parsed)})")

    add(f"\n== UNITS: {len(Counter(p.unit for p in parsed))} distinct; top 40 overall ==")
    out += _top(Counter(p.unit for p in parsed), 40)
    add(f"top 30 among non-archived ({len(valid)} factors):")
    out += _top(Counter(p.unit for p in valid), 30)

    add("\n== UNCERTAINTY (Incertitude) ==")
    for label, group in (("all importable", parsed), ("non-archived", valid)):
        vals = [p.uncertainty_pct for p in group if p.uncertainty_pct is not None]
        if vals:
            add(f"  {label}: {len(vals)} of {len(group)} have a value | min {min(vals)} | "
                f"median {statistics.median(vals)} | max {max(vals)}")
        else:
            add(f"  {label}: none have a value")

    totals = [p.kg_co2e_per_unit for p in parsed]
    add(f"\n== TOTALS: min {min(totals)} | max {max(totals)} | zero {sum(t == 0 for t in totals)} | "
        f"negative {sum(t < 0 for t in totals)} ==")

    add("\n== CATEGORY, first level (non-archived) ==")
    out += _top(Counter((p.category_path or "(none)").split(">")[0].strip() for p in valid), 15)

    add("\n== POSTE ROWS vs ELEMENT ROWS ==")
    posts_by_id = defaultdict(list)
    for v in views:
        if norm(v.get("type_ligne") or "") == "poste":
            posts_by_id[clean_text(v.get("identifiant_de_l_element"))].append(v)
    element_ids = {clean_text(v.get("identifiant_de_l_element")) for v in views if is_element(v)}
    n_poste = sum(len(x) for x in posts_by_id.values())
    linked = sum(len(x) for k, x in posts_by_id.items() if k in element_ids)
    add(f"  poste rows: {n_poste} | sharing an id with an element row: {linked}")

    add("\n== SAMPLES OF DECOMPOSED ELEMENTS (one per structure) ==")
    seen = set()
    for v in views:
        s = norm(v.get("structure") or "")
        if not is_element(v) or not s.startswith("element_decompose") or s in seen:
            continue
        seen.add(s)
        add(f"\n  structure: {clean_text(v.get('structure'))}")
        add(f"    element: {_brief(v)}")
        for post in posts_by_id.get(clean_text(v.get("identifiant_de_l_element")), [])[:4]:
            add(f"    poste:   {_brief(post)}")

    add("\n== SPOT CHECKS (non-archived, shortest names first) ==")

    def spot(label: str, name_pattern: str, unit_hint: str, n: int = 6) -> None:
        rx = re.compile(name_pattern)
        hits = [p for p in valid if rx.search(norm(p.name)) and unit_hint in p.unit.lower()]
        add(f"\n  {label}: {len(hits)} matches")
        for p in sorted(hits, key=lambda p: len(p.name))[:n]:
            add(f"    id {p.source_id} | {p.name[:80]} | {p.kg_co2e_per_unit} kgCO2e/{p.unit} | "
                f"{p.geography} | uncertainty {p.uncertainty_pct}")

    spot("electricity", "electricite", "kwh")
    spot("natural gas", "gaz_naturel", "kwh")
    spot("diesel", "gazole", "litre")
    spot("fuel oil", "fioul", "litre")
    spot("petrol", "essence", "litre")

    REPORT_FILE.write_text("\n".join(out), encoding="utf-8")
    print(f"wrote {REPORT_FILE} ({len(out)} lines)")


def _chunks(items: list, size: int = 1000):
    for i in range(0, len(items), size):
        yield items[i : i + size]


def load() -> None:
    """
    Insert-only and idempotent per version: factors from this snapshot are added once.
    A newer snapshot gets a new version string, so older factors stay in place and
    existing emission records keep pointing at exactly what they were calculated with.
    """
    from sqlalchemy import insert
    from app.db.database import SessionLocal
    from app.models.emission_factor import EmissionFactor, EmissionFactorComponent

    meta = json.loads(META_FILE.read_text(encoding="utf-8"))
    version = f"base-carbone@{meta['dataUpdatedAt'][:10]}"
    with DATA_FILE.open(encoding="utf-8") as fh:
        rows = [json.loads(line) for line in fh]

    factors, components, skipped = {}, defaultdict(list), Counter()
    for row in rows:
        factor, reason = parse_row(row)
        if factor:
            factors[factor.source_id] = factor
            continue
        if reason == SKIP_NOT_ELEMENT:
            component, reason = parse_component(row)
            if component:
                components[component.source_id].append(component)
                continue
        skipped[reason] += 1
    orphans = sum(len(v) for k, v in components.items() if k not in factors)

    db = SessionLocal()
    try:
        scope = (EmissionFactor.source == SOURCE, EmissionFactor.source_version == version)
        existing = {sid for (sid,) in db.query(EmissionFactor.source_id).filter(*scope)}
        new = [f for sid, f in factors.items() if sid not in existing]
        print(f"{version}: {len(factors)} parsed | {len(existing)} already loaded | {len(new)} to insert")

        for chunk in _chunks(new):
            db.execute(insert(EmissionFactor), [
                {
                    "source": SOURCE, "source_id": f.source_id, "source_version": version,
                    "name": f.name, "unit": f.unit, "kg_co2e_per_unit": f.kg_co2e_per_unit,
                    "uncertainty_pct": f.uncertainty_pct, "geography": f.geography,
                    "sub_geography": f.sub_geography, "status": f.status,
                    "category_path": f.category_path, "valid_until": f.valid_until,
                    "raw": f.raw,
                }
                for f in chunk
            ])
        db.flush()

        id_map = dict(db.query(EmissionFactor.source_id, EmissionFactor.id).filter(*scope))
        new_ids = {f.source_id for f in new}
        comp_rows = [
            {
                "emission_factor_id": id_map[sid], "post_type": c.post_type,
                "post_name": c.post_name, "kg_co2e_per_unit": c.kg_co2e_per_unit,
                "gases": c.gases or None,
            }
            for sid, cs in components.items() if sid in new_ids
            for c in cs
        ]
        for chunk in _chunks(comp_rows):
            db.execute(insert(EmissionFactorComponent), chunk)
        db.commit()
        print(f"inserted {len(new)} factors and {len(comp_rows)} components")
        print(f"skipped rows: {dict(skipped)} | component rows without a factor: {orphans}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def verify() -> None:
    """Checks the loaded data and writes ademe_verify.txt."""
    from sqlalchemy import func, text
    from app.db.database import SessionLocal
    from app.models.emission_factor import EmissionFactor

    db = SessionLocal()
    out: list[str] = []
    add = out.append
    try:
        add("== FACTORS BY VERSION / STATUS ==")
        for version, status, n in db.execute(text(
            "SELECT source_version, COALESCE(status, '(none)'), COUNT(*) FROM emission_factors "
            "WHERE source = :s GROUP BY 1, 2 ORDER BY 1, 2"), {"s": SOURCE}):
            add(f"  {n:>6}  {version} | {status}")
        add(f"components: {db.execute(text('SELECT COUNT(*) FROM emission_factor_components')).scalar()}")

        add("\n== DO THE COMPONENTS ADD UP TO THE FACTOR'S TOTAL? (tolerance 2%) ==")
        rows = db.execute(text(
            "SELECT f.source_id, f.name, f.unit, f.kg_co2e_per_unit AS total, "
            "SUM(c.kg_co2e_per_unit) AS parts "
            "FROM emission_factors f JOIN emission_factor_components c "
            "ON c.emission_factor_id = f.id WHERE f.source = :s GROUP BY f.id"), {"s": SOURCE}).all()
        bad = [r for r in rows if abs(r.parts - r.total) > 0.02 * abs(r.total) + 1e-9]
        add(f"factors with components: {len(rows)} | not adding up: {len(bad)}")
        for r in sorted(bad, key=lambda r: -abs(r.parts - r.total))[:10]:
            add(f"  id {r.source_id} | {r.name[:60]} | total {r.total} | parts {r.parts}")

        def show(label: str, name_like: str, unit: str) -> None:
            hits = (
                db.query(EmissionFactor)
                .filter(
                    EmissionFactor.source == SOURCE,
                    EmissionFactor.name.ilike(name_like),
                    func.lower(EmissionFactor.unit) == unit.lower(),
                    EmissionFactor.geography == "France continentale",
                    EmissionFactor.status.notilike("archiv%"),
                )
                .order_by(func.length(EmissionFactor.name))
                .limit(4)
                .all()
            )
            add(f"\n== {label}: first {len(hits)} non-archived, France continentale ==")
            for f in hits:
                add(f"  db id {f.id} | ademe id {f.source_id} | {f.name} | {f.sub_geography} | "
                    f"{f.kg_co2e_per_unit} kgCO2e/{f.unit} | uncertainty {f.uncertainty_pct} | {f.status}")
                for c in f.components:
                    add(f"      {c.post_type} / {c.post_name}: {c.kg_co2e_per_unit}  {c.gases}")

        show("ELECTRICITY", "%lectricit%mix moyen%", "kWh")
        show("NATURAL GAS (PCS)", "%gaz naturel%", "kWh PCS")
        show("NATURAL GAS (PCI)", "%gaz naturel%", "kWh PCI")
        show("DIESEL", "%gazole%", "litre")
        show("PETROL", "%essence%", "litre")
    finally:
        db.close()

    REPORT = Path("ademe_verify.txt")
    REPORT.write_text("\n".join(out), encoding="utf-8")
    print(f"wrote {REPORT} ({len(out)} lines)")


def posts() -> None:
    """Which post types exist per factor category, and which factors the allocation rules can book."""
    from sqlalchemy import or_
    from app.db.database import SessionLocal
    from app.models.emission import EmissionScope
    from app.models.emission_factor import EmissionFactor, EmissionFactorComponent
    from app.services.allocation import DIRECT_POSTS, ENERGY_RELATED_POSTS
    from collections import defaultdict, Counter
    from app.ingest.ademe import norm, SOURCE
    import pathlib

    db = SessionLocal()
    try:
        rows = (
            db.query(
                EmissionFactor.id, EmissionFactor.name, EmissionFactor.unit,
                EmissionFactor.kg_co2e_per_unit.label("total"),
                EmissionFactor.category_path, EmissionFactorComponent.post_type,
            )
            .join(EmissionFactorComponent, EmissionFactorComponent.emission_factor_id == EmissionFactor.id)
            .filter(
                EmissionFactor.source == SOURCE,
                or_(EmissionFactor.status.is_(None), ~EmissionFactor.status.ilike("archiv%")),
            )
            .all()
        )
    finally:
        db.close()

    by_factor, info = defaultdict(set), {}
    for r in rows:
        by_factor[r.id].add(r.post_type)
        info[r.id] = (r.name, r.unit, r.total, (r.category_path or "(none)").split(">")[0].strip())

    out = ["== POST TYPES BY TOP-LEVEL CATEGORY (non-archived factors with components) =="]
    by_top = defaultdict(Counter)
    for fid, ps in by_factor.items():
        for p in ps:
            by_top[info[fid][3]][p] += 1
    for top, counter in sorted(by_top.items()):
        out.append(f"\n  {top}  ({sum(1 for i in info.values() if i[3] == top)} factors)")
        out += [f"    {n:>5}  {p}" for p, n in counter.most_common()]

    rules = {
        "Combustibles": DIRECT_POSTS[EmissionScope.SCOPE_1],
        "Electricité": DIRECT_POSTS[EmissionScope.SCOPE_2],
    }
    out.append("\n== CAN THE ALLOCATION RULES BOOK THESE FACTORS? ==")
    for top, direct in rules.items():
        known = direct | ENERGY_RELATED_POSTS
        ids = [f for f, i in info.items() if i[3] == top]
        normed = {f: {norm(p) for p in by_factor[f]} for f in ids}
        ok = [f for f in ids if normed[f] <= known and normed[f] & direct]
        unknown = [f for f in ids if not normed[f] <= known]
        no_direct = [f for f in ids if normed[f] <= known and not normed[f] & direct]
        out.append(
            f"\n  {top}: {len(ok)} bookable | {len(unknown)} with unhandled posts | "
            f"{len(no_direct)} with no direct post (of {len(ids)})"
        )
        for label, group in (("unhandled posts", unknown), ("no direct post", no_direct)):
            for f in group[:12]:
                name, unit, total, _ = info[f]
                out.append(
                    f"      [{label}] db id {f} | {name[:70]} | {total} kgCO2e/{unit} | {sorted(by_factor[f])}"
                )

    pathlib.Path("ademe_posts.txt").write_text("\n".join(out), encoding="utf-8")
    print(f"wrote ademe_posts.txt ({len(out)} lines)")


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) == 2 else ""
    {"fetch": fetch, "report": report, "load": load, "verify": verify, "posts": posts}.get(
        command, lambda: print(__doc__)
    )()
