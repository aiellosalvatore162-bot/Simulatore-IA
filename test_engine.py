"""
Test di integrità e performance per il motore Monte Carlo Dixon-Coles
Verifica coerenza matematica, somma delle simulazioni e tutti i 15 mercati.
"""

import pytest
from engine import MatchConfig, TeamParams, simulate_match


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


if __name__ == "__main__":
    test_simulation_50k_consistency()
    print("Tutti i test sono stati superati con successo!")
