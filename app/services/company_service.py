from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi import HTTPException, status
from app.models.company import Company
from app.schemas.company import CompanyCreate, CompanyUpdate


class CompanyService:
    """
    All database operations related to companies live here.
    The router calls these methods — it never touches the DB directly.
    """

    @staticmethod
    def get_all(
        db: Session,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Company], int]:
        """
        Paginated query — never return all rows without a limit.
        In production a table can have millions of rows.
        offset() skips rows, limit() caps the result count.
        """
        total = db.query(func.count(Company.id)).scalar()
        offset = (page - 1) * page_size
        items = (
            db.query(Company)
            .order_by(Company.created_at.desc())
            .offset(offset)
            .limit(page_size)
            .all()
        )
        return items, total

    @staticmethod
    def get_by_id(db: Session, company_id: int) -> Company:
        company = db.query(Company).filter(Company.id == company_id).first()
        if not company:
            # Raise HTTP 404 — FastAPI catches this and returns the right response
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Company with id {company_id} not found",
            )
        return company

    @staticmethod
    def create(db: Session, data: CompanyCreate) -> Company:
        # Check for duplicate name — database has unique constraint too,
        # but checking here gives a cleaner error message
        existing = (
            db.query(Company).filter(Company.name == data.name).first()
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Company '{data.name}' already exists",
            )

        # model_dump() converts the Pydantic schema to a plain dict
        # ** unpacks it as keyword arguments to the SQLAlchemy model
        company = Company(**data.model_dump())
        db.add(company)
        db.commit()
        db.refresh(company)  # refresh loads DB-generated fields (id, timestamps)
        return company

    @staticmethod
    def update(
        db: Session,
        company_id: int,
        data: CompanyUpdate,
    ) -> Company:
        company = CompanyService.get_by_id(db, company_id)

        # exclude_unset=True only updates fields the client actually sent.
        # This is what makes PATCH different from PUT.
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(company, field, value)

        db.commit()
        db.refresh(company)
        return company

    @staticmethod
    def delete(db: Session, company_id: int) -> None:
        company = CompanyService.get_by_id(db, company_id)
        db.delete(company)
        db.commit()