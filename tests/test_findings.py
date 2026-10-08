from app.ml.findings import group_findings


def _r(i, group, flagged, severity=None, month=1, tonnes=10.0):
    return {
        "record_id": i, "activity_group_id": group, "reporting_year": 2024,
        "reporting_month": month, "scope": "scope_1", "category": "stationary_combustion",
        "co2_tonnes": tonnes, "is_anomaly": flagged, "anomaly_severity": severity,
        "times_series_median": 2.5 if flagged else 1.0,
    }


def test_records_of_one_activity_become_one_finding():
    rows = [_r(1, "g1", True, "medium"), _r(2, "g1", True, "high"), _r(3, "g2", False)]
    findings = group_findings(rows)
    assert len(findings) == 1
    assert findings[0]["severity"] == "high"
    assert [x["record_id"] for x in findings[0]["records"]] == [1, 2]
    assert findings[0]["total_co2_tonnes"] == 20.0


def test_records_without_a_group_are_their_own_finding():
    rows = [_r(1, None, True, "low"), _r(2, None, True, "low", month=2)]
    assert len(group_findings(rows)) == 2


def test_nothing_flagged_means_no_findings():
    assert group_findings([_r(1, "g1", False)]) == []


def test_findings_are_ordered_by_severity_then_date():
    rows = [_r(1, "a", True, "low", month=1), _r(2, "b", True, "high", month=5),
            _r(3, "c", True, "high", month=2)]
    assert [f["records"][0]["record_id"] for f in group_findings(rows)] == [3, 2, 1]
