"""Transparent on-demand football probability engine.

All predictions are derived from the supplied match input. No database,
calendar, bookmaker fallback, narrative template, or hidden team defaults is
used here.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Mapping

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
    odds: dict[str, float] | None = None


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


def _event_catalog(home: np.ndarray, away: np.ndarray, corners: np.ndarray, cards: np.ndarray) -> dict[str, np.ndarray]:
    total = home + away
    events = {
        "1": home > away,
        "1X": home >= away,
        "X": home == away,
        "X2": away >= home,
        "2": home < away,
        "Over 1.5 gol": total > 1.5,
        "Over 2.5 gol": total > 2.5,
        "Under 2.5 gol": total < 2.5,
        "Under 3.5 gol": total < 3.5,
        "Goal": (home > 0) & (away > 0),
        "No Goal": (home == 0) | (away == 0),
        "Over 8.5 corner": corners > 8.5,
        "Under 8.5 corner": corners < 8.5,
        "Over 4.5 cartellini": cards > 4.5,
        "Under 4.5 cartellini": cards < 4.5,
    }
    for low, high in ((1, 2), (1, 3), (2, 4), (2, 5)):
        events[f"Multigol {low}-{high}"] = (total >= low) & (total <= high)
    for threshold in (7.5, 8.5, 9.5, 10.5):
        events[f"Over {threshold:g} corner"] = corners > threshold
        events[f"Under {threshold:g} corner"] = corners < threshold
    for threshold in (3.5, 4.5, 5.5, 6.5):
        events[f"Over {threshold:g} cartellini"] = cards > threshold
        events[f"Under {threshold:g} cartellini"] = cards < threshold
    return events


def _probability(mask: np.ndarray) -> float:
    return float(mask.mean())


def financial_analysis(events: Mapping[str, np.ndarray], odds: Mapping[str, float] | None) -> dict[str, Any]:
    """Calculate fair probability, EV and quarter-Kelly stake for user odds."""
    candidates: list[dict[str, Any]] = []
    for market, raw_odd in (odds or {}).items():
        if market not in events:
            continue
        try:
            odd = float(raw_odd)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(odd) or odd <= 1.0:
            continue
        probability = _probability(events[market])
        edge = probability - (1.0 / odd)
        ev = probability * odd - 1.0
        denominator = odd - 1.0
        full_kelly = max(0.0, (probability * odd - 1.0) / denominator) if denominator else 0.0
        candidates.append({
            "market": market,
            "odds": odd,
            "simulated_probability_pct": round(probability * 100.0, 2),
            "implied_probability_pct": round(100.0 / odd, 2),
            "edge_pct": round(edge * 100.0, 2),
            "ev_pct": round(ev * 100.0, 2),
            "kelly_pct": round(full_kelly * 100.0, 2),
            "recommended_quarter_kelly_pct": round(full_kelly * 25.0, 2),
            "is_value": ev > 0.0,
        })
    candidates.sort(key=lambda item: (item["ev_pct"], item["edge_pct"]), reverse=True)
    return {
        "quotes_provided": len(candidates),
        "markets": candidates,
        "best_value": candidates[0] if candidates else None,
        "risk_note": "Kelly è una stima sensibile all'errore del modello; viene mostrato un quarto Kelly, non una garanzia.",
    }


def smart_combo(events: Mapping[str, np.ndarray], odds: Mapping[str, float] | None) -> dict[str, Any]:
    """Select a conservative mixed-market double when both legs have quotes."""
    if not odds:
        return {"status": "no_quotes", "legs": [], "message": "Inserire almeno due quote per calcolare una schedina."}
    preferred = (
        ("1X", "Over 1.5 gol"),
        ("X2", "Under 3.5 gol"),
        ("Multigol 2-4", "Under 8.5 corner"),
        ("Over 8.5 corner", "Over 4.5 cartellini"),
    )
    options: list[dict[str, Any]] = []
    for first, second in preferred:
        if first not in events or second not in events or first not in odds or second not in odds:
            continue
        try:
            odd_a, odd_b = float(odds[first]), float(odds[second])
        except (TypeError, ValueError):
            continue
        if odd_a <= 1.0 or odd_b <= 1.0:
            continue
        joint = events[first] & events[second]
        probability = _probability(joint)
        total_odd = odd_a * odd_b
        options.append({
            "legs": [first, second],
            "odds": [odd_a, odd_b],
            "combined_odds": round(total_odd, 3),
            "simulated_probability_pct": round(probability * 100.0, 2),
            "ev_pct": round((probability * total_odd - 1.0) * 100.0, 2),
            "joint_count": int(joint.sum()),
        })
    options.sort(key=lambda item: (item["ev_pct"], item["simulated_probability_pct"]), reverse=True)
    return {
        "status": "ready" if options else "insufficient_quotes",
        "recommendation": options[0] if options else None,
        "candidates": options,
        "message": "La probabilità è congiunta sui campioni simulati, non il prodotto di probabilità indipendenti.",
    }


def statistical_report(config: MatchConfig, result: Mapping[str, Any]) -> str:
    """Generate a metric-only contextual report, with no fixed football claims."""
    model = result["model"]
    summary = result["summary"]
    markets = result["markets"]
    home, away = config.home.name, config.away.name
    p1, px, p2 = (markets["1x2"][key]["percentage"] for key in ("1", "X", "2"))
    leader = home if p1 >= max(px, p2) else away if p2 >= px else "il pareggio"
    score = summary["modal_score"]
    xg_gap = model["lambda"] - model["mu"]
    direction = "favore casa" if xg_gap > 0 else "favore ospite" if xg_gap < 0 else "equilibrato"
    return (
        f"Sintesi statistica: {leader} è l'esito 1X2 più frequente "
        f"({max(p1, px, p2):.2f}%). λ={model['lambda']:.3f}, μ={model['mu']:.3f}, "
        f"scarto xG {xg_gap:+.3f} ({direction}). Score modale "
        f"{score['home']}-{score['away']} nel {score['share_pct']:.2f}% dei campioni. "
        f"Over 2.5: {markets['over_under']['Over_2.5']['percentage']:.2f}%; "
        f"Goal: {markets['goal_no_goal']['Goal']['percentage']:.2f}%. "
        f"Il risultato è descrittivo della simulazione, non una certezza."
    )


def simulate_match(config: MatchConfig) -> dict[str, Any]:
    lambda_, mu, ledger = expected_goals(config)
    matrix = dixon_coles_matrix(lambda_, mu, config.dixon_coles_rho)
    rng = np.random.default_rng(config.seed)
    size = matrix.shape[0]
    choices = rng.choice(matrix.size, size=config.simulations, p=matrix.ravel())
    home = choices // size
    away = choices % size
    first_half_matrix = dixon_coles_matrix(lambda_ / 2.0, mu / 2.0, config.dixon_coles_rho)
    first_half_choices = rng.choice(first_half_matrix.size, size=config.simulations, p=first_half_matrix.ravel())
    first_half_size = first_half_matrix.shape[0]
    first_home = first_half_choices // first_half_size
    first_away = first_half_choices % first_half_size
    total = home + away
    corner_mean = max(0.1, np.mean([config.home.corners_for, config.away.corners_for, config.home.corners_against, config.away.corners_against]) * 4.5)
    cards_mean = max(0.1, np.mean([config.home.cards_for, config.away.cards_for, config.referee_yellow_avg]))
    corners = rng.poisson(corner_mean, config.simulations)
    cards = rng.poisson(cards_mean, config.simulations)
    events = _event_catalog(home, away, corners, cards)
    markets = {
        "1x2": {"1": _market(home > away), "X": _market(home == away), "2": _market(home < away)},
        "first_half_1x2": {"1": _market(first_home > first_away), "X": _market(first_home == first_away), "2": _market(first_home < first_away)},
        "over_under": {
            **{f"Over_{threshold}": _market(total > threshold) for threshold in (0.5, 1.5, 2.5, 3.5)},
            **{f"Under_{threshold}": _market(total < threshold) for threshold in (0.5, 1.5, 2.5, 3.5)},
        },
        "multigol": {f"{low}-{high}": _market((total >= low) & (total <= high)) for low, high in ((1, 2), (1, 3), (2, 4), (2, 5))},
        "goal_no_goal": {"Goal": _market((home > 0) & (away > 0)), "No_Goal": _market((home == 0) | (away == 0))},
        "corners": {
            "mean": round(float(corners.mean()), 3),
            **{f"Over_{threshold:g}": _market(corners > threshold) for threshold in (7.5, 8.5, 9.5, 10.5)},
            **{f"Under_{threshold:g}": _market(corners < threshold) for threshold in (7.5, 8.5, 9.5, 10.5)},
        },
        "cards": {
            "mean": round(float(cards.mean()), 3),
            **{f"Over_{threshold:g}": _market(cards > threshold) for threshold in (3.5, 4.5, 5.5, 6.5)},
            **{f"Under_{threshold:g}": _market(cards < threshold) for threshold in (3.5, 4.5, 5.5, 6.5)},
        },
    }
    outcomes = {"1": home > away, "X": home == away, "2": home < away}
    score_pairs, counts = np.unique(np.column_stack((home, away)), axis=0, return_counts=True)
    mode = score_pairs[int(np.argmax(counts))]
    result = {
        "input": {"home": config.home.__dict__, "away": config.away.__dict__, "referee_yellow_avg": config.referee_yellow_avg, "referee_fouls_avg": config.referee_fouls_avg},
        "model": {"lambda": round(lambda_, 6), "mu": round(mu, 6), "dixon_coles_rho": config.dixon_coles_rho, "simulation_count": config.simulations, "seed": config.seed, "formula_ledger": ledger},
        "markets": markets,
        "summary": {
            "modal_score": {"home": int(mode[0]), "away": int(mode[1]), "share_pct": round(float(counts.max() / config.simulations * 100), 2)},
            "confidence_intervals_95": {key: _confidence(mask) for key, mask in outcomes.items()},
        },
    }
    interval_width = np.mean([
        bounds[1] - bounds[0]
        for bounds in result["summary"]["confidence_intervals_95"].values()
    ])
    result["summary"]["reliability"] = {
        "index_pct": round(float(np.clip(100.0 - interval_width, 0.0, 100.0)), 2),
        "method": "100 - media ampiezza degli intervalli Wilson 95% sugli esiti 1X2",
        "warning": "Non misura la qualità dei dati di input o la correttezza del modello.",
    }
    result["financial"] = financial_analysis(events, getattr(config, "odds", None))
    result["smart_combo"] = smart_combo(events, getattr(config, "odds", None))
    result["statistical_report"] = statistical_report(config, result)
    result["dashboard"] = {
        "goals_distribution": {
            "goals": list(range(0, 8)),
            "home": [round(float(np.mean(home == value) * 100), 2) for value in range(0, 8)],
            "away": [round(float(np.mean(away == value) * 100), 2) for value in range(0, 8)],
        },
        "strength_comparison": {
            "labels": ["Attacco", "Difesa inversa", "xG fatti", "xG subiti", "Elo normalizzato"],
            "home": [config.home.attack, 1 / config.home.defense, config.home.xg_for, config.home.xg_against, config.home.elo / 1500],
            "away": [config.away.attack, 1 / config.away.defense, config.away.xg_for, config.away.xg_against, config.away.elo / 1500],
        },
    }
    return result
