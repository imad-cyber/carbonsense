from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi import HTTPException, status
from app.models.emission import EmissionRecord, EmissionScope
from app.models.company import Company
from app.schemas.emission import EmissionRecordCreate, EmissionRecordUpdate, EmissionSummary
from app.core.cache import cache, make_summary_key
from app.core.config import settings


class EmissionService:

    @staticmethod
    def get_by_company(
        db: Session,
        company_id: int,
        year: int | None = None,
        scope: EmissionScope | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[EmissionRecord], int]:
        query = db.query(EmissionRecord).filter(
            EmissionRecord.company_id == company_id
        )
        # Filters are applied only when the caller provides them
        # This is a common pattern — one method handles filtered and unfiltered queries
        if year:
            query = query.filter(EmissionRecord.reporting_year == year)
        if scope:
            query = query.filter(EmissionRecord.scope == scope)

        total = query.with_entities(func.count(EmissionRecord.id)).scalar()
        offset = (page - 1) * page_size
        items = (
            query
            .order_by(EmissionRecord.reporting_year.desc(), EmissionRecord.scope)
            .offset(offset)
            .limit(page_size)
            .all()
        )
        return items, total

    @staticmethod
    def get_by_id(db: Session, record_id: int) -> EmissionRecord:
        record = (
            db.query(EmissionRecord)
            .filter(EmissionRecord.id == record_id)
            .first()
        )
        if not record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Emission record {record_id} not found",
            )
        return record

    @staticmethod
    def create(db: Session, data: EmissionRecordCreate) -> EmissionRecord:
        # Always validate the foreign key exists before inserting
        company = db.query(Company).filter(
            Company.id == data.company_id
        ).first()
        if not company:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Company {data.company_id} not found",
            )

        record = EmissionRecord(**data.model_dump())
        db.add(record)
        db.commit()
        db.refresh(record)
        cache.delete_pattern(f"summary:company:{record.company_id}:*")

        # Publish to Kafka for real-time processing (Phase 8).
        # Kafka failure must NEVER fail the HTTP request.
        try:
            from app.data_pipeline.kafka_producer import emission_producer
            emission_producer.publish_emission_created({
                "id": record.id,
                "company_id": record.company_id,
                "scope": record.scope.value,
                "category": record.category.value,
                "co2_tonnes": record.co2_tonnes,
                "reporting_year": record.reporting_year,
                "reporting_month": record.reporting_month,
            })
        except Exception:  # noqa: BLE001 — graceful degradation
            pass

        # Business metric (Phase 10) — failures must never affect the request
        try:
            from app.core.metrics import emissions_ingested_total
            emissions_ingested_total.labels(
                scope=record.scope.value,
                company_id=str(record.company_id),
            ).inc()
        except Exception:  # noqa: BLE001
            pass

        return record

    @staticmethod
    def update(
        db: Session,
        record_id: int,
        data: EmissionRecordUpdate,
    ) -> EmissionRecord:
        record = EmissionService.get_by_id(db, record_id)
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(record, field, value)
        db.commit()
        db.refresh(record)
        cache.delete_pattern(f"summary:company:{record.company_id}:*")
        return record

    @staticmethod
    def delete(db: Session, record_id: int) -> None:
        record = EmissionService.get_by_id(db, record_id)
        db.delete(record)
        db.commit()
        cache.delete_pattern(f"summary:company:{record.company_id}:*")

    # Add these imports at the top of emission_service.py:

    @staticmethod
    def get_summary(
        db: Session,
        company_id: int,
        year: int,
    ) -> EmissionSummary:
        """
        Cache-aside pattern:
        1. Build the cache key
        2. Try to return from cache (fast path — microseconds)
        3. On miss: query DB, store result in cache (slow path — milliseconds)

        This means the first call pays the DB cost.
        Every subsequent call (until TTL expires) is served from RAM.
        """
        cache_key = make_summary_key(company_id, year)

        # ── Fast path ───────────────────────────────────────────────
        cached = cache.get(cache_key)
        if cached:
            # Return a proper Pydantic object from the cached dict
            return EmissionSummary(**cached)

        # ── Slow path (DB query) ─────────────────────────────────────
        company = db.query(Company).filter(Company.id == company_id).first()
        if not company:
            raise HTTPException(status_code=404, detail="Company not found")

        rows = (
            db.query(
                EmissionRecord.scope,
                func.sum(EmissionRecord.co2_tonnes).label("total"),
                func.count(EmissionRecord.id).label("count"),
            )
            .filter(
                EmissionRecord.company_id == company_id,
                EmissionRecord.reporting_year == year,
            )
            .group_by(EmissionRecord.scope)
            .all()
        )

        totals = {row.scope: row.total for row in rows}
        count = sum(row.count for row in rows)

        summary = EmissionSummary(
            company_id=company_id,
            reporting_year=year,
            scope_1_total=totals.get(EmissionScope.SCOPE_1, 0.0),
            scope_2_total=totals.get(EmissionScope.SCOPE_2, 0.0),
            scope_3_total=totals.get(EmissionScope.SCOPE_3, 0.0),
            grand_total=sum(totals.values()),
            record_count=count,
        )

        # Store in Redis — cache miss is now populated
        cache.set(cache_key, summary.model_dump(), ttl=settings.CACHE_TTL_SUMMARY)

        return summary