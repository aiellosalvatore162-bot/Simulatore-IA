"""Transparent on-demand football probability engine.

All predictions are derived from the supplied match input. No database,
calendar, bookmaker fallback, narrative template, or hidden team defaults is
used here.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

import numpy as np
from scipy.stats import poisson

from parser import MatchInput


@dataclass(frozen=True)
class TeamParams:
    name: str
    attack: float
    defense: float
    elo: float
    form: str
    xg_for: float
    xg_against: float
    corners_for: float
    corners_against: float
    cards_for: float


@dataclass(frozen=True)
class MatchConfig:
    home: TeamParams
    away: TeamParams
    referee_yellow_avg: float
    referee_fouls_avg: float
    simulations: int = 50_000
    seed: int = 42
    home_advantage: float = 1.15
    base_goals_home: float = 1.38
    base_goals_away: float = 1.12
    dixon_coles_rho: float = -0.11


def config_from_input(match: MatchInput, simulations: int = 50_000, seed: int = 42) -> MatchConfig:
    def team(value: Any) -> TeamParams:
        return TeamParams(
            name=value.name,
            attack=value.attack,
            defense=value.defense,
            elo=value.elo,
            form=value.form,
            xg_for=value.xg_for,
            xg_against=value.xg_against,
            corners_for=value.corners_for,
            corners_against=value.corners_against,
            cards_for=value.cards_for,
        )

    return MatchConfig(
        home=team(match.home),
        away=team(match.away),
        referee_yellow_avg=match.referee.yellow_avg,
        referee_fouls_avg=match.referee.fouls_avg,
        simulations=simulations,
        seed=seed,
    )


def _form_multiplier(form: str) -> float:
    values = {"W": 1.06, "D": 1.0, "L": 0.94}
    tokens = form.split("-")
    weights = np.array([0.7 ** index for index in range(len(tokens) - 1, -1, -1)])
    factors = np.array([values[token] for token in tokens])
    return float(np.average(factors, weights=weights))


def expected_goals(config: MatchConfig) -> tuple[float, float, dict[str, Any]]:
    """Return lambda/mu and a complete, human-readable contribution ledger."""
    elo_delta = config.home.elo - config.away.elo
    elo_home = 10.0 ** (elo_delta / 2400.0)
    elo_away = 10.0 ** (-elo_delta / 2400.0)
    home_form = _form_multiplier(config.home.form)
    away_form = _form_multiplier(config.away.form)

    home_xg_signal = np.mean([config.home.xg_for / config.base_goals_home, config.away.xg_against / config.base_goals_home])
    away_xg_signal = np.mean([config.away.xg_for / config.base_goals_away, config.home.xg_against / config.base_goals_away])
    home_attack = (config.home.attack ** 0.35) * (1.0 / config.away.defense) ** 0.25
    away_attack = (config.away.attack ** 0.35) * (1.0 / config.home.defense) ** 0.25
    home_strength = home_attack * (home_xg_signal ** 0.20) * (home_form ** 0.10) * (elo_home ** 0.10)
    away_strength = away_attack * (away_xg_signal ** 0.20) * (away_form ** 0.10) * (elo_away ** 0.10)
    lambda_ = float(np.clip(config.base_goals_home * config.home_advantage * home_strength, 0.05, 5.0))
    mu = float(np.clip(config.base_goals_away * away_strength, 0.05, 5.0))
    ledger = {
        "formula": "lambda = base_home * home_advantage * attack^0.35 * opponent_defense^-0.25 * xG^0.20 * form^0.10 * Elo^0.10",
        "home": {"attack_signal": home_attack, "xg_signal": home_xg_signal, "form_multiplier": home_form, "elo_multiplier": elo_home},
        "away": {"attack_signal": away_attack, "xg_signal": away_xg_signal, "form_multiplier": away_form, "elo_multiplier": elo_away},
        "weights": {"attack": 0.35, "opponent_defense": 0.25, "xg": 0.20, "form": 0.10, "elo": 0.10},
    }
    return lambda_, mu, ledger


def dixon_coles_matrix(lambda_: float, mu: float, rho: float, max_goals: int = 12) -> np.ndarray:
    goals = np.arange(max_goals + 1)
    matrix = np.outer(poisson.pmf(goals, lambda_), poisson.pmf(goals, mu))
    corrections = {(0, 0): 1 - lambda_ * mu * rho, (0, 1): 1 + mu * rho, (1, 0): 1 + lambda_ * rho, (1, 1): 1 - rho}
    for (home, away), factor in corrections.items():
        matrix[home, away] *= max(0.0, factor)
    return matrix / matrix.sum()


def _market(mask: np.ndarray) -> dict[str, float | int]:
    count = int(mask.sum())
    return {"count": count, "percentage": round(count / len(mask) * 100.0, 2)}


def _confidence(mask: np.ndarray) -> list[float]:
    n = len(mask)
    p = float(mask.mean())
    z = 1.96
    denominator = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denominator
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denominator
    return [round(max(0.0, center - margin) * 100, 2), round(min(1.0, center + margin) * 100, 2)]


def simulate_match(config: MatchConfig) -> dict[str, Any]:
    lambda_, mu, ledger = expected_goals(config)
    matrix = dixon_coles_matrix(lambda_, mu, config.dixon_coles_rho)
    rng = np.random.default_rng(config.seed)
    size = matrix.shape[0]
    choices = rng.choice(matrix.size, size=config.simulations, p=matrix.ravel())
    home = choices // size
    away = choices % size
    total = home + away
    corner_mean = max(0.1, np.mean([config.home.corners_for, config.away.corners_for, config.home.corners_against, config.away.corners_against]) * 4.5)
    cards_mean = max(0.1, np.mean([config.home.cards_for, config.away.cards_for, config.referee_yellow_avg]))
    corners = rng.poisson(corner_mean, config.simulations)
    cards = rng.poisson(cards_mean, config.simulations)
    markets = {
        "1x2": {"1": _market(home > away), "X": _market(home == away), "2": _market(home < away)},
        "over_under": {f"Over_{threshold}": _market(total > threshold) for threshold in (0.5, 1.5, 2.5, 3.5)},
        "goal_no_goal": {"Goal": _market((home > 0) & (away > 0)), "No_Goal": _market((home == 0) | (away == 0))},
        "corners": {"mean": round(float(corners.mean()), 3), "Over_8.5": _market(corners > 8.5), "Under_8.5": _market(corners < 8.5)},
        "cards": {"mean": round(float(cards.mean()), 3), "Over_4.5": _market(cards > 4.5), "Under_4.5": _market(cards < 4.5)},
    }
    outcomes = {"1": home > away, "X": home == away, "2": home < away}
    score_pairs, counts = np.unique(np.column_stack((home, away)), axis=0, return_counts=True)
    mode = score_pairs[int(np.argmax(counts))]
    return {
        "input": {"home": config.home.__dict__, "away": config.away.__dict__, "referee_yellow_avg": config.referee_yellow_avg, "referee_fouls_avg": config.referee_fouls_avg},
        "model": {"lambda": round(lambda_, 6), "mu": round(mu, 6), "dixon_coles_rho": config.dixon_coles_rho, "simulation_count": config.simulations, "seed": config.seed, "formula_ledger": ledger},
        "markets": markets,
        "summary": {
            "modal_score": {"home": int(mode[0]), "away": int(mode[1]), "share_pct": round(float(counts.max() / config.simulations * 100), 2)},
            "confidence_intervals_95": {key: _confidence(mask) for key, mask in outcomes.items()},
        },
    }
