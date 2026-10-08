"""Groups per-record anomaly scores into one finding per activity entry."""

_RANK = {"high": 3, "medium": 2, "low": 1, None: 0}


def group_findings(results: list[dict]) -> list[dict]:
    """
    One input (e.g. a month of gas consumption) creates several records: a direct one and
    its upstream part. They share a quantity, so they are flagged together. A finding reports
    them once, with the strongest severity among its flagged records.
    """
    groups: dict[str, list[dict]] = {}
    for r in results:
        key = r.get("activity_group_id") or f"record:{r['record_id']}"
        groups.setdefault(key, []).append(r)

    findings = []
    for rows in groups.values():
        flagged = [r for r in rows if r["is_anomaly"]]
        if not flagged:
            continue
        top = max(flagged, key=lambda r: _RANK[r["anomaly_severity"]])
        findings.append({
            "activity_group_id": rows[0].get("activity_group_id"),
            "reporting_year": rows[0]["reporting_year"],
            "reporting_month": rows[0]["reporting_month"],
            "severity": top["anomaly_severity"],
            "times_series_median": top["times_series_median"],
            "total_co2_tonnes": round(sum(r["co2_tonnes"] for r in rows), 3),
            "records": [
                {
                    "record_id": r["record_id"], "scope": r["scope"],
                    "category": r["category"], "co2_tonnes": r["co2_tonnes"],
                    "is_anomaly": r["is_anomaly"],
                }
                for r in rows
            ],
        })
    return sorted(
        findings,
        key=lambda f: (-_RANK[f["severity"]], f["reporting_year"], f["reporting_month"]),
    )
