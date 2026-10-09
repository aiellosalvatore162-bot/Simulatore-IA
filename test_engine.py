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


def test_probabilities_use_the_declared_sample_size():
    result = simulate_match(config_from_input(parse_match_input(VALID), simulations=2000, seed=3))
    assert sum(item["count"] for item in result["markets"]["1x2"].values()) == 2000
    assert result["summary"]["modal_score"]["share_pct"] > 0
