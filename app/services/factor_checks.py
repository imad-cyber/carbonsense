from datetime import date


def factor_warnings(
    *,
    status: str | None,
    valid_until: date | None,
    uncertainty_pct: float | None,
    reporting_year: int,
) -> list[str]:
    """Things a reviewer should know about a factor chosen for a given reporting year."""
    warnings = []
    if status and status.lower().startswith("archiv"):
        warnings.append(
            "This factor is archived by its publisher. Prefer a currently valid factor "
            "unless you are reproducing a past report."
        )
    if valid_until and reporting_year > valid_until.year:
        warnings.append(
            f"The publisher's stated validity date ({valid_until.isoformat()}) is earlier "
            f"than the reporting year {reporting_year}."
        )
    if uncertainty_pct is None:
        warnings.append("The publisher gives no uncertainty for this factor, so no range is shown.")
    return warnings
