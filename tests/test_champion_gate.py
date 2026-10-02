"""Tests for the champion/challenger promotion gate."""
from app.ml.forecaster import BASELINE, CHALLENGER, choose_champion


def _report(base: list, chal: list) -> dict:
    """Build a minimal rolling-origin report for choose_champion."""
    return {
        "per_fold": [
            {"models": {BASELINE: {"wape_pct": b}, CHALLENGER: {"wape_pct": c}}}
            for b, c in zip(base, chal)
        ]
    }


def test_no_promotion_on_a_tie():
    """Challenger must WIN every fold, not merely match."""
    assert choose_champion(_report([6, 6, 6, 6], [6.1, 5.9, 6.0, 6.2])) == BASELINE


def test_no_promotion_if_it_loses_a_single_fold():
    """Even one fold where challenger is worse blocks promotion."""
    assert choose_champion(_report([6, 6, 6, 6], [4, 4, 4, 6.5])) == BASELINE


def test_no_promotion_below_margin():
    """Challenger wins every fold but improvement is below PROMOTION_MARGIN_PP."""
    # mean gain is 0.2pp, default margin is 0.5pp
    assert choose_champion(_report([6, 6, 6, 6], [5.8, 5.8, 5.8, 5.8])) == BASELINE


def test_promotion_when_it_wins_every_fold_by_the_margin():
    """Challenger wins every fold and mean gain >= 0.5pp → promote."""
    assert choose_champion(_report([6, 6, 6, 6], [5, 5, 5, 5])) == CHALLENGER


def test_custom_margin_respected():
    """Caller can lower or raise the margin threshold."""
    # mean gain 0.3pp: fails default 0.5 but passes 0.2
    assert choose_champion(_report([6, 6, 6, 6], [5.7, 5.7, 5.7, 5.7]), margin_pp=0.2) == CHALLENGER
    assert choose_champion(_report([6, 6, 6, 6], [5.7, 5.7, 5.7, 5.7]), margin_pp=0.5) == BASELINE
