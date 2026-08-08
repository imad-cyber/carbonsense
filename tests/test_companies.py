"""Company CRUD endpoint tests — pagination, RBAC, partial updates."""
from tests.conftest import auth_headers


def _company_payload(name: str) -> dict:
    return {
        "name": name,
        "sector": "technology",
        "country": "France",
        "employee_count": 250,
        "annual_revenue_eur": 60_000,
    }


def test_create_company_as_analyst(test_client, analyst_token):
    response = test_client.post(
        "/api/v1/companies/",
        json=_company_payload("Analyst Created SA"),
        headers=auth_headers(analyst_token),
    )
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Analyst Created SA"
    assert body["sector"] == "technology"
    assert "id" in body


def test_create_company_duplicate_name(test_client, analyst_token):
    payload = _company_payload("Duplicate Corp SA")
    first = test_client.post(
        "/api/v1/companies/", json=payload, headers=auth_headers(analyst_token)
    )
    assert first.status_code == 201
    second = test_client.post(
        "/api/v1/companies/", json=payload, headers=auth_headers(analyst_token)
    )
    assert second.status_code == 409


def test_list_companies_paginated(test_client, analyst_token, sample_company):
    response = test_client.get(
        "/api/v1/companies/?page=1&page_size=5",
        headers=auth_headers(analyst_token),
    )
    assert response.status_code == 200
    body = response.json()
    assert "items" in body
    assert "total" in body
    assert body["page"] == 1
    assert body["page_size"] == 5
    assert len(body["items"]) <= 5


def test_get_company_not_found(test_client, analyst_token):
    response = test_client.get(
        "/api/v1/companies/999999", headers=auth_headers(analyst_token)
    )
    assert response.status_code == 404


def test_update_company_partial(test_client, analyst_token, sample_company):
    original_sector = sample_company.sector.value
    response = test_client.patch(
        f"/api/v1/companies/{sample_company.id}",
        json={"employee_count": 999},
        headers=auth_headers(analyst_token),
    )
    assert response.status_code == 200
    body = response.json()
    # Only the updated field changed — others preserved
    assert body["employee_count"] == 999
    assert body["name"] == sample_company.name
    assert body["sector"] == original_sector


def test_delete_company_as_admin(test_client, admin_token, sample_company):
    response = test_client.delete(
        f"/api/v1/companies/{sample_company.id}",
        headers=auth_headers(admin_token),
    )
    assert response.status_code == 204


def test_delete_company_as_analyst(test_client, analyst_token, sample_company):
    response = test_client.delete(
        f"/api/v1/companies/{sample_company.id}",
        headers=auth_headers(analyst_token),
    )
    assert response.status_code == 403  # analysts cannot delete


def test_unauthenticated_access(test_client, sample_company):
    endpoints = [
        ("get", "/api/v1/companies/"),
        ("get", f"/api/v1/companies/{sample_company.id}"),
        ("post", "/api/v1/companies/"),
        ("patch", f"/api/v1/companies/{sample_company.id}"),
        ("delete", f"/api/v1/companies/{sample_company.id}"),
    ]
    for method, url in endpoints:
        response = getattr(test_client, method)(url)
        assert response.status_code == 401, f"{method.upper()} {url} not protected"
