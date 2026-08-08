"""
CSRDReportGenerator — turns emission data into an ESRS E1 narrative.

Two entry points:
- generate_full_report(): async generator for SSE streaming endpoints
- generate_report_sync(): blocking version for Celery tasks
"""
import logging

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.ml.vector_store_manager import vector_store_manager

logger = logging.getLogger(__name__)


class CSRDReportGenerator:

    def generate_report_context(self, emission_summary: dict, company_info: dict) -> str:
        """
        Formats emission data as structured text context for the LLM.
        Includes company profile, Scope 1/2/3 totals, scope shares and
        the largest scope — everything the model needs to reason about.
        """
        scope_1 = emission_summary.get("scope_1_total", 0.0)
        scope_2 = emission_summary.get("scope_2_total", 0.0)
        scope_3 = emission_summary.get("scope_3_total", 0.0)
        grand_total = emission_summary.get("grand_total", 0.0) or (scope_1 + scope_2 + scope_3)

        def share(value: float) -> str:
            return f"{(value / grand_total * 100):.1f}%" if grand_total else "n/a"

        scopes = {"Scope 1": scope_1, "Scope 2": scope_2, "Scope 3": scope_3}
        largest_scope = max(scopes, key=scopes.get) if grand_total else "n/a"

        lines = [
            f"Company: {company_info.get('name', 'Unknown')}",
            f"Industry sector: {company_info.get('sector', 'unknown')}",
            f"Country: {company_info.get('country', 'unknown')}",
            f"Employees: {company_info.get('employee_count') or 'not disclosed'}",
            f"Annual revenue (kEUR): {company_info.get('annual_revenue_eur') or 'not disclosed'}",
            f"Reporting year: {emission_summary.get('reporting_year')}",
            "",
            "GHG emissions (tonnes CO2 equivalent):",
            f"- Scope 1 (direct): {scope_1:,.1f} t CO2e ({share(scope_1)} of total)",
            f"- Scope 2 (purchased energy): {scope_2:,.1f} t CO2e ({share(scope_2)} of total)",
            f"- Scope 3 (value chain): {scope_3:,.1f} t CO2e ({share(scope_3)} of total)",
            f"- Total gross emissions: {grand_total:,.1f} t CO2e",
            f"- Largest contributing scope: {largest_scope}",
            f"- Number of underlying emission records: {emission_summary.get('record_count', 0)}",
        ]
        return "\n".join(lines)

    def _build_chain_inputs(self, company_id: int, year: int, db: Session) -> dict:
        """Fetch data from the DB and assemble the chain input dict."""
        from app.services.company_service import CompanyService
        from app.services.emission_service import EmissionService

        company = CompanyService.get_by_id(db, company_id)
        summary = EmissionService.get_summary(db, company_id, year)

        emission_context = self.generate_report_context(
            summary.model_dump(),
            {
                "name": company.name,
                "sector": company.sector.value if hasattr(company.sector, "value") else str(company.sector),
                "country": company.country,
                "employee_count": company.employee_count,
                "annual_revenue_eur": company.annual_revenue_eur,
            },
        )

        regulatory_chunks = vector_store_manager.search(
            "ESRS E1 climate change disclosure requirements scope 1 2 3", k=4
        )
        regulatory_context = "\n\n".join(c["content"] for c in regulatory_chunks) or (
            "ESRS E1 requires disclosure of gross Scope 1, 2 and 3 GHG emissions, "
            "reduction targets and methodology."
        )

        return {
            "emission_context": emission_context,
            "regulatory_context": regulatory_context,
        }

    def _record_report_metric(self, company_id: int) -> None:
        try:
            from app.core.metrics import csrd_reports_generated_total
            csrd_reports_generated_total.labels(company_id=str(company_id)).inc()
        except Exception:  # noqa: BLE001 — metrics must never break report generation
            pass

    async def generate_full_report(self, company_id: int, year: int, db: Session):
        """
        Streams the full CSRD E1 report chunk by chunk (for SSE endpoints).
        """
        if not settings.OPENAI_API_KEY:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="LLM not configured — set OPENAI_API_KEY in .env",
            )

        from app.ml.rag_chain import build_csrd_report_chain

        inputs = self._build_chain_inputs(company_id, year, db)
        chain = build_csrd_report_chain()

        async for chunk in chain.astream(inputs):
            if chunk:
                yield chunk

        self._record_report_metric(company_id)

    def generate_report_sync(self, company_id: int, year: int, db: Session) -> str:
        """
        Synchronous version for Celery tasks — returns the complete report.
        """
        if not settings.OPENAI_API_KEY:
            raise RuntimeError("LLM not configured — set OPENAI_API_KEY in .env")

        from app.ml.rag_chain import build_csrd_report_chain

        inputs = self._build_chain_inputs(company_id, year, db)
        chain = build_csrd_report_chain()
        report = chain.invoke(inputs)

        self._record_report_metric(company_id)
        return report


report_generator = CSRDReportGenerator()
