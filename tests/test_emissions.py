"""Emission endpoint tests — CRUD, validation, summary, caching, bulk upload."""
from unittest.mock import patch

import pytest

from tests.conftest import REDIS_AVAILABLE, auth_headers


def _record(company_id: int, scope="scope_1", category="stationary_combustion",
            co2=125.5, year=2024, month=3) -> dict:
    return {
        "company_id": company_id,
        "scope": scope,
        "category": category,
        "co2_tonnes": co2,
        "reporting_year": year,
        "reporting_month": month,
        "data_source": "test",
    }


def test_create_emission_scope1(test_client, analyst_token, sample_company):
    response = test_client.post(
        "/api/v1/emissions/",
        json=_record(sample_company.id),
        headers=auth_headers(analyst_token),
    )
    assert response.status_code == 201
    body = response.json()
    assert body["scope"] == "scope_1"
    assert body["co2_tonnes"] == 125.5
    assert body["company_id"] == sample_company.id


def test_create_emission_invalid_scope_category_combo(test_client, analyst_token, sample_company):
    # scope_1 + purchased_electricity violates the GHG Protocol mapping
    response = test_client.post(
        "/api/v1/emissions/",
        json=_record(sample_company.id, scope="scope_1", category="purchased_electricity"),
        headers=auth_headers(analyst_token),
    )
    assert response.status_code == 422


def test_emission_summary_aggregation(test_client, analyst_token, sample_company):
    records = [
        _record(sample_company.id, "scope_1", "stationary_combustion", 100.0),
        _record(sample_company.id, "scope_2", "purchased_electricity", 200.0),
        _record(sample_company.id, "scope_3", "supply_chain", 700.0),
    ]
    for r in records:
        assert test_client.post(
            "/api/v1/emissions/", json=r, headers=auth_headers(analyst_token)
        ).status_code == 201

    response = test_client.get(
        f"/api/v1/emissions/summary/{sample_company.id}/2024",
        headers=auth_headers(analyst_token),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["scope_1_total"] == 100.0
    assert body["scope_2_total"] == 200.0
    assert body["scope_3_total"] == 700.0
    assert body["grand_total"] == 1000.0
    assert body["record_count"] == 3


@pytest.mark.skipif(not REDIS_AVAILABLE, reason="Cache tests require Redis")
def test_summary_cached(test_client, analyst_token, sample_company):
    from app.core.cache import cache, make_summary_key

    test_client.post(
        "/api/v1/emissions/",
        json=_record(sample_company.id),
        headers=auth_headers(analyst_token),
    )

    # First call populates the cache
    test_client.get(
        f"/api/v1/emissions/summary/{sample_company.id}/2024",
        headers=auth_headers(analyst_token),
    )
    cache_key = make_summary_key(sample_company.id, 2024)
    assert cache.get(cache_key) is not None

    # Second call is served from cache — same result
    response = test_client.get(
        f"/api/v1/emissions/summary/{sample_company.id}/2024",
        headers=auth_headers(analyst_token),
    )
    assert response.status_code == 200


@pytest.mark.skipif(not REDIS_AVAILABLE, reason="Cache tests require Redis")
def test_cache_invalidated_on_new_record(test_client, analyst_token, sample_company):
    from app.core.cache import cache, make_summary_key

    test_client.post(
        "/api/v1/emissions/",
        json=_record(sample_company.id, co2=50.0),
        headers=auth_headers(analyst_token),
    )
    test_client.get(
        f"/api/v1/emissions/summary/{sample_company.id}/2024",
        headers=auth_headers(analyst_token),
    )
    cache_key = make_summary_key(sample_company.id, 2024)
    assert cache.get(cache_key) is not None

    # Inserting a new record must invalidate the cached summary
    test_client.post(
        "/api/v1/emissions/",
        json=_record(sample_company.id, co2=75.0, month=4),
        headers=auth_headers(analyst_token),
    )
    assert cache.get(cache_key) is None


def test_bulk_upload_returns_202(test_client, analyst_token, sample_company):
    payload = {
        "records": [
            {
                "scope": "scope_1",
                "category": "mobile_combustion",
                "co2_tonnes": 42.0,
                "reporting_year": 2024,
                "reporting_month": 5,
            }
        ]
    }
    # Mock Celery's .delay() — tests must not require a broker/worker
    with patch("app.api.v1.endpoints.emissions.process_bulk_emissions") as mock_task:
        mock_task.delay.return_value.id = "fake-task-id-123"
        response = test_client.post(
            f"/api/v1/emissions/bulk/{sample_company.id}",
            json=payload,
            headers=auth_headers(analyst_token),
        )
    assert response.status_code == 202
    body = response.json()
    assert body["task_id"] == "fake-task-id-123"
    assert body["status"] == "queued"
