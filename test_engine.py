"""
Test di integrità e performance per il motore Monte Carlo Dixon-Coles
Verifica coerenza matematica, somma delle simulazioni e tutti i 15 mercati.
"""

import pytest
from engine import MatchConfig, TeamParams, calculate_expected_goals, calculate_team_strength, simulate_match


def test_simulation_50k_consistency():
    config = MatchConfig(
        home_team=TeamParams(name="Inter", attack=1.3, defense=0.85, elo=1820),
        away_team=TeamParams(name="Milan", attack=1.1, defense=0.95, elo=1740),
        n_simulations=50_000,
        seed=42,
    )
    res = simulate_match(config)
    meta = res["metadata"]
    markets = res["markets"]
    convergence = res["market_convergence"]

    # Verifica metadati
    assert meta["simulations_count"] == 50_000
    assert meta["execution_time_ms"] < 300.0  # Esecuzione rapida
    assert meta["expected_goals_home_lambda"] > 0.0
    assert meta["expected_goals_away_mu"] > 0.0

    # 1. Verifica 1X2 FT
    count_1x2 = sum(v["count"] for v in markets["1x2_finale"].values())
    assert count_1x2 == 50_000

    # 2. Verifica 1X2 HT
    count_1x2_ht = sum(v["count"] for v in markets["1x2_primo_tempo"].values())
    assert count_1x2_ht == 50_000

    # 3. Verifica Goal / No Goal FT
    count_gg_ng = markets["goal_nogoal_finale"]["Goal"]["count"] + markets["goal_nogoal_finale"]["No_Goal"]["count"]
    assert count_gg_ng == 50_000

    # 4. Verifica Over / Under 2.5 FT
    ou_25 = markets["over_under_finale"]["Over_2.5"]["count"] + markets["over_under_finale"]["Under_2.5"]["count"]
    # Nota: il totale può escludere esattamente 2.5 (che è non intero, quindi la somma è 50000 esatta)
    assert ou_25 == 50_000

    # 5. Verifica presenza di tutti i 15 mercati
    expected_markets = [
        "1x2_finale",
        "1x2_primo_tempo",
        "over_under_finale",
        "over_under_primo_tempo",
        "goal_nogoal_finale",
        "goal_nogoal_primo_tempo",
        "cartellini",
        "calci_dangolo",
        "multigol_partita",
        "multigol_casa",
        "multigol_ospite",
        "multigol_casa_combo_ospite",
        "multigol_primo_tempo_combo_secondo_tempo",
        "over_under_squadra_casa",
        "over_under_squadra_ospite",
    ]
    for m in expected_markets:
        assert m in markets, f"Mercato {m} mancante!"

    # 6. Verifica convergenza
    assert "best_synergy_market" in convergence
    assert "assistant_explanation" in convergence
    assert len(convergence["assistant_explanation"]) > 50


def test_form_affects_expected_goals_and_all_requested_ranges_exist():
    strong_form = MatchConfig(
        home_team=TeamParams(name="Home", recent_form="W-W-W-W-W"),
        away_team=TeamParams(name="Away", recent_form="L-L-L-L-L"),
    )
    weak_form = MatchConfig(
        home_team=TeamParams(name="Home", recent_form="L-L-L-L-L"),
        away_team=TeamParams(name="Away", recent_form="W-W-W-W-W"),
    )
    strong_lambda, strong_mu = calculate_expected_goals(strong_form)
    weak_lambda, weak_mu = calculate_expected_goals(weak_form)
    assert strong_lambda > weak_lambda
    assert strong_mu < weak_mu

    markets = simulate_match(MatchConfig(
        home_team=TeamParams(name="Home"),
        away_team=TeamParams(name="Away"),
        n_simulations=2_000,
        seed=7,
    ))["markets"]
    for market_name in ("multigol_partita", "multigol_casa", "multigol_ospite"):
        for key in ("0_2", "0_3", "1_4", "2_4", "2_5", "2_6", "3_4", "3_5", "3_6"):
            assert key in markets[market_name]
    for key in ("Over_0.5", "Under_0.5", "Over_4.5", "Under_4.5"):
        assert key in markets["over_under_finale"]

    assert calculate_team_strength(strong_form.home_team) > calculate_team_strength(weak_form.home_team)


def test_custom_bookmaker_quote_is_used_for_value_bet():
    result = simulate_match(
        MatchConfig(
            home_team=TeamParams(name="Home"),
            away_team=TeamParams(name="Away"),
            n_simulations=2_000,
            seed=11,
        ),
        custom_odds={"over_under_finale:Under_4.5": 5.0},
    )
    bets = result["value_betting"]["all_value_bets"]
    assert any(bet["market"] == "over_under_finale: Under 4.5" and bet["odds"] == 5.0 for bet in bets)


def test_simulation_can_run_without_odds():
    result = simulate_match(
        MatchConfig(
            home_team=TeamParams(name="Home", xg_for=1.8, xg_against=1.1),
            away_team=TeamParams(name="Away", xg_for=1.2, xg_against=1.4),
            n_simulations=2_000,
            seed=12,
        ),
        custom_odds={},
    )
    assert result["market_odds"] == {}
    assert result["value_betting"]["best_value_bet"] is None
    assert result["metadata"]["expected_goals_home_lambda"] != result["metadata"]["expected_goals_away_mu"]


def test_metadata_reports_applied_xg_inputs():
    result = simulate_match(
        MatchConfig(
            home_team=TeamParams(name="Home", xg_for=1.7, xg_against=1.0),
            away_team=TeamParams(name="Away", xg_for=1.1, xg_against=1.3),
            n_simulations=1_000,
            seed=3,
        ),
        custom_odds={},
    )
    assert result["metadata"]["xg_inputs"]["applied"] is True
    assert result["metadata"]["xg_inputs"]["home_xg_for"] == 1.7


def test_different_xg_inputs_change_probabilities():
    low = simulate_match(
        MatchConfig(
            home_team=TeamParams(name="Home"),
            away_team=TeamParams(name="Away"),
            n_simulations=10_000,
            seed=21,
        ),
        custom_odds={},
    )
    high = simulate_match(
        MatchConfig(
            home_team=TeamParams(name="Home", xg_for=3.2, xg_against=0.4),
            away_team=TeamParams(name="Away", xg_for=0.4, xg_against=3.2),
            n_simulations=10_000,
            seed=21,
        ),
        custom_odds={},
    )
    assert high["metadata"]["expected_goals_home_lambda"] > low["metadata"]["expected_goals_home_lambda"]
    assert high["markets"]["1x2_finale"]["1"]["percentage"] > low["markets"]["1x2_finale"]["1"]["percentage"]


if __name__ == "__main__":
    test_simulation_50k_consistency()
    print("Tutti i test sono stati superati con successo!")
