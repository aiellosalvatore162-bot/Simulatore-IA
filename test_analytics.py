from engine import MatchConfig, TeamParams, simulate_match


def test_advanced_analytics_reports_xpts_and_projection():
    result = simulate_match(MatchConfig(
        home_team=TeamParams(name="Casa", elo=1650, recent_form="W-D-W-L-W"),
        away_team=TeamParams(name="Ospite", elo=1580, recent_form="D-L-W-D-L"),
        n_simulations=5_000,
        seed=19,
    ))

    analytics = result["advanced_analytics"]
    assert 0.0 <= analytics["xpts"]["home"] <= 3.0
    assert 0.0 <= analytics["xpts"]["away"] <= 3.0
    assert analytics["long_term_projection"]["horizon_matches"] == 38
    assert analytics["long_term_projection"]["home"]["points"] >= 0.0
    assert analytics["long_term_projection"]["away"]["expected_goals_for"] > 0.0


def test_advanced_analytics_intervals_and_diagnostics_are_bounded():
    result = simulate_match(MatchConfig(
        home_team=TeamParams(name="Casa"),
        away_team=TeamParams(name="Ospite"),
        n_simulations=2_000,
        seed=23,
    ))

    analytics = result["advanced_analytics"]
    intervals = analytics["uncertainty"]["confidence_intervals_95"]
    assert analytics["uncertainty"]["sample_size"] == 2_000
    assert 0.0 <= analytics["uncertainty"]["outcome_entropy_bits"] <= 1.585
    for interval in intervals.values():
        assert 0.0 <= interval["lower_pct"] <= interval["upper_pct"] <= 100.0

    diagnostics = analytics["monte_carlo_diagnostics"]
    assert diagnostics["max_probability_deviation_pct"] < 10.0
    assert set(analytics["scouting_profile"]) == {"home", "away", "elo_gap"}
