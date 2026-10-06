import calendar
from datetime import date


def _period_end(year: int, month: int | None) -> date:
    if month is None:
        return date(year, 12, 31)
    return date(year, month, calendar.monthrange(year, month)[1])


def factor_warnings(
    *,
    status: str | None,
    valid_until: date | None,
    uncertainty_pct: float | None,
    reporting_year: int,
    reporting_month: int | None = None,
) -> list[str]:
    """Things a reviewer should know about a factor chosen for a given reporting period."""
    warnings = []
    if status and status.lower().startswith("archiv"):
        warnings.append(
            "This factor is archived by its publisher. Prefer a currently valid factor "
            "unless you are reproducing a past report."
        )
    if valid_until:
        end = _period_end(reporting_year, reporting_month)
        if end > valid_until:
            warnings.append(
                f"The publisher's stated validity date for this factor ({valid_until.isoformat()}) "
                f"is earlier than the end of the reporting period ({end.isoformat()})."
            )
    if uncertainty_pct is None:
        warnings.append("The publisher gives no uncertainty for this factor, so no range is shown.")
    return warnings
