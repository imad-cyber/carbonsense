from fastapi import HTTPException, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session
from app.models.emission_factor import EmissionFactor


def _like(term: str) -> str:
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


class EmissionFactorService:
    @staticmethod
    def search(
        db: Session,
        q: str | None = None,
        unit: str | None = None,
        geography: str | None = None,
        category: str | None = None,
        include_archived: bool = False,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[EmissionFactor], int]:
        query = db.query(EmissionFactor)
        if q:
            query = query.filter(EmissionFactor.name.ilike(_like(q), escape="\\"))
        if unit:
            query = query.filter(func.lower(EmissionFactor.unit) == unit.lower())
        if geography:
            query = query.filter(EmissionFactor.geography.ilike(_like(geography), escape="\\"))
        if category:
            query = query.filter(EmissionFactor.category_path.ilike(_like(category), escape="\\"))
        if not include_archived:
            query = query.filter(
                or_(EmissionFactor.status.is_(None), ~EmissionFactor.status.ilike("archiv%"))
            )
        total = query.count()
        items = (
            query.order_by(EmissionFactor.name)
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return items, total

    @staticmethod
    def get_by_id(db: Session, factor_id: int) -> EmissionFactor:
        factor = db.query(EmissionFactor).filter(EmissionFactor.id == factor_id).first()
        if not factor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Emission factor {factor_id} not found",
            )
        return factor
