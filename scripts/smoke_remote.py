"""
Smoke test of a deployed API. Creates nothing.
  python scripts/smoke_remote.py https://your-api.example.com
"""
import sys

import httpx

BASE = (sys.argv[1] if len(sys.argv) == 2 else sys.exit(__doc__)).rstrip("/")
DEMO = {"email": "demo@carbonsense.fr", "password": "Demo-Auditor-2026"}
failures = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global failures
    failures += 0 if ok else 1
    print(("PASS  " if ok else "FAIL  ") + name + (f"   [{detail}]" if detail else ""))


with httpx.Client(base_url=BASE, timeout=90) as c:
    r = c.get("/health")
    check("health", r.status_code == 200, r.text)
    r = c.post("/api/v1/auth/login", json=DEMO)
    check("demo login", r.status_code == 200, str(r.status_code))
    if r.status_code != 200:
        sys.exit("cannot continue without a token")
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}

    check("registration is closed",
          c.post("/api/v1/auth/register",
                 json={"email": DEMO["email"], "password": "Passw0rdX1", "role": "admin"}
                 ).status_code == 403, "409 would mean it is OPEN")
    check("experimental routes are off", c.get("/api/v1/rag/status", headers=h).status_code == 404)
    check("openapi has the preview route", "from-activity/preview" in c.get("/openapi.json").text)

    items = c.get("/api/v1/companies/?page_size=100", headers=h).json()["items"]
    demo = next((x for x in items if x["name"].startswith("Démo")), None)
    check("demo company present", demo is not None, str([x["name"] for x in items]))
    if demo is None:
        sys.exit(1)
    cid = demo["id"]

    total = c.get("/api/v1/emission-factors/", headers=h,
                  params={"include_archived": "true", "page_size": 1}).json()["total"]
    check("all 10,939 factors loaded", total == 10939, str(total))

    s = c.get(f"/api/v1/emissions/summary/{cid}/2024", headers=h).json()
    check("2024 summary matches local",
          s["record_count"] == 84 and abs(s["scope_1_total"] - 1433.22) < 0.05
          and abs(s["scope_2_total"] - 676.40) < 0.05 and abs(s["scope_3_total"] - 626.86) < 0.05,
          f"{s['record_count']} records, S1 {s['scope_1_total']:.2f}, S2 {s['scope_2_total']:.2f}, S3 {s['scope_3_total']:.2f}")

    f = c.get("/api/v1/emission-factors/", headers=h,
              params={"q": "Gaz naturel - 2022", "unit": "kWh PCS", "geography": "France continentale"}
              ).json()["items"]
    gas = next((x for x in f if x["source_id"] == "37133"), None)
    check("gas factor 37133 found", gas is not None)
    if gas:
        payload = {"company_id": cid, "scope": "scope_1", "category": "stationary_combustion",
                   "emission_factor_id": gas["id"], "quantity": 50, "unit": "MWh PCS",
                   "reporting_year": 2024, "reporting_month": 1}
        r = c.post("/api/v1/emissions/from-activity/preview", json=payload, headers=h)
        body = r.json() if r.status_code == 200 else {}
        slices = [round(x["co2_tonnes"], 2) for x in body.get("slices", [])]
        check("preview: 9.05 t Scope 1 + 1.72 t Scope 3", slices == [9.05, 1.72], str(slices or r.text))
        check("demo user cannot save",
              c.post("/api/v1/emissions/from-activity", json=payload, headers=h).status_code == 403)

    r = c.post("/api/v1/predictions/anomalies", json={"company_id": cid, "year": 2023}, headers=h)
    findings = r.json().get("findings", []) if r.status_code == 200 else []
    check("2023 findings include February as high",
          any(x["reporting_month"] == 2 and x["severity"] == "high" for x in findings), f"{len(findings)} findings")

    r = c.post("/api/v1/predictions/forecast", headers=h, json={
        "company_id": cid, "scope": "scope_1", "category": "stationary_combustion",
        "reporting_year": 2025, "reporting_month": 1})
    check("forecast answers", r.status_code == 200 and r.json().get("predicted_co2_tonnes", 0) > 0,
          str(r.status_code))

print(f"\n{failures} failure(s)")
sys.exit(1 if failures else 0)
