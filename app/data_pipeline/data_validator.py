"""
Data quality validation for emission records — Great Expectations style,
implemented from scratch to avoid the heavy dependency.

Each rule returns a ValidationResult(passed, rule, message, severity).
validate_batch() runs everything against a list of records and splits
them into valid/invalid sets with reasons.
"""
import logging
from dataclasses import dataclass, field
from datetime import date

logger = logging.getLogger(__name__)

# Plausible upper bounds in tonnes CO2e per scope/category.
# Scope 3 supply chains of very large companies can reach millions of
# tonnes; direct combustion above a few million tonnes is suspicious.
CO2_UPPER_BOUNDS: dict[tuple[str, str], float] = {
    ("scope_1", "stationary_combustion"): 5_000_000,
    ("scope_1", "mobile_combustion"): 2_000_000,
    ("scope_2", "purchased_electricity"): 3_000_000,
    ("scope_2", "purchased_heat"): 2_000_000,
    ("scope_3", "business_travel"): 1_000_000,
    ("scope_3", "employee_commuting"): 1_000_000,
    ("scope_3", "supply_chain"): 10_000_000,
    ("scope_3", "waste"): 1_000_000,
}
DEFAULT_UPPER_BOUND = 10_000_000


@dataclass
class ValidationResult:
    passed: bool
    rule: str
    message: str
    severity: str = "error"  # "error" | "warning"
    details: dict = field(default_factory=dict)


class EmissionDataValidator:
    """Validates emission data before DB insertion."""

    def validate_co2_value(self, co2_tonnes: float, scope: str, category: str) -> ValidationResult:
        """CO2 value must be positive and within a plausible range for its scope/category."""
        if co2_tonnes is None or co2_tonnes <= 0:
            return ValidationResult(
                passed=False,
                rule="co2_range_check",
                message=f"CO2 value must be positive — got {co2_tonnes}",
            )

        upper = CO2_UPPER_BOUNDS.get((scope, category), DEFAULT_UPPER_BOUND)
        if co2_tonnes > upper:
            return ValidationResult(
                passed=False,
                rule="co2_range_check",
                message=(
                    f"{co2_tonnes:,.0f}t CO2e is implausibly high for "
                    f"{scope}/{category} (max plausible: {upper:,.0f}t)"
                ),
            )

        return ValidationResult(
            passed=True,
            rule="co2_range_check",
            message="CO2 value within plausible range",
        )

    def validate_year_consistency(self, year: int, month: int | None) -> ValidationResult:
        """Reporting period cannot be in the future, and year must be >= 2000."""
        if year is None or year < 2000:
            return ValidationResult(
                passed=False,
                rule="year_consistency_check",
                message=f"Reporting year must be >= 2000 — got {year}",
            )

        today = date.today()
        if year > today.year:
            return ValidationResult(
                passed=False,
                rule="year_consistency_check",
                message=f"Reporting year {year} is in the future",
            )
        if year == today.year and month and month > today.month:
            return ValidationResult(
                passed=False,
                rule="year_consistency_check",
                message=f"Reporting period {year}-{month:02d} is in the future",
            )

        return ValidationResult(
            passed=True,
            rule="year_consistency_check",
            message="Reporting period is valid",
        )

    def validate_completeness(self, records: list[dict]) -> ValidationResult:
        """
        A complete annual dataset should cover all 3 scopes, and Scope 3
        should normally be the largest (warning only — some sectors differ).
        """
        scopes_present = {str(r.get("scope", "")) for r in records}
        expected = {"scope_1", "scope_2", "scope_3"}
        missing = expected - scopes_present

        warnings: list[str] = []

        if missing:
            return ValidationResult(
                passed=False,
                rule="completeness_check",
                message=f"Dataset is missing scopes: {sorted(missing)}",
                details={"missing_scopes": sorted(missing)},
            )

        totals: dict[str, float] = {}
        for r in records:
            scope = str(r.get("scope", ""))
            totals[scope] = totals.get(scope, 0.0) + float(r.get("co2_tonnes", 0) or 0)

        if totals and max(totals, key=totals.get) != "scope_3":
            warnings.append(
                "Scope 3 is usually the largest scope (70-90% of footprint) "
                "but is not here — verify value-chain data is complete."
            )

        return ValidationResult(
            passed=True,
            rule="completeness_check",
            message="All scopes present" + (f" — {len(warnings)} warning(s)" if warnings else ""),
            severity="warning" if warnings else "error",
            details={"warnings": warnings, "scope_totals": totals},
        )

    def validate_batch(self, records: list[dict]) -> dict:
        """Run all validations on a batch of records."""
        results: list[ValidationResult] = []
        valid_records: list[dict] = []
        invalid_records: list[dict] = []
        warnings = 0

        for i, record in enumerate(records):
            record_results = [
                self.validate_co2_value(
                    record.get("co2_tonnes"),
                    str(record.get("scope", "")),
                    str(record.get("category", "")),
                ),
                self.validate_year_consistency(
                    record.get("reporting_year"),
                    record.get("reporting_month"),
                ),
            ]
            failures = [r for r in record_results if not r.passed]
            results.extend(record_results)

            if failures:
                invalid_records.append({
                    "row": i,
                    "record": record,
                    "reasons": [f.message for f in failures],
                })
            else:
                valid_records.append(record)

        completeness = self.validate_completeness(records)
        results.append(completeness)
        if completeness.details.get("warnings"):
            warnings += len(completeness.details["warnings"])

        return {
            "total": len(records),
            "passed": len(valid_records),
            "failed": len(invalid_records),
            "warnings": warnings,
            "results": results,
            "valid_records": valid_records,
            "invalid_records": invalid_records,
        }


validator = EmissionDataValidator()  # module singleton
