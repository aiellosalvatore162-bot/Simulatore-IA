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
    assert set(first["markets"]["first_half_goal_no_goal"]) == {"Goal", "No_Goal"}
    assert set(first["markets"]["multigol"]) == {"1-2", "1-3", "2-4", "2-5"}
    assert "Over_10.5" in first["markets"]["corners"]
    assert "Under_6.5" in first["markets"]["cards"]


def test_probabilities_use_the_declared_sample_size():
    result = simulate_match(config_from_input(parse_match_input(VALID), simulations=2000, seed=3))
    assert sum(item["count"] for item in result["markets"]["1x2"].values()) == 2000
    assert result["summary"]["modal_score"]["share_pct"] > 0
    for market in result["markets"]["1x2"].values():
        low, high = market["confidence_interval_95"]
        assert 0 <= low <= high <= 100
        assert 0 <= market["reliability_pct"] <= 100
        assert market["fair_odds"] > 1.0


def test_complete_market_catalog_exposes_all_requested_families():
    result = simulate_match(config_from_input(parse_match_input(VALID), simulations=2000, seed=9))
    markets = result["markets"]
    assert set(markets["double_chance"]) == {"1X", "X2", "12"}
    assert set(markets["second_half_1x2"]) == {"1", "X", "2"}
    assert set(markets["second_half_double_chance"]) == {"1X", "X2", "12"}
    assert set(markets["over_under"]) == {
        "Over_0.5", "Under_0.5", "Over_1.5", "Under_1.5",
        "Over_2.5", "Under_2.5", "Over_3.5", "Under_3.5",
        "Over_4.5", "Under_4.5",
    }
    assert set(markets["multigol_complete"]) == {"1-2", "1-3", "1-4", "2-3", "2-4", "2-5", "3-5", "3-6"}
    assert set(markets["goal_sums"]) == {"0", "1", "2", "3", "4", "5+"}
    assert len(markets["combos"]) >= 10
    assert set(markets["corner_1x2"]) == {"1", "X", "2"}
    assert set(markets["card_1x2"]) == {"1", "X", "2"}


def test_financial_analysis_and_smart_combo_use_joint_samples():
    match = parse_match_input(VALID)
    config = config_from_input(match, simulations=5000, seed=4)
    config = config.__class__(
        **{**config.__dict__, "odds": {"1X": 1.35, "Over 1.5 gol": 1.30, "Over 8.5 corner": 1.90, "Over 4.5 cartellini": 1.80}}
    )
    result = simulate_match(config)
    assert result["financial"]["quotes_provided"] == 4
    assert result["financial"]["best_value"] is not None
    best = result["financial"]["best_value"]
    assert best["recommended_stake_pct"] == best["recommended_quarter_kelly_pct"]
    assert best["kelly_fraction"] == 0.25
    assert len(best["confidence_interval_95"]) == 2
    assert result["smart_combo"]["recommendation"] is not None
    combo = result["smart_combo"]["recommendation"]
    assert len(combo["legs"]) == 2
    assert combo["recommended_stake_pct"] >= 0
    assert 0 <= combo["reliability_pct"] <= 100


def test_quotes_from_parsed_input_reach_value_bet_analysis():
    text = VALID.replace("CASA: Inter", "CASA: Inter | Quota 1: 1.85").replace(
        "OSPITE: Milan", "OSPITE: Milan | Quota X: 3.40 | Quota 2: 4.20"
    )
    result = simulate_match(config_from_input(parse_match_input(text), simulations=2000, seed=5))
    assert {row["market"] for row in result["financial"]["markets"]} == {"1", "X", "2"}
    assert all("recommended_stake_pct" in row for row in result["financial"]["markets"])


def test_dnb_financial_settlement_exposes_push_probability():
    config = config_from_input(parse_match_input(VALID), simulations=4000, seed=6)
    config = config.__class__(**{**config.__dict__, "odds": {"Casa DNB": 1.70}})
    result = simulate_match(config)
    row = result["financial"]["markets"][0]
    assert row["market"] == "Casa DNB"
    assert row["push_probability_pct"] > 0
    assert 0 <= row["loss_probability_pct"] <= 100


def test_report_is_consistent_with_returned_probabilities():
    result = simulate_match(config_from_input(parse_match_input(VALID), simulations=3000, seed=2))
    report = result["statistical_report"]
    p1 = result["markets"]["1x2"]["1"]["percentage"]
    assert f"{p1:.2f}%" in report
    assert f"λ={result['model']['lambda']:.3f}" in report
