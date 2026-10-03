"""Metriche derivate per analisi calcistica e scouting.

Le funzioni di questo modulo sono additive: consumano campioni e parametri gia
prodotti dal motore, senza cambiare la simulazione o i mercati esistenti.
"""

from typing import Any, Dict

import numpy as np

def _entropy(probabilities: np.ndarray) -> float:
    values = probabilities[probabilities > 0.0]
    return float(-np.sum(values * np.log2(values)))


def _wilson_interval(successes: int, total: int, z: float = 1.96) -> Dict[str, float]:
    if total <= 0:
        return {"lower_pct": 0.0, "upper_pct": 0.0}
    proportion = successes / total
    denominator = 1.0 + (z * z / total)
    center = (proportion + (z * z / (2.0 * total))) / denominator
    margin = (z / denominator) * np.sqrt(
        (proportion * (1.0 - proportion) / total) + (z * z / (4.0 * total * total))
    )
    return {
        "lower_pct": round(float(max(0.0, center - margin) * 100.0), 2),
        "upper_pct": round(float(min(1.0, center + margin) * 100.0), 2),
    }


def _form_score(form: str) -> float:
    values = {"W": 1.0, "D": 0.5, "L": 0.0}
    recent = [values.get(item.strip().upper(), 0.5) for item in str(form).split("-")[-5:]]
    return round(float(np.mean(recent) * 100.0), 2) if recent else 50.0


def analyze_simulation(
    config: Any,
    lambda_: float,
    mu: float,
    joint_probs: np.ndarray,
    home_ft: np.ndarray,
    away_ft: np.ndarray,
) -> Dict[str, Any]:
    """Calcola xPts, incertezza, proiezioni e indicatori di scouting.

    Le probabilita Monte Carlo sono confrontate con la matrice teorica per
    evidenziare stabilita del campione e non per correggere il risultato.
    """
    total = int(len(home_ft))
    home_win = home_ft > away_ft
    draw = home_ft == away_ft
    away_win = away_ft > home_ft
    outcome_masks = {"home": home_win, "draw": draw, "away": away_win}
    outcome_probabilities = np.array([mask.mean() for mask in outcome_masks.values()], dtype=np.float64)
    analytic_home = float(np.tril(joint_probs, -1).sum())
    analytic_draw = float(np.trace(joint_probs))
    analytic_away = float(np.triu(joint_probs, 1).sum())
    analytic_outcomes = np.array([analytic_home, analytic_draw, analytic_away], dtype=np.float64)

    points_home = np.where(home_win, 3.0, np.where(draw, 1.0, 0.0))
    points_away = np.where(away_win, 3.0, np.where(draw, 1.0, 0.0))
    xpts_home = float(points_home.mean())
    xpts_away = float(points_away.mean())
    xpts_total = xpts_home + xpts_away
    xpts_home_ci = 1.96 * float(points_home.std(ddof=1) / np.sqrt(total)) if total > 1 else 0.0
    xpts_away_ci = 1.96 * float(points_away.std(ddof=1) / np.sqrt(total)) if total > 1 else 0.0

    confidence_intervals = {
        outcome: _wilson_interval(int(mask.sum()), total)
        for outcome, mask in outcome_masks.items()
    }
    outcome_labels = {"home": config.home_team.name, "draw": "Pareggio", "away": config.away_team.name}
    most_likely_index = int(np.argmax(outcome_probabilities))
    most_likely_outcome = ("home", "draw", "away")[most_likely_index]

    horizon = 38
    projected_points_home = xpts_home * horizon
    projected_points_away = xpts_away * horizon
    projected_home = {
        "team": config.home_team.name,
        "points_per_match": round(xpts_home, 3),
        "points": round(projected_points_home, 2),
        "points_interval": [
            round(max(0.0, xpts_home - xpts_home_ci) * horizon, 2),
            round(min(3.0, xpts_home + xpts_home_ci) * horizon, 2),
        ],
        "wins": round(float(home_win.mean() * horizon), 2),
        "draws": round(float(draw.mean() * horizon), 2),
        "losses": round(float(away_win.mean() * horizon), 2),
        "expected_goals_for": round(lambda_ * horizon, 2),
        "expected_goals_against": round(mu * horizon, 2),
        "expected_goal_difference": round((lambda_ - mu) * horizon, 2),
    }
    projected_away = {
        "team": config.away_team.name,
        "points_per_match": round(xpts_away, 3),
        "points": round(projected_points_away, 2),
        "points_interval": [
            round(max(0.0, xpts_away - xpts_away_ci) * horizon, 2),
            round(min(3.0, xpts_away + xpts_away_ci) * horizon, 2),
        ],
        "wins": round(float(away_win.mean() * horizon), 2),
        "draws": round(float(draw.mean() * horizon), 2),
        "losses": round(float(home_win.mean() * horizon), 2),
        "expected_goals_for": round(mu * horizon, 2),
        "expected_goals_against": round(lambda_ * horizon, 2),
        "expected_goal_difference": round((mu - lambda_) * horizon, 2),
    }

    base_home = max(float(config.base_goals_home), 0.01)
    base_away = max(float(config.base_goals_away), 0.01)
    scouting = {
        "home": {
            "team": config.home_team.name,
            "attack_index": round(lambda_ / base_home, 3),
            "defensive_resistance": round(base_away / max(mu, 0.01), 3),
            "elo": round(float(config.home_team.elo), 2),
            "form_score": _form_score(config.home_team.recent_form),
        },
        "away": {
            "team": config.away_team.name,
            "attack_index": round(mu / base_away, 3),
            "defensive_resistance": round(base_home / max(lambda_, 0.01), 3),
            "elo": round(float(config.away_team.elo), 2),
            "form_score": _form_score(config.away_team.recent_form),
        },
        "elo_gap": round(float(config.home_team.elo - config.away_team.elo), 2),
    }

    return {
        "xpts": {
            "home": round(xpts_home, 4),
            "away": round(xpts_away, 4),
            "total": round(xpts_total, 4),
            "home_share_pct": round(xpts_home / max(xpts_total, 0.01) * 100.0, 2),
            "away_share_pct": round(xpts_away / max(xpts_total, 0.01) * 100.0, 2),
        },
        "uncertainty": {
            "outcome_entropy_bits": round(_entropy(outcome_probabilities), 4),
            "scoreline_entropy_bits": round(_entropy(joint_probs.ravel()), 4),
            "most_likely_outcome": outcome_labels[most_likely_outcome],
            "confidence_intervals_95": confidence_intervals,
            "sample_size": total,
        },
        "long_term_projection": {
            "horizon_matches": horizon,
            "home": projected_home,
            "away": projected_away,
        },
        "scouting_profile": scouting,
        "monte_carlo_diagnostics": {
            "analytic_outcomes_pct": {
                "home": round(analytic_outcomes[0] * 100.0, 2),
                "draw": round(analytic_outcomes[1] * 100.0, 2),
                "away": round(analytic_outcomes[2] * 100.0, 2),
            },
            "sample_outcomes_pct": {
                "home": round(outcome_probabilities[0] * 100.0, 2),
                "draw": round(outcome_probabilities[1] * 100.0, 2),
                "away": round(outcome_probabilities[2] * 100.0, 2),
            },
            "max_probability_deviation_pct": round(float(np.max(np.abs(outcome_probabilities - analytic_outcomes)) * 100.0), 2),
        },
    }
