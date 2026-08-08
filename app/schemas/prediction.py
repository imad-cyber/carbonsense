from pydantic import BaseModel, Field
from typing import Optional
from app.models.emission import EmissionScope, EmissionCategory


class ForecastRequest(BaseModel):
    """Request body for POST /predictions/forecast."""
    company_id: int = Field(..., gt=0)
    scope: EmissionScope
    category: EmissionCategory
    reporting_year: int = Field(..., ge=2000, le=2100)
    reporting_month: int = Field(..., ge=1, le=12)


class ShapContribution(BaseModel):
    feature: str
    feature_value: float
    shap_value: float
    direction: str


class PredictionExplanation(BaseModel):
    base_value: float
    prediction: float
    top_drivers: list[ShapContribution]
    explanation_method: str


class ForecastResponse(BaseModel):
    company_id: int
    scope: str
    category: str
    reporting_year: int
    reporting_month: int
    predicted_co2_tonnes: float
    explanation: PredictionExplanation


class AnomalyScanRequest(BaseModel):
    """Request body for POST /predictions/anomalies."""
    company_id: int = Field(..., gt=0)
    year: int = Field(..., ge=2000, le=2100)


class AnomalyRecordResult(BaseModel):
    record_id: int
    company_id: int
    scope: str
    category: str
    co2_tonnes: float
    reporting_year: int
    reporting_month: int
    anomaly_score: float
    is_anomaly: bool
    anomaly_severity: Optional[str] = None


class AnomalyScanResponse(BaseModel):
    company_id: int
    year: int
    total_records: int
    anomaly_count: int
    anomaly_rate: float
    records: list[AnomalyRecordResult]


class FeatureImportanceItem(BaseModel):
    feature: str
    importance: float
    rank: int


class FeatureImportanceResponse(BaseModel):
    feature_importance: list[FeatureImportanceItem]


class ModelStatusResponse(BaseModel):
    forecasting_model: bool
    anomaly_detector: bool
