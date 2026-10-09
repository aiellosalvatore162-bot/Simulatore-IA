from engine import config_from_input, simulate_match
from parser import parse_match_input

from test_parser import VALID


def test_simulation_is_reproducible_and_auditable():
    match = parse_match_input(VALID)
    config = config_from_input(match, simulations=3000, seed=11)
    first = simulate_match(config)
    second = simulate_match(config)
    assert first == second
    assert first["model"]["simulation_count"] == 3000
    assert first["model"]["formula_ledger"]["weights"]["xg"] == 0.20
    assert set(first["markets"]["1x2"]) == {"1", "X", "2"}
    assert set(first["markets"]["first_half_1x2"]) == {"1", "X", "2"}
    assert set(first["markets"]["multigol"]) == {"1-2", "1-3", "2-4", "2-5"}
    assert "Over_10.5" in first["markets"]["corners"]
    assert "Under_6.5" in first["markets"]["cards"]


def test_probabilities_use_the_declared_sample_size():
    result = simulate_match(config_from_input(parse_match_input(VALID), simulations=2000, seed=3))
    assert sum(item["count"] for item in result["markets"]["1x2"].values()) == 2000
    assert result["summary"]["modal_score"]["share_pct"] > 0


def test_financial_analysis_and_smart_combo_use_joint_samples():
    match = parse_match_input(VALID)
    config = config_from_input(match, simulations=5000, seed=4)
    config = config.__class__(
        **{**config.__dict__, "odds": {"1X": 1.35, "Over 1.5 gol": 1.30, "Over 8.5 corner": 1.90, "Over 4.5 cartellini": 1.80}}
    )
    result = simulate_match(config)
    assert result["financial"]["quotes_provided"] == 4
    assert result["financial"]["best_value"] is not None
    assert result["smart_combo"]["recommendation"] is not None
    assert len(result["smart_combo"]["recommendation"]["legs"]) == 2


def test_report_is_consistent_with_returned_probabilities():
    result = simulate_match(config_from_input(parse_match_input(VALID), simulations=3000, seed=2))
    report = result["statistical_report"]
    p1 = result["markets"]["1x2"]["1"]["percentage"]
    assert f"{p1:.2f}%" in report
    assert f"λ={result['model']['lambda']:.3f}" in report
