"""
VectorStoreManager — singleton facade over the FAISS vector store.

Owns ingestion (built-in regulatory texts + user PDFs) and search.
Everything degrades gracefully when the RAG dependencies or the
OpenAI key are missing.
"""
import logging

from app.ml.document_processor import (
    add_documents_to_store,
    load_pdf,
    load_text,
    load_vector_store,
    split_documents,
)

logger = logging.getLogger(__name__)

# Representative CSRD/ESRS regulatory texts. In production these would be
# the full ESRS PDFs — these condensed excerpts make the RAG demo
# self-contained without shipping hundreds of pages.
REGULATORY_TEXTS: list[tuple[str, dict]] = [
    (
        "CSRD Reporting Requirements: The Corporate Sustainability Reporting "
        "Directive (CSRD, Directive (EU) 2022/2464) requires large EU companies "
        "and listed SMEs to report on sustainability matters in accordance with "
        "the European Sustainability Reporting Standards (ESRS). Companies with "
        "more than 250 employees, EUR 50 million net turnover, or EUR 25 million "
        "total assets (meeting two of three criteria) must report from financial "
        "year 2024 onwards, with first reports published in 2025. Listed SMEs "
        "follow from financial year 2026. Reports must be included in the "
        "management report, digitally tagged in ESEF/XBRL format, and subject "
        "to limited assurance by an accredited auditor.",
        {"source": "CSRD Directive (EU) 2022/2464", "topic": "reporting_requirements"},
    ),
    (
        "GHG Emission Scopes (GHG Protocol, referenced by ESRS E1): Scope 1 "
        "covers direct greenhouse gas emissions from sources owned or controlled "
        "by the company, such as stationary combustion in boilers and furnaces, "
        "and mobile combustion in company vehicles. Scope 2 covers indirect "
        "emissions from the generation of purchased electricity, steam, heating "
        "and cooling consumed by the company; it must be reported using both the "
        "location-based method (grid average emission factors) and the "
        "market-based method (contractual instruments such as guarantees of "
        "origin and PPAs). Scope 3 covers all other indirect emissions in the "
        "value chain, including purchased goods and services, business travel, "
        "employee commuting, waste, and use of sold products. Scope 3 typically "
        "represents 70-90% of a company's total carbon footprint.",
        {"source": "ESRS E1 / GHG Protocol", "topic": "emission_scopes"},
    ),
    (
        "ESRS E1 Climate Change Requirements: ESRS E1 requires disclosure of "
        "(1) the transition plan for climate change mitigation aligned with "
        "limiting global warming to 1.5°C, (2) material impacts, risks and "
        "opportunities related to climate, (3) gross Scope 1, 2 and 3 GHG "
        "emissions in tonnes of CO2 equivalent, (4) total GHG emissions "
        "intensity per net revenue, (5) GHG reduction targets for 2030 and "
        "2050 with milestone years, (6) energy consumption and mix including "
        "renewable share, and (7) internal carbon pricing schemes if applied. "
        "Emission data must follow the GHG Protocol Corporate Standard and be "
        "presented for the reporting year alongside comparison to the base year.",
        {"source": "ESRS E1", "topic": "e1_requirements"},
    ),
    (
        "Double Materiality Assessment: Under CSRD, companies must perform a "
        "double materiality assessment covering both impact materiality (the "
        "company's actual or potential impacts on people and the environment "
        "across its value chain, on a gross basis, considering severity and "
        "likelihood) and financial materiality (sustainability matters that "
        "generate risks or opportunities affecting the company's development, "
        "financial position, performance, cash flows, access to finance or cost "
        "of capital). A sustainability matter is material if it meets either "
        "criterion. The assessment methodology, stakeholder engagement process "
        "and outcomes must be disclosed under ESRS 2 IRO-1 and IRO-2.",
        {"source": "ESRS 2 / CSRD", "topic": "double_materiality"},
    ),
    (
        "CSRD Verification and Assurance Requirements: Sustainability "
        "information reported under CSRD must be verified by an independent "
        "accredited assurance provider. Initially, limited assurance is "
        "required — the auditor confirms no evidence of material misstatement "
        "was found. The European Commission may move to reasonable assurance "
        "(the same level as financial audits) following a feasibility "
        "assessment. The assurance covers compliance with ESRS, the double "
        "materiality assessment process, ESEF digital tagging, and the "
        "indicators reported under Article 8 of the Taxonomy Regulation. "
        "Member states may allow independent assurance services providers "
        "other than the statutory auditor to perform the engagement.",
        {"source": "CSRD Article 34", "topic": "verification"},
    ),
]


class VectorStoreManager:
    """Lazy-loaded singleton wrapper around the FAISS store."""

    def __init__(self):
        self._store = None

    def _get_store(self):
        if self._store is None:
            try:
                self._store = load_vector_store()
            except ImportError as e:
                logger.warning(f"RAG dependencies not installed: {e}")
                return None
        return self._store

    def ingest_regulatory_text(self) -> int:
        """
        Ingest the built-in CSRD/ESRS texts into the vector store.
        Returns the number of chunks ingested.
        """
        documents = []
        for text, metadata in REGULATORY_TEXTS:
            documents.extend(load_text(text, metadata))

        chunks = split_documents(documents)
        self._store = add_documents_to_store(chunks)
        logger.info(f"Ingested {len(chunks)} regulatory chunks into FAISS")
        return len(chunks)

    def ingest_pdf(self, file_path: str) -> int:
        """Ingest a user-uploaded PDF. Returns the number of chunks added."""
        documents = load_pdf(file_path)
        chunks = split_documents(documents)
        self._store = add_documents_to_store(chunks)
        logger.info(f"Ingested {len(chunks)} chunks from PDF {file_path}")
        return len(chunks)

    def search(self, query: str, k: int = 5) -> list[dict]:
        """Top-k similarity search — returns content + metadata + score."""
        store = self._get_store()
        if store is None:
            return []

        results = store.similarity_search_with_score(query, k=k)
        return [
            {
                "content": doc.page_content,
                "metadata": doc.metadata,
                "score": float(score),
            }
            for doc, score in results
        ]

    def is_ready(self) -> bool:
        """True if a FAISS index exists on disk and has documents."""
        try:
            store = self._get_store()
        except Exception as e:  # index corrupted / deps missing
            logger.warning(f"Vector store not ready: {e}")
            return False
        if store is None:
            return False
        return self.document_count() > 0

    def document_count(self) -> int:
        store = self._get_store()
        if store is None:
            return 0
        try:
            return store.index.ntotal
        except AttributeError:
            return 0

    def reload(self) -> None:
        """Drop the cached store so the next access re-reads from disk."""
        self._store = None


# Module-level singleton
vector_store_manager = VectorStoreManager()
