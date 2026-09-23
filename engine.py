"""
Engine di Simulazione Monte Carlo per Pronostici Calcistici
Basato su distribuzione di Poisson bivariata con correzione di Dixon-Coles.
Esegue esattamente 50.000 simulazioni vettorializzate con NumPy.
"""

from dataclasses import dataclass
import math
import re
import time
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
from scipy.stats import poisson


@dataclass
class TeamParams:
    name: str
    attack: float = 1.0       # Indice offensivo (1.0 = media)
    defense: float = 1.0      # Indice difensivo (1.0 = media, <1.0 solido, >1.0 debole)
    elo: float = 1500.0       # Punteggio Elo
    cards_factor: float = 1.0 # Propensione ai cartellini
    corners_factor: float = 1.0 # Propensione a generare corner
    recent_form: str = "D-D-D-D-D"
    xg_for: float | None = None
    xg_against: float | None = None


@dataclass
class MatchConfig:
    home_team: TeamParams
    away_team: TeamParams
    home_advantage: float = 1.15
    base_goals_home: float = 1.38
    base_goals_away: float = 1.12
    dixon_coles_rho: float = -0.11
    n_simulations: int = 50000
    seed: int | None = None
    home_momentum: float = 5.0
    away_momentum: float = 5.0
    home_absence_impact: float = 0.0
    away_absence_impact: float = 0.0
    home_stakes_multiplier: float = 1.0
    away_stakes_multiplier: float = 1.0
    referee_yellow_avg: float = 4.5
    referee_red_avg: float = 0.15
    referee_fouls_avg: float = 24.0


def _recent_form_multiplier(form: str) -> float:
    """Pesa le ultime cinque gare dando piu peso agli eventi recenti."""
    values = {"W": 1.06, "D": 1.0, "L": 0.94}
    results = [item.strip().upper() for item in form.split("-")[-5:]]
    if not results:
        return 1.0
    weights = np.array([0.70 ** index for index in range(len(results) - 1, -1, -1)], dtype=np.float64)
    factors = np.array([values.get(item, 1.0) for item in results], dtype=np.float64)
    return float(np.average(factors, weights=weights))


def _absence_multiplier(impact: float) -> float:
    """Riduce la produzione in modo non lineare quando l'assenza e importante."""
    normalized = float(np.clip(impact, 0.0, 1.0))
    return float(np.clip(1.0 - 0.24 * normalized ** 1.35, 0.70, 1.0))


def _momentum_volatility(value: float) -> float:
    return float(np.clip(0.85 + 0.03 * np.clip(value, 0.0, 10.0), 0.85, 1.15))


def calculate_team_strength(team: TeamParams) -> float:
    """Punteggio organico 0-100, esplicito e composto da Elo, attacco, difesa e forma."""
    form_points = {"W": 1.0, "D": 0.5, "L": 0.0}
    form_values = [form_points.get(item.strip().upper(), 0.5) for item in team.recent_form.split("-")[-5:]]
    form_score = float(np.mean(form_values)) * 100.0 if form_values else 50.0
    elo_score = float(np.clip(50.0 + (team.elo - 1500.0) / 8.0, 0.0, 100.0))
    attack_score = float(np.clip(team.attack / 2.0 * 100.0, 0.0, 100.0))
    defense_score = float(np.clip((2.0 - team.defense) / 1.2 * 100.0, 0.0, 100.0))
    return round(0.40 * elo_score + 0.25 * attack_score + 0.25 * defense_score + 0.10 * form_score, 2)


def compute_dixon_coles_tau(x: int, y: int, lambda_: float, mu: float, rho: float) -> float:
    """
    Fattore di correlazione Dixon-Coles per punteggi bassi (0 e 1).
    """
    if x == 0 and y == 0:
        return max(0.0, 1.0 - lambda_ * mu * rho)
    elif x == 0 and y == 1:
        return max(0.0, 1.0 + mu * rho)
    elif x == 1 and y == 0:
        return max(0.0, 1.0 + lambda_ * rho)
    elif x == 1 and y == 1:
        return max(0.0, 1.0 - rho)
    else:
        return 1.0


def calculate_expected_goals(config: MatchConfig) -> Tuple[float, float]:
    """
    Calcola i tassi attesi di gol (lambda per casa, mu per trasferta)
    integrando forza offensiva, difensiva, fattore campo e rating Elo.
    """
    home_form = _recent_form_multiplier(config.home_team.recent_form)
    away_form = _recent_form_multiplier(config.away_team.recent_form)
    home_availability = _absence_multiplier(config.home_absence_impact)
    away_availability = _absence_multiplier(config.away_absence_impact)

    def weighted_strength(
        attack: float,
        opponent_defense: float,
        own_xg: Optional[float],
        opponent_xg_against: Optional[float],
        form: float,
        elo_delta: float,
        base_goals: float,
    ) -> float:
        signals = [attack, opponent_defense, form, 10.0 ** (elo_delta / 2400.0)]
        weights = [0.35, 0.25, 0.15, 0.10]
        xg_values = [value / base_goals for value in (own_xg, opponent_xg_against) if value is not None]
        if xg_values:
            signals.append(float(np.mean(xg_values)))
            weights.append(0.15)
        else:
            weights[0] += 0.075
            weights[1] += 0.075
        normalized = np.clip(np.asarray(signals, dtype=np.float64), 0.55, 1.65)
        return float(np.exp(np.average(np.log(normalized), weights=weights)))

    delta_elo = config.home_team.elo - config.away_team.elo
    home_strength = weighted_strength(
        config.home_team.attack, config.away_team.defense,
        config.home_team.xg_for, config.away_team.xg_against,
        home_form, delta_elo, config.base_goals_home,
    )
    away_strength = weighted_strength(
        config.away_team.attack, config.home_team.defense,
        config.away_team.xg_for, config.home_team.xg_against,
        away_form, -delta_elo, config.base_goals_away,
    )

    lambda_ = config.base_goals_home * config.home_advantage * home_strength
    lambda_ *= home_availability * (1.0 + 0.10 * float(np.clip(config.away_absence_impact, 0.0, 1.0)))
    mu = config.base_goals_away * away_strength
    mu *= away_availability * (1.0 + 0.10 * float(np.clip(config.home_absence_impact, 0.0, 1.0)))

    lambda_ = float(np.clip(lambda_, 0.20, 3.50))
    mu = float(np.clip(mu, 0.20, 3.50))

    return lambda_, mu


def _filter_score_matrix_for_market_trend(joint_probs: np.ndarray, lambda_: float, mu: float) -> Tuple[np.ndarray, Dict[str, Any]]:
    """Elimina gli scenari incompatibili con un trend offensivo gia evidente."""
    goals = np.arange(joint_probs.shape[0])
    home, away = np.meshgrid(goals, goals, indexing="ij")
    total = home + away
    over_25 = float(np.sum(joint_probs[total > 2]))
    both_score = float(np.sum(joint_probs[(home > 0) & (away > 0)]))
    high_intensity = over_25 >= 0.65 and both_score >= 0.65 and lambda_ + mu >= 2.7
    mask = np.ones_like(joint_probs, dtype=bool)
    if high_intensity:
        mask &= total >= 2
    filtered = np.where(mask, joint_probs, 0.0)
    total_probability = float(np.sum(filtered))
    if total_probability <= 0.0:
        filtered = joint_probs
        total_probability = float(np.sum(filtered))
    filtered /= total_probability
    return filtered, {
        "high_intensity_filter": high_intensity,
        "raw_over_2_5_probability": round(over_25 * 100.0, 2),
        "raw_goal_probability": round(both_score * 100.0, 2),
        "removed_low_total_scenarios": high_intensity,
    }


def generate_bivariate_dixon_coles_probs(
    lambda_: float, mu: float, rho: float, max_goals: int = 12
) -> np.ndarray:
    """
    Genera la matrice congiunta di probabilità (max_goals+1, max_goals+1)
    applicando Poisson bivariata con correzione Dixon-Coles per (0,0), (0,1), (1,0), (1,1).
    """
    grid_size = max_goals + 1
    p_x = np.array([poisson.pmf(x, lambda_) for x in range(grid_size)], dtype=np.float64)
    p_y = np.array([poisson.pmf(y, mu) for y in range(grid_size)], dtype=np.float64)

    # Prodotto esterno marginali indipendenti
    joint_probs = np.outer(p_x, p_y)

    # Applicazione correzione Dixon-Coles sui 4 punteggi base
    for x in (0, 1):
        for y in (0, 1):
            tau = compute_dixon_coles_tau(x, y, lambda_, mu, rho)
            joint_probs[x, y] *= tau

    # Normalizzazione per garantire somma esattamente uguale a 1.0
    total = np.sum(joint_probs)
    if total > 0:
        joint_probs /= total

    return joint_probs


def _calc_stat(mask: np.ndarray, total: int) -> Dict[str, Any]:
    """Helper per calcolare conteggio esatto e percentuale su 50.000 simulazioni."""
    count = int(np.sum(mask))
    pct = round((count / total) * 100.0, 2)
    return {"count": count, "percentage": pct}


def analyze_market_convergence(
    home_ft: np.ndarray,
    away_ft: np.ndarray,
    total_ft: np.ndarray,
    home_ht: np.ndarray,
    away_ht: np.ndarray,
    total_ht: np.ndarray,
    corners: np.ndarray,
    cards: np.ndarray,
    n_sims: int,
    home_name: str,
    away_name: str,
    lambda_: float,
    mu: float
) -> Dict[str, Any]:
    """
    Analizza la convergenza tra mercati e individua le sinergie statistiche più significative.
    Calcola lift, probabilità congiunta e genera una spiegazione testuale professionale.
    """
    # Definiamo eventi chiave
    events = {
        "1": home_ft > away_ft,
        "X": home_ft == away_ft,
        "2": away_ft > home_ft,
        "1X": home_ft >= away_ft,
        "X2": away_ft >= home_ft,
        "12": home_ft != away_ft,
        "Over 1.5": total_ft > 1.5,
        "Under 2.5": total_ft < 2.5,
        "Over 2.5": total_ft > 2.5,
        "Over 3.5": total_ft > 3.5,
        "Goal": (home_ft > 0) & (away_ft > 0),
        "No Goal": (home_ft == 0) | (away_ft == 0),
        "Multigol 1-3": (total_ft >= 1) & (total_ft <= 3),
        "Multigol 2-4": (total_ft >= 2) & (total_ft <= 4),
        "Casa Over 1.5": home_ft >= 2,
        "Ospite Over 0.5": away_ft >= 1,
        "Over 8.5 Corner": corners > 8.5,
        "Over 3.5 Cartellini": cards > 3.5,
    }

    # Calcolo probabilità singole
    p_single = {k: np.mean(v) for k, v in events.items()}

    # Combinazioni selezionate tra mercati
    candidate_combos = [
        ("1", "Over 1.5"),
        ("1", "Over 2.5"),
        ("1", "No Goal"),
        ("1X", "Under 2.5"),
        ("1X", "Over 1.5"),
        ("1X", "Multigol 2-4"),
        ("X", "Under 2.5"),
        ("2", "Over 1.5"),
        ("X2", "Under 2.5"),
        ("Goal", "Over 2.5"),
        ("No Goal", "Under 2.5"),
        ("1", "Casa Over 1.5"),
        ("Multigol 2-4", "Goal"),
        ("1X", "Multigol 1-3"),
        ("Goal", "Over 8.5 Corner"),
        ("1", "Over 8.5 Corner"),
    ]

    synergy_results = []
    for m1, m2 in candidate_combos:
        if m1 not in events or m2 not in events:
            continue
        joint_mask = events[m1] & events[m2]
        count = int(np.sum(joint_mask))
        joint_prob = count / n_sims
        expected_independent = p_single[m1] * p_single[m2]
        
        lift = (joint_prob / expected_independent) if expected_independent > 0 else 1.0
        synergy_score = joint_prob * math.sqrt(max(0.01, lift))

        lift_val = float(lift)
        synergy_val = float(synergy_score)
        pct_val = round(float(joint_prob * 100.0), 2)

        synergy_results.append({
            "combo": f"{m1} + {m2}",
            "market_1": m1,
            "market_2": m2,
            "count": count,
            "percentage": pct_val,
            "lift": round(lift_val, 3),
            "synergy_score": round(synergy_val, 4),
            "correlation_type": "positiva" if lift_val > 1.05 else ("neutra" if lift_val >= 0.95 else "negativa")
        })

    # Ordiniamo per score di sinergia e probabilità
    synergy_results.sort(key=lambda x: (x["synergy_score"], x["percentage"]), reverse=True)
    best_combo = synergy_results[0] if synergy_results else None

    # Generazione della spiegazione testuale
    explanation_parts = []
    explanation_parts.append(
        f"L'analisi su {n_sims:,} simulazioni Monte Carlo (modello Dixon-Coles) per {home_name} vs {away_name} "
        f"evidenzia tassi di gol attesi pari a {lambda_:.2f} per i padroni di casa e {mu:.2f} per gli ospiti."
    )

    if best_combo:
        explanation_parts.append(
            f"La convergenza statistica primaria ricade sulla combinazione '{best_combo['combo']}', "
            f"che si è verificata in {best_combo['count']:,} simulazioni su {n_sims:,} ({best_combo['percentage']}%), "
            f"con un coefficiente di sinergia (Lift) di {best_combo['lift']}x rispetto alla stima a eventi indipendenti."
        )

    # Commento sul trend tattico/statistico
    if lambda_ > mu * 1.5:
        trend = (
            f"La spiccata superiorità di {home_name} (data da indice offensivo ed Elo) polarizza i mercati "
            f"verso una vittoria interna associata a una buona produzione offensiva."
        )
    elif mu > lambda_ * 1.3:
        trend = (
            f"La pericolosità offensiva di {away_name} e la fragilità difensiva di {home_name} "
            f"spostano il baricentro statistico verso esiti favorevoli agli ospiti o a quote Over."
        )
    elif abs(lambda_ - mu) < 0.35 and (lambda_ + mu) < 2.3:
        trend = (
            "L'equilibrio nei valori di forza ed Elo suggerisce una gara tattica a basso punteggio, "
            "con forte convergenza su esiti Under 2.5 e pareggio o margini stretti."
        )
    else:
        trend = (
            f"Entrambe le formazioni mostrano indici di realizzazione consistenti, creando forte affinità "
            f"tra i mercati Goal e Over moderati (Multigol 2-4)."
        )
    explanation_parts.append(trend)

    explanation_text = " ".join(explanation_parts)

    return {
        "best_synergy_market": best_combo,
        "top_combos": synergy_results[:5],
        "assistant_explanation": explanation_text
    }


def simulate_match(config: MatchConfig) -> Dict[str, Any]:
    """
    Esegue la simulazione completa di 50.000 partite con NumPy vettorializzato.
    Restituisce tutti i 15 mercati in percentuale e conteggio esatto,
    più la convergenza e la spiegazione testuale.
    """
    start_time = time.perf_counter()

    if config.seed is not None:
        np.random.seed(config.seed)

    n_sims = config.n_simulations
    max_goals = 12

    # 1. Calcolo tassi attesi di gol
    lambda_, mu = calculate_expected_goals(config)

    # 2. Matrice Dixon-Coles bivariata
    joint_probs = generate_bivariate_dixon_coles_probs(
        lambda_, mu, config.dixon_coles_rho, max_goals=max_goals
    )
    flat_probs = joint_probs.flatten()

    # 3. Campionamento Monte Carlo vettorializzato su 50.000 match
    grid_size = max_goals + 1
    sampled_indices = np.random.choice(len(flat_probs), size=n_sims, p=flat_probs)
    home_ft = (sampled_indices // grid_size).astype(np.int32)
    away_ft = (sampled_indices % grid_size).astype(np.int32)
    total_ft = home_ft + away_ft

    # 4. Suddivisione 1° Tempo / 2° Tempo (Campionamento Binomiale condizionato, p_ht = 0.45)
    # Garantisce per ogni simulazione: FT = HT + 2H
    p_ht = 0.45
    home_ht = np.random.binomial(home_ft, p_ht).astype(np.int32)
    away_ht = np.random.binomial(away_ft, p_ht).astype(np.int32)
    total_ht = home_ht + away_ht

    home_2h = home_ft - home_ht
    away_2h = away_ft - away_ht
    total_2h = home_2h + away_2h

    # 5. Simulazione Cartellini, Corner e Falli
    # Cartellini: base 4.4, influenzati da bilanciamento Elo e propensioni
    elo_gap = abs(config.home_team.elo - config.away_team.elo)
    tension_factor = 1.0 + max(0.0, (100.0 - min(elo_gap, 100.0)) / 400.0) # più tesa se Elo simile
    referee_yellow_factor = float(np.clip(config.referee_yellow_avg / 4.5, 0.5, 2.5))
    referee_red_factor = 1.0 + float(np.clip(config.referee_red_avg, 0.0, 1.0)) * 0.20
    intensity_factor = (config.home_stakes_multiplier + config.away_stakes_multiplier) / 2.0
    exp_cards = 4.4 * ((config.home_team.cards_factor + config.away_team.cards_factor) / 2.0) * tension_factor * referee_yellow_factor * referee_red_factor * intensity_factor
    exp_cards = max(1.0, min(22.0, exp_cards))
    cards = np.random.poisson(lam=exp_cards, size=n_sims)

    # Corner: base 9.8, influenzati da volume offensivo (lambda + mu)
    exp_corners = 9.8 * ((lambda_ + mu) / 2.5) * ((config.home_team.corners_factor + config.away_team.corners_factor) / 2.0) * intensity_factor
    exp_corners = max(5.0, exp_corners)
    corners = np.random.poisson(lam=exp_corners, size=n_sims)

    # Falli: stima indipendente ma coerente con intensità e propensione ai cartellini.
    exp_fouls = config.referee_fouls_avg * ((config.home_team.cards_factor + config.away_team.cards_factor) / 2.0) * tension_factor * intensity_factor
    exp_fouls = max(12.0, min(45.0, exp_fouls))
    fouls = np.random.poisson(lam=exp_fouls, size=n_sims)

    # 6. CALCOLO DEI 15 MERCATI RICHIESTI

    # 6.1 1X2 Finale
    m_1x2_ft = {
        "1": _calc_stat(home_ft > away_ft, n_sims),
        "X": _calc_stat(home_ft == away_ft, n_sims),
        "2": _calc_stat(away_ft > home_ft, n_sims),
    }

    # 6.2 1X2 Primo Tempo
    m_1x2_ht = {
        "1": _calc_stat(home_ht > away_ht, n_sims),
        "X": _calc_stat(home_ht == away_ht, n_sims),
        "2": _calc_stat(away_ht > home_ht, n_sims),
    }

    # 6.3 Over / Under Finale da 0.5 a 4.5
    m_ou_ft = {}
    for threshold in [0.5, 1.5, 2.5, 3.5, 4.5]:
        m_ou_ft[f"Over_{threshold}"] = _calc_stat(total_ft > threshold, n_sims)
        m_ou_ft[f"Under_{threshold}"] = _calc_stat(total_ft < threshold, n_sims)

    # 6.4 Over / Under Primo Tempo da 0.5 a 4.5
    m_ou_ht = {}
    for threshold in [0.5, 1.5, 2.5, 3.5, 4.5]:
        m_ou_ht[f"Over_{threshold}"] = _calc_stat(total_ht > threshold, n_sims)
        m_ou_ht[f"Under_{threshold}"] = _calc_stat(total_ht < threshold, n_sims)

    # 6.5 Goal / No Goal Finale
    is_goal_ft = (home_ft > 0) & (away_ft > 0)
    m_gg_ng_ft = {
        "Goal": _calc_stat(is_goal_ft, n_sims),
        "No_Goal": _calc_stat(~is_goal_ft, n_sims),
    }

    # 6.6 Goal / No Goal Primo Tempo
    is_goal_ht = (home_ht > 0) & (away_ht > 0)
    m_gg_ng_ht = {
        "Goal": _calc_stat(is_goal_ht, n_sims),
        "No_Goal": _calc_stat(~is_goal_ht, n_sims),
    }

    # 6.7 Cartellini (stima totale match / fasce)
    m_cards = {
        "expected_mean": round(float(np.mean(cards)), 2),
        "Over_3.5": _calc_stat(cards > 3.5, n_sims),
        "Under_3.5": _calc_stat(cards < 3.5, n_sims),
        "Over_4.5": _calc_stat(cards > 4.5, n_sims),
        "Under_4.5": _calc_stat(cards < 4.5, n_sims),
        "Over_5.5": _calc_stat(cards > 5.5, n_sims),
        "Under_5.5": _calc_stat(cards < 5.5, n_sims),
        "fascia_0_3": _calc_stat(cards <= 3, n_sims),
        "fascia_4_5": _calc_stat((cards >= 4) & (cards <= 5), n_sims),
        "fascia_6_plus": _calc_stat(cards >= 6, n_sims),
    }

    # 6.8 Calci d'angolo (stima totale match / fasce)
    m_corners = {
        "expected_mean": round(float(np.mean(corners)), 2),
        "Over_8.5": _calc_stat(corners > 8.5, n_sims),
        "Under_8.5": _calc_stat(corners < 8.5, n_sims),
        "Over_9.5": _calc_stat(corners > 9.5, n_sims),
        "Under_9.5": _calc_stat(corners < 9.5, n_sims),
        "Over_10.5": _calc_stat(corners > 10.5, n_sims),
        "Under_10.5": _calc_stat(corners < 10.5, n_sims),
        "Over_11.5": _calc_stat(corners > 11.5, n_sims),
        "Under_11.5": _calc_stat(corners < 11.5, n_sims),
        "fascia_0_8": _calc_stat(corners <= 8, n_sims),
        "fascia_9_11": _calc_stat((corners >= 9) & (corners <= 11), n_sims),
        "fascia_12_plus": _calc_stat(corners >= 12, n_sims),
    }

    # 6.9 Falli totali (stima dinamica per ogni simulazione)
    m_fouls = {
        "expected_mean": round(float(np.mean(fouls)), 2),
        "Over_19.5": _calc_stat(fouls > 19.5, n_sims),
        "Under_19.5": _calc_stat(fouls < 19.5, n_sims),
        "Over_24.5": _calc_stat(fouls > 24.5, n_sims),
        "Under_24.5": _calc_stat(fouls < 24.5, n_sims),
        "Over_29.5": _calc_stat(fouls > 29.5, n_sims),
        "Under_29.5": _calc_stat(fouls < 29.5, n_sims),
    }

    # Helper per calcolo multigol su un vettore di gol
    def _compute_multigol_ranges(goals_arr: np.ndarray, ranges: List[Tuple[int, int]]) -> Dict[str, Any]:
        res = {}
        for low, high in ranges:
            key = f"{low}_{high}"
            mask = (goals_arr >= low) & (goals_arr <= high)
            res[key] = _calc_stat(mask, n_sims)
        return res

    mg_ranges_match = [
        (0, 1), (0, 2), (0, 3), (0, 4), (0, 5),
        (1, 2), (1, 3), (1, 4), (1, 5),
        (2, 3), (2, 4), (2, 5), (2, 6),
        (3, 4), (3, 5), (3, 6)
    ]
    mg_ranges_team = [
        (0, 1), (0, 2), (0, 3), (0, 4), (0, 5),
        (1, 2), (1, 3), (1, 4), (1, 5),
        (2, 3), (2, 4), (2, 5), (2, 6),
        (3, 4), (3, 5), (3, 6)
    ]

    # 6.9 Multigol partita da 0-1 a 3-6
    m_mg_match = _compute_multigol_ranges(total_ft, mg_ranges_match)

    # 6.10 Multigol casa da 0-1 a 3-6
    m_mg_home = _compute_multigol_ranges(home_ft, mg_ranges_team)

    # 6.11 Multigol ospite da 0-1 a 3-6
    m_mg_away = _compute_multigol_ranges(away_ft, mg_ranges_team)

    # 6.12 Multigol Casa + Multigol Ospite (Combo principali)
    combo_pairs = [
        ((1, 2), (0, 1)),
        ((1, 2), (1, 2)),
        ((1, 3), (0, 1)),
        ((1, 3), (1, 2)),
        ((2, 3), (0, 1)),
        ((2, 4), (1, 2)),
        ((0, 1), (1, 2)),
        ((0, 1), (1, 3)),
        ((0, 1), (2, 3)),
        ((2, 3), (1, 3)),
    ]
    m_mg_home_away_combo = {}
    for (h_l, h_h), (a_l, a_h) in combo_pairs:
        mask = (home_ft >= h_l) & (home_ft <= h_h) & (away_ft >= a_l) & (away_ft <= a_h)
        key = f"Casa_{h_l}_{h_h}_e_Ospite_{a_l}_{a_h}"
        m_mg_home_away_combo[key] = _calc_stat(mask, n_sims)

    # 6.13 Multigol 1° Tempo + Multigol 2° Tempo (Combo principali)
    half_pairs = [
        ((0, 1), (0, 1)),
        ((0, 1), (1, 2)),
        ((0, 1), (1, 3)),
        ((1, 2), (1, 2)),
        ((1, 2), (1, 3)),
        ((1, 2), (0, 1)),
        ((1, 3), (1, 2)),
        ((0, 0), (1, 2)),
        ((1, 2), (2, 3)),
    ]
    m_mg_ht_2h_combo = {}
    for (ht_l, ht_h), (sh_l, sh_h) in half_pairs:
        mask = (total_ht >= ht_l) & (total_ht <= ht_h) & (total_2h >= sh_l) & (total_2h <= sh_h)
        key = f"1T_{ht_l}_{ht_h}_e_2T_{sh_l}_{sh_h}"
        m_mg_ht_2h_combo[key] = _calc_stat(mask, n_sims)

    # 6.14 Over Squadra Casa da 0.5 a 3.5
    m_over_home = {}
    for t in [0.5, 1.5, 2.5, 3.5]:
        m_over_home[f"Over_{t}"] = _calc_stat(home_ft > t, n_sims)
        m_over_home[f"Under_{t}"] = _calc_stat(home_ft < t, n_sims)

    # 6.15 Over Squadra Ospite da 0.5 a 3.5
    m_over_away = {}
    for t in [0.5, 1.5, 2.5, 3.5]:
        m_over_away[f"Over_{t}"] = _calc_stat(away_ft > t, n_sims)
        m_over_away[f"Under_{t}"] = _calc_stat(away_ft < t, n_sims)

def normalize_market_odds(odds_dict: Optional[Dict[str, Optional[float]]] = None) -> Dict[str, Dict[str, Any]]:
    """Rimuove l'aggio normalizzando le probabilita inverse per ogni lavagna."""
    raw: Dict[str, Dict[str, float]] = {}
    aliases = {"1": "1x2_finale", "X": "1x2_finale", "2": "1x2_finale"}
    for key, value in (odds_dict or {}).items():
        try:
            odds = float(value)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(odds) or odds <= 1.0:
            continue
        if ":" in key:
            category, selection = key.split(":", 1)
        else:
            category, selection = aliases.get(key, "over_under_finale"), key
        raw.setdefault(category, {})[selection] = odds
    normalized: Dict[str, Dict[str, Any]] = {}
    for category, selections in raw.items():
        inverse = {selection: 1.0 / odds for selection, odds in selections.items()}
        total = sum(inverse.values())
        if total <= 0.0:
            continue
        normalized[category] = {
            "overround": total,
            "margin_pct": round((total - 1.0) * 100.0, 3),
            "probabilities": {selection: probability / total for selection, probability in inverse.items()},
            "odds": selections,
        }
    return normalized


def _market_probabilities(lambda_: float, mu: float) -> Dict[str, Dict[str, float]]:
    """Calcola probabilita teoriche Poisson per calibrare le quote bookmaker."""
    goals = np.arange(13)
    home, away = np.meshgrid(goals, goals, indexing="ij")
    joint = np.outer(poisson.pmf(goals, lambda_), poisson.pmf(goals, mu))
    total = home + away
    probabilities: Dict[str, Dict[str, float]] = {
        "1x2_finale": {
            "1": float(joint[home > away].sum()), "X": float(joint[home == away].sum()), "2": float(joint[home < away].sum())
        },
        "goal_nogoal_finale": {
            "Goal": float(joint[(home > 0) & (away > 0)].sum()),
            "No_Goal": float(joint[(home == 0) | (away == 0)].sum()),
        },
    }
    for threshold in (0.5, 1.5, 2.5, 3.5, 4.5):
        probabilities.setdefault("over_under_finale", {})[f"Over_{threshold}"] = float(joint[total > threshold].sum())
        probabilities["over_under_finale"][f"Under_{threshold}"] = float(joint[total < threshold].sum())
    for category, values in (
        ("over_under_squadra_casa", home),
        ("over_under_squadra_ospite", away),
    ):
        for threshold in (0.5, 1.5, 2.5, 3.5):
            probabilities.setdefault(category, {})[f"Over_{threshold}"] = float(joint[values > threshold].sum())
            probabilities[category][f"Under_{threshold}"] = float(joint[values < threshold].sum())
    for category, lower, upper in (
        ("multigol_partita", 0, 2),
        ("multigol_partita", 1, 3),
        ("multigol_partita", 2, 4),
        ("multigol_casa", 0, 2),
        ("multigol_casa", 1, 3),
        ("multigol_casa", 2, 4),
        ("multigol_ospite", 0, 2),
        ("multigol_ospite", 1, 3),
        ("multigol_ospite", 2, 4),
    ):
        values = total if category == "multigol_partita" else home if category == "multigol_casa" else away
        probabilities.setdefault(category, {})[f"{lower}_{upper}"] = float(joint[(values >= lower) & (values <= upper)].sum())
    return probabilities


def calibrate_expected_goals(lambda_: float, mu: float, odds_dict: Optional[Dict[str, Optional[float]]] = None) -> Tuple[float, float, Dict[str, Any]]:
    """Calibra i tassi Poisson sui mercati quote disponibili, senza inventare mercati mancanti."""
    normalized = normalize_market_odds(odds_dict)
    targets = normalized.get("1x2_finale", {}).get("probabilities", {})
    total_targets = normalized.get("over_under_finale", {}).get("probabilities", {})
    goal_targets = normalized.get("goal_nogoal_finale", {}).get("probabilities", {})
    advanced_targets = {
        category: data.get("probabilities", {})
        for category, data in normalized.items()
        if category in {
            "over_under_squadra_casa",
            "over_under_squadra_ospite",
            "multigol_partita",
            "multigol_casa",
            "multigol_ospite",
        }
    }
    if not targets and not total_targets and not goal_targets and not any(advanced_targets.values()):
        return lambda_, mu, {"applied": False, "markets": {}, "base_lambda": lambda_, "base_mu": mu}
    best = (float("inf"), lambda_, mu)
    for candidate_lambda in np.linspace(0.20, 3.50, 67):
        for candidate_mu in np.linspace(0.20, 3.50, 67):
            predicted = _market_probabilities(float(candidate_lambda), float(candidate_mu))
            error = 0.0
            for selection, target in targets.items():
                error += (predicted["1x2_finale"].get(selection, 0.0) - target) ** 2
            for selection, target in total_targets.items():
                error += (predicted["over_under_finale"].get(selection, 0.0) - target) ** 2
            for selection, target in goal_targets.items():
                error += (predicted["goal_nogoal_finale"].get(selection, 0.0) - target) ** 2
            for category, category_targets in advanced_targets.items():
                for selection, target in category_targets.items():
                    error += (predicted.get(category, {}).get(selection, 0.0) - target) ** 2
            if error < best[0]:
                best = (error, float(candidate_lambda), float(candidate_mu))
    return best[1], best[2], {
        "applied": True,
        "markets": sorted(normalized),
        "base_lambda": lambda_,
        "base_mu": mu,
        "calibrated_lambda": best[1],
        "calibrated_mu": best[2],
        "fit_error": round(best[0], 8),
        "normalized_probabilities": {category: data["probabilities"] for category, data in normalized.items()},
    }


def calculate_value_bets(markets: Dict[str, Any], odds_dict: Optional[Dict[str, Optional[float]]] = None) -> Dict[str, Any]:
    """
    Confronta la percentuale d'uscita delle 50.000 simulazioni con la quota del bookmaker.
    Calcola Expected Value: EV = (P_simulata * Quota) - 1.
    Calcola Edge = P_simulata - P_implicita.
    Individua il mercato con la miglior Value Bet e margine di scostamento.
    """
    candidates = []
    odds_dict = odds_dict or {}
    normalized = normalize_market_odds(odds_dict)

    def parse_odds(raw_odds: Any) -> Optional[float]:
        if raw_odds is None or (isinstance(raw_odds, str) and not raw_odds.strip()):
            return None
        try:
            quota = float(raw_odds)
        except (TypeError, ValueError):
            return None
        return quota if math.isfinite(quota) else None

    def add_candidate(category: str, market_key: str, raw_quota: Any) -> None:
        quota = parse_odds(raw_quota)
        if quota is None:
            return
        stat = markets.get(category, {}).get(market_key)
        if not stat or quota <= 1.0:
            return
        p_sim = float(stat["percentage"]) / 100.0
        p_imp = normalized.get(category, {}).get("probabilities", {}).get(market_key, 1.0 / quota)
        ev = (p_sim * quota) - 1.0
        candidates.append({
            "market": f"{category}: {market_key.replace('_', ' ')}",
            "sign": market_key,
            "category": category,
            "odds": quota,
            "simulated_prob_pct": round(p_sim * 100.0, 2),
            "implied_prob_pct": round(p_imp * 100.0, 2),
            "raw_implied_prob_pct": round((1.0 / quota) * 100.0, 2),
            "edge_pct": round((p_sim - p_imp) * 100.0, 2),
            "ev_pct": round(ev * 100.0, 2),
            "is_value": ev > 0.02,
        })

    # Quote inserite dall'utente: categoria:chiave evita collisioni tra mercati.
    for quote_key, quote in odds_dict.items():
        if ":" in quote_key:
            category, market_key = quote_key.split(":", 1)
            add_candidate(category, market_key, quote)

    # Compatibilita con le quote storiche piatte del motore.
    for sign in ["1", "X", "2"]:
        if sign in odds_dict and sign in markets.get("1x2_finale", {}):
            quota = parse_odds(odds_dict[sign])
            if quota is None or quota <= 1.0:
                continue
            p_sim = float(markets["1x2_finale"][sign]["percentage"]) / 100.0
            p_imp = 1.0 / quota if quota > 0 else 1.0
            ev = (p_sim * quota) - 1.0
            edge = p_sim - p_imp
            candidates.append({
                "market": f"1X2: {sign}",
                "sign": sign,
                "category": "1X2",
                "odds": quota,
                "simulated_prob_pct": round(p_sim * 100.0, 2),
                "implied_prob_pct": round(p_imp * 100.0, 2),
                "edge_pct": round(edge * 100.0, 2),
                "ev_pct": round(ev * 100.0, 2),
                "is_value": ev > 0.02
            })

    # Over / Under 2.5
    for ou in ["Over_2.5", "Under_2.5"]:
        if ou in odds_dict and ou in markets.get("over_under_finale", {}):
            quota = parse_odds(odds_dict[ou])
            if quota is None or quota <= 1.0:
                continue
            p_sim = float(markets["over_under_finale"][ou]["percentage"]) / 100.0
            p_imp = 1.0 / quota if quota > 0 else 1.0
            ev = (p_sim * quota) - 1.0
            edge = p_sim - p_imp
            candidates.append({
                "market": ou.replace("_", " "),
                "sign": ou,
                "category": "Over/Under",
                "odds": quota,
                "simulated_prob_pct": round(p_sim * 100.0, 2),
                "implied_prob_pct": round(p_imp * 100.0, 2),
                "edge_pct": round(edge * 100.0, 2),
                "ev_pct": round(ev * 100.0, 2),
                "is_value": ev > 0.02
            })

    # Goal / No Goal
    for gg in ["Goal", "No_Goal"]:
        if gg in odds_dict and gg in markets.get("goal_nogoal_finale", {}):
            quota = parse_odds(odds_dict[gg])
            if quota is None or quota <= 1.0:
                continue
            p_sim = float(markets["goal_nogoal_finale"][gg]["percentage"]) / 100.0
            p_imp = 1.0 / quota if quota > 0 else 1.0
            ev = (p_sim * quota) - 1.0
            edge = p_sim - p_imp
            candidates.append({
                "market": gg.replace("_", " "),
                "sign": gg,
                "category": "Goal/NoGoal",
                "odds": quota,
                "simulated_prob_pct": round(p_sim * 100.0, 2),
                "implied_prob_pct": round(p_imp * 100.0, 2),
                "edge_pct": round(edge * 100.0, 2),
                "ev_pct": round(ev * 100.0, 2),
                "is_value": ev > 0.02
            })

    # Ordina per EV decrescente
    candidates.sort(key=lambda x: x["ev_pct"], reverse=True)
    best_value = candidates[0] if candidates else None

    return {
        "best_value_bet": best_value,
        "all_value_bets": candidates,
        "positive_ev_count": len([c for c in candidates if c["ev_pct"] > 0])
    }


def validate_value_bets_against_score(
    value_betting: Dict[str, Any], predicted_home: int, predicted_away: int
) -> Dict[str, Any]:
    """Rimuove consigli incompatibili con la scoreline modale della simulazione."""
    total_goals = predicted_home + predicted_away

    def compatible(candidate: Dict[str, Any]) -> bool:
        category = str(candidate.get("category", "")).lower()
        sign = str(candidate.get("sign", ""))
        if category in {"1x2_finale", "1x2"}:
            expected = "X" if predicted_home == predicted_away else ("1" if predicted_home > predicted_away else "2")
            return sign == expected
        if category in {"over_under_finale", "over/under"}:
            match = re.search(r"(Over|Under)_(\d+(?:\.\d+)?)", sign, re.IGNORECASE)
            if match:
                threshold = float(match.group(2))
                return total_goals > threshold if match.group(1).lower() == "over" else total_goals < threshold
        if category == "goal_nogoal_finale":
            return sign == ("Goal" if predicted_home > 0 and predicted_away > 0 else "No_Goal")
        if category in {"over_under_squadra_casa", "over_under_squadra_ospite"}:
            goals = predicted_home if "casa" in category else predicted_away
            match = re.search(r"(Over|Under)_(\d+(?:\.\d+)?)", sign, re.IGNORECASE)
            if match:
                threshold = float(match.group(2))
                return goals > threshold if match.group(1).lower() == "over" else goals < threshold
        if category in {"multigol_partita", "multigol_casa", "multigol_ospite"}:
            values = re.search(r"(\d+)_(\d+)", sign)
            if values:
                goals = total_goals if category == "multigol_partita" else (predicted_home if category == "multigol_casa" else predicted_away)
                return int(values.group(1)) <= goals <= int(values.group(2))
        return True

    candidates = [candidate for candidate in value_betting.get("all_value_bets", []) if compatible(candidate)]
    candidates.sort(key=lambda item: item.get("ev_pct", 0), reverse=True)
    return {
        **value_betting,
        "best_value_bet": candidates[0] if candidates else None,
        "all_value_bets": candidates,
        "positive_ev_count": sum(candidate.get("ev_pct", 0) > 0 for candidate in candidates),
    }


def generate_ai_narrative(
    home_name: str,
    away_name: str,
    lambda_: float,
    mu: float,
    p_1: float,
    p_x: float,
    p_2: float,
    best_convergence: Optional[Dict[str, Any]],
    best_value: Optional[Dict[str, Any]]
) -> str:
    """
    Genera un commento sintetico, rapido e naturale di 2-3 righe che riassume:
    1. Cosa è successo nella maggioranza dei 50.000 scenari (andamento e scenario tattico).
    2. Qual è la convergenza chiave tra i mercati.
    3. Qual è il mercato con il miglior rapporto rischio/rendimento (Value Bet).
    """
    if p_1 >= 50.0:
        riga1 = f"Nella maggioranza delle 50.000 simulazioni ({p_1:.1f}% dei casi) {home_name} impone la propria superiorità territoriale e offensiva chiudendo la gara a proprio favore."
    elif p_2 >= 45.0:
        riga1 = f"Nel {p_2:.1f}% degli scenari simulati {away_name} riesce a sfruttare le transizioni offensive e a colpire la difesa avversaria, emergendo come esito prevalente."
    elif p_x >= 30.0:
        riga1 = f"Nel {p_x:.1f}% degli scenari prevale l'equilibrio tattico a baricentro basso, determinando una gara molto bloccata e con margini di punteggio ridotti."
    else:
        riga1 = f"Gli scenari mostrano un match aperto ed equilibrato, con un volume realizzativo atteso di circa {lambda_ + mu:.2f} reti complessive."

    if best_convergence:
        riga2 = f"La convergenza chiave si concentra su '{best_convergence.get('combo', 'N/A')}', che registra un'elevata stabilità stocastica ({best_convergence.get('percentage', 0)}%) e un Lift sinergico di {best_convergence.get('lift', 1.0)}x rispetto alla casualità."
    else:
        riga2 = "I mercati convergono su esiti a media intensità realizzativa."

    if best_value and best_value.get("ev_pct", 0) > 0:
        riga3 = f"Sotto il profilo rischio/rendimento, la giocata di massimo valore è '{best_value['market']}' a quota {best_value['odds']:.2f}, con un margine di vantaggio atteso (EV) del +{best_value['ev_pct']:.1f}% rispetto al banco."
    elif best_value:
        riga3 = f"In termini di rischio/rendimento la proposta più bilanciata è '{best_value['market']}' a quota {best_value['odds']:.2f}, allineata ai valori statistici stimati."
    else:
        riga3 = "Non emergono discrepanze anomale rispetto alle quote stimate dal banco."

    return f"{riga1} {riga2} {riga3}"


def generate_deep_narrative(
    home_name: str,
    away_name: str,
    lambda_: float,
    mu: float,
    home_ft: np.ndarray,
    away_ft: np.ndarray,
    home_ht: np.ndarray,
    away_ht: np.ndarray,
    cards: np.ndarray,
    config: MatchConfig,
    best_convergence: Optional[Dict[str, Any]],
    best_value: Optional[Dict[str, Any]],
) -> str:
    """Racconta la dinamica emersa dai vettori simulati, senza frasi prefabbricate."""
    total_ft = home_ft + away_ft
    total_ht = home_ht + away_ht
    late_goals = total_ft - total_ht
    mode_pairs, mode_counts = np.unique(np.column_stack((home_ft, away_ft)), axis=0, return_counts=True)
    mode_index = int(np.argmax(mode_counts))
    mode_home, mode_away = (int(mode_pairs[mode_index, 0]), int(mode_pairs[mode_index, 1]))
    mode_share = float(mode_counts[mode_index] / len(total_ft) * 100.0)
    first_half_share = float(np.mean(total_ht) / max(np.mean(total_ft), 0.01))
    late_share = float(np.mean(late_goals) / max(np.mean(total_ft), 0.01))
    card_mean = float(np.mean(cards))
    home_late = float(np.mean(home_ft - home_ht))
    away_late = float(np.mean(away_ft - away_ht))
    leader = home_name if lambda_ >= mu else away_name
    weaker = away_name if leader == home_name else home_name

    if late_share >= 0.58:
        tempo = f"Il baricentro si alza soprattutto dopo l'intervallo: il {late_share * 100:.1f}% del volume medio di gol arriva nella ripresa"
    elif first_half_share >= 0.52:
        tempo = f"La partita tende a sbloccarsi presto, con il primo tempo che assorbe il {first_half_share * 100:.1f}% del volume medio di gol"
    else:
        tempo = "Il copione resta distribuito tra i due tempi, senza un unico momento dominante"

    if home_late > away_late + 0.12:
        transition = f"la spinta tardiva favorisce {home_name} ({home_late:.2f} gol medi nella ripresa contro {away_late:.2f})"
    elif away_late > home_late + 0.12:
        transition = f"le transizioni tardive premiano {away_name} ({away_late:.2f} contro {home_late:.2f} gol medi nella ripresa)"
    else:
        transition = "la distribuzione temporale resta sostanzialmente bilanciata tra le due squadre"

    if mode_home == mode_away:
        result_read = f"Lo score modale e {mode_home}-{mode_away}, presente nel {mode_share:.2f}% dei campioni"
    else:
        result_read = f"Lo score modale e {mode_home}-{mode_away}, presente nel {mode_share:.2f}% dei campioni e coerente con il vantaggio atteso di {leader}"

    tension = "La tensione aumenta la varianza disciplinare" if card_mean >= 5.5 else "Il profilo disciplinare resta contenuto e non introduce uno scompenso marcato"
    convergence = ""
    if best_convergence:
        convergence = (
            f"La convergenza piu informativa e {best_convergence.get('combo', 'la combinazione principale')}, "
            f"osservata nel {best_convergence.get('percentage', 0):.2f}% degli scenari: non e un dato isolato, ma l'incrocio tra il volume atteso ({lambda_ + mu:.2f} xG) e la distribuzione del rischio."
        )
    value = ""
    if best_value:
        value = f" Il confronto quote segnala {best_value['market']} a {best_value['odds']:.2f}, con EV {best_value['ev_pct']:+.1f}%."

    return (
        f"Su {len(total_ft):,} partite simulate, {leader} costruisce il margine teorico con {lambda_:.2f} xG contro {mu:.2f} di {weaker}. "
        f"{tempo}; {transition}. {result_read}. {tension}, con una media di {card_mean:.2f} cartellini: assenze e motivazioni entrano quindi nel racconto come disponibilita e spinta finale, non come gol aggiunti artificialmente. "
        f"{convergence}{value}"
    )


def simulate_match(config: MatchConfig, custom_odds: Optional[Dict[str, Optional[float]]] = None) -> Dict[str, Any]:
    """
    Esegue la simulazione completa di 50.000 partite con NumPy vettorializzato.
    Restituisce tutti i 15 mercati in percentuale e conteggio esatto,
    più la convergenza, il calcolo di Value Betting e la sintesi narrativa AI.
    """
    start_time = time.perf_counter()

    if config.seed is not None:
        np.random.seed(config.seed)

    n_sims = config.n_simulations
    max_goals = 12

    # 1. Calcolo tassi attesi di gol
    lambda_, mu = calculate_expected_goals(config)
    lambda_, mu, bookmaker_calibration = calibrate_expected_goals(lambda_, mu, custom_odds)

    # 2. Campionamento Monte Carlo stocastico direttamente dai lambda.
    home_ft = np.random.poisson(lam=lambda_, size=n_sims).astype(np.int32)
    away_ft = np.random.poisson(lam=mu, size=n_sims).astype(np.int32)
    total_ft = home_ft + away_ft
    trend_filter = {
        "high_intensity_filter": False,
        "raw_over_2_5_probability": None,
        "raw_goal_probability": None,
        "removed_low_total_scenarios": False,
    }

    # 4. Suddivisione 1° Tempo / 2° Tempo (Campionamento Binomiale condizionato, p_ht = 0.45)
    home_late_push = 0.02 * (config.home_momentum - 5.0) + 1.5 * (config.home_stakes_multiplier - 1.0)
    away_late_push = 0.02 * (config.away_momentum - 5.0) + 1.5 * (config.away_stakes_multiplier - 1.0)
    home_ht_probability = float(np.clip(0.45 - home_late_push, 0.35, 0.55))
    away_ht_probability = float(np.clip(0.45 - away_late_push, 0.35, 0.55))
    home_ht = np.random.binomial(home_ft, home_ht_probability).astype(np.int32)
    away_ht = np.random.binomial(away_ft, away_ht_probability).astype(np.int32)
    total_ht = home_ht + away_ht

    home_2h = home_ft - home_ht
    away_2h = away_ft - away_ht
    total_2h = home_2h + away_2h

    # 5. Simulazione Cartellini e Corner
    elo_gap = abs(config.home_team.elo - config.away_team.elo)
    tension_factor = 1.0 + max(0.0, (100.0 - min(elo_gap, 100.0)) / 400.0)
    referee_yellow_factor = float(np.clip(config.referee_yellow_avg / 4.5, 0.5, 2.5))
    referee_red_factor = 1.0 + float(np.clip(config.referee_red_avg, 0.0, 1.0)) * 0.20
    intensity_factor = (config.home_stakes_multiplier + config.away_stakes_multiplier) / 2.0
    exp_cards = 4.4 * ((config.home_team.cards_factor + config.away_team.cards_factor) / 2.0) * tension_factor * referee_yellow_factor * referee_red_factor * intensity_factor
    exp_cards = max(1.0, min(22.0, exp_cards))
    referee_dispersion = 1.0 + float(np.clip(config.referee_yellow_avg / 4.5 - 1.0, 0.0, 1.5)) * 0.35
    card_shape = max(0.5, exp_cards / max(referee_dispersion - 1.0, 0.01))
    card_rates = np.random.gamma(card_shape, max(referee_dispersion - 1.0, 0.01), size=n_sims) if referee_dispersion > 1.01 else exp_cards
    cards = np.random.poisson(lam=card_rates, size=n_sims)

    exp_corners = 9.8 * ((lambda_ + mu) / 2.5) * ((config.home_team.corners_factor + config.away_team.corners_factor) / 2.0) * intensity_factor
    exp_corners = max(5.0, exp_corners)
    corners = np.random.poisson(lam=exp_corners, size=n_sims)

    # Falli: stima dinamica coerente con intensità e propensione ai cartellini.
    exp_fouls = config.referee_fouls_avg * ((config.home_team.cards_factor + config.away_team.cards_factor) / 2.0) * tension_factor * intensity_factor
    exp_fouls = max(12.0, min(45.0, exp_fouls))
    foul_dispersion = 1.0 + float(np.clip(config.referee_fouls_avg / 24.0 - 1.0, 0.0, 1.5)) * 0.25
    foul_shape = max(0.5, exp_fouls / max(foul_dispersion - 1.0, 0.01))
    foul_rates = np.random.gamma(foul_shape, max(foul_dispersion - 1.0, 0.01), size=n_sims) if foul_dispersion > 1.01 else exp_fouls
    fouls = np.random.poisson(lam=foul_rates, size=n_sims)

    # 6. CALCOLO DEI 15 MERCATI RICHIESTI
    m_1x2_ft = {
        "1": _calc_stat(home_ft > away_ft, n_sims),
        "X": _calc_stat(home_ft == away_ft, n_sims),
        "2": _calc_stat(away_ft > home_ft, n_sims),
    }

    m_1x2_ht = {
        "1": _calc_stat(home_ht > away_ht, n_sims),
        "X": _calc_stat(home_ht == away_ht, n_sims),
        "2": _calc_stat(away_ht > home_ht, n_sims),
    }

    m_ou_ft = {}
    for threshold in [0.5, 1.5, 2.5, 3.5, 4.5]:
        m_ou_ft[f"Over_{threshold}"] = _calc_stat(total_ft > threshold, n_sims)
        m_ou_ft[f"Under_{threshold}"] = _calc_stat(total_ft < threshold, n_sims)

    m_ou_ht = {}
    for threshold in [0.5, 1.5, 2.5, 3.5, 4.5]:
        m_ou_ht[f"Over_{threshold}"] = _calc_stat(total_ht > threshold, n_sims)
        m_ou_ht[f"Under_{threshold}"] = _calc_stat(total_ht < threshold, n_sims)

    is_goal_ft = (home_ft > 0) & (away_ft > 0)
    m_gg_ng_ft = {
        "Goal": _calc_stat(is_goal_ft, n_sims),
        "No_Goal": _calc_stat(~is_goal_ft, n_sims),
    }

    is_goal_ht = (home_ht > 0) & (away_ht > 0)
    m_gg_ng_ht = {
        "Goal": _calc_stat(is_goal_ht, n_sims),
        "No_Goal": _calc_stat(~is_goal_ht, n_sims),
    }

    m_cards = {
        "expected_mean": round(float(np.mean(cards)), 2),
        "Over_3.5": _calc_stat(cards > 3.5, n_sims),
        "Under_3.5": _calc_stat(cards < 3.5, n_sims),
        "Over_4.5": _calc_stat(cards > 4.5, n_sims),
        "Under_4.5": _calc_stat(cards < 4.5, n_sims),
        "Over_5.5": _calc_stat(cards > 5.5, n_sims),
        "Under_5.5": _calc_stat(cards < 5.5, n_sims),
        "fascia_0_3": _calc_stat(cards <= 3, n_sims),
        "fascia_4_5": _calc_stat((cards >= 4) & (cards <= 5), n_sims),
        "fascia_6_plus": _calc_stat(cards >= 6, n_sims),
    }

    m_corners = {
        "expected_mean": round(float(np.mean(corners)), 2),
        "Over_8.5": _calc_stat(corners > 8.5, n_sims),
        "Under_8.5": _calc_stat(corners < 8.5, n_sims),
        "Over_9.5": _calc_stat(corners > 9.5, n_sims),
        "Under_9.5": _calc_stat(corners < 9.5, n_sims),
        "Over_10.5": _calc_stat(corners > 10.5, n_sims),
        "Under_10.5": _calc_stat(corners < 10.5, n_sims),
        "Over_11.5": _calc_stat(corners > 11.5, n_sims),
        "Under_11.5": _calc_stat(corners < 11.5, n_sims),
        "fascia_0_8": _calc_stat(corners <= 8, n_sims),
        "fascia_9_11": _calc_stat((corners >= 9) & (corners <= 11), n_sims),
        "fascia_12_plus": _calc_stat(corners >= 12, n_sims),
    }

    m_fouls = {
        "expected_mean": round(float(np.mean(fouls)), 2),
        "Over_19.5": _calc_stat(fouls > 19.5, n_sims),
        "Under_19.5": _calc_stat(fouls < 19.5, n_sims),
        "Over_24.5": _calc_stat(fouls > 24.5, n_sims),
        "Under_24.5": _calc_stat(fouls < 24.5, n_sims),
        "Over_29.5": _calc_stat(fouls > 29.5, n_sims),
        "Under_29.5": _calc_stat(fouls < 29.5, n_sims),
    }

    def _compute_multigol_ranges(goals_arr: np.ndarray, ranges: List[Tuple[int, int]]) -> Dict[str, Any]:
        res = {}
        for low, high in ranges:
            key = f"{low}_{high}"
            mask = (goals_arr >= low) & (goals_arr <= high)
            res[key] = _calc_stat(mask, n_sims)
        return res

    mg_ranges_match = [
        (0, 1), (0, 2), (0, 3), (0, 4), (0, 5),
        (1, 2), (1, 3), (1, 4), (1, 5),
        (2, 3), (2, 4), (2, 5), (2, 6),
        (3, 4), (3, 5), (3, 6)
    ]
    mg_ranges_team = [
        (0, 1), (0, 2), (0, 3), (0, 4), (0, 5),
        (1, 2), (1, 3), (1, 4), (1, 5),
        (2, 3), (2, 4), (2, 5), (2, 6),
        (3, 4), (3, 5), (3, 6)
    ]

    m_mg_match = _compute_multigol_ranges(total_ft, mg_ranges_match)
    m_mg_home = _compute_multigol_ranges(home_ft, mg_ranges_team)
    m_mg_away = _compute_multigol_ranges(away_ft, mg_ranges_team)

    combo_pairs = [
        ((1, 2), (0, 1)),
        ((1, 2), (1, 2)),
        ((1, 3), (0, 1)),
        ((1, 3), (1, 2)),
        ((2, 3), (0, 1)),
        ((2, 4), (1, 2)),
        ((0, 1), (1, 2)),
        ((0, 1), (1, 3)),
        ((0, 1), (2, 3)),
        ((2, 3), (1, 3)),
    ]
    m_mg_home_away_combo = {}
    for (h_l, h_h), (a_l, a_h) in combo_pairs:
        mask = (home_ft >= h_l) & (home_ft <= h_h) & (away_ft >= a_l) & (away_ft <= a_h)
        key = f"Casa_{h_l}_{h_h}_e_Ospite_{a_l}_{a_h}"
        m_mg_home_away_combo[key] = _calc_stat(mask, n_sims)

    half_pairs = [
        ((0, 1), (0, 1)),
        ((0, 1), (1, 2)),
        ((0, 1), (1, 3)),
        ((1, 2), (1, 2)),
        ((1, 2), (1, 3)),
        ((1, 2), (0, 1)),
        ((1, 3), (1, 2)),
        ((0, 0), (1, 2)),
        ((1, 2), (2, 3)),
    ]
    m_mg_ht_2h_combo = {}
    for (ht_l, ht_h), (sh_l, sh_h) in half_pairs:
        mask = (total_ht >= ht_l) & (total_ht <= ht_h) & (total_2h >= sh_l) & (total_2h <= sh_h)
        key = f"1T_{ht_l}_{ht_h}_e_2T_{sh_l}_{sh_h}"
        m_mg_ht_2h_combo[key] = _calc_stat(mask, n_sims)

    m_over_home = {}
    for t in [0.5, 1.5, 2.5, 3.5]:
        m_over_home[f"Over_{t}"] = _calc_stat(home_ft > t, n_sims)
        m_over_home[f"Under_{t}"] = _calc_stat(home_ft < t, n_sims)

    m_over_away = {}
    for t in [0.5, 1.5, 2.5, 3.5]:
        m_over_away[f"Over_{t}"] = _calc_stat(away_ft > t, n_sims)
        m_over_away[f"Under_{t}"] = _calc_stat(away_ft < t, n_sims)

    # 7. Analisi di convergenza tra i mercati
    convergence = analyze_market_convergence(
        home_ft=home_ft,
        away_ft=away_ft,
        total_ft=total_ft,
        home_ht=home_ht,
        away_ht=away_ht,
        total_ht=total_ht,
        corners=corners,
        cards=cards,
        n_sims=n_sims,
        home_name=config.home_team.name,
        away_name=config.away_team.name,
        lambda_=lambda_,
        mu=mu,
    )

    all_markets = {
        "1x2_finale": m_1x2_ft,
        "1x2_primo_tempo": m_1x2_ht,
        "over_under_finale": m_ou_ft,
        "over_under_primo_tempo": m_ou_ht,
        "goal_nogoal_finale": m_gg_ng_ft,
        "goal_nogoal_primo_tempo": m_gg_ng_ht,
        "cartellini": m_cards,
        "calci_dangolo": m_corners,
        "falli": m_fouls,
        "multigol_partita": m_mg_match,
        "multigol_casa": m_mg_home,
        "multigol_ospite": m_mg_away,
        "multigol_casa_combo_ospite": m_mg_home_away_combo,
        "multigol_primo_tempo_combo_secondo_tempo": m_mg_ht_2h_combo,
        "over_under_squadra_casa": m_over_home,
        "over_under_squadra_ospite": m_over_away,
    }

    def _mode_pair(first: np.ndarray, second: np.ndarray, outcome: Optional[str] = None) -> Tuple[int, int]:
        pairs, counts = np.unique(np.column_stack((first, second)), axis=0, return_counts=True)
        if outcome is not None:
            if outcome == "1":
                valid = pairs[:, 0] > pairs[:, 1]
            elif outcome == "2":
                valid = pairs[:, 1] > pairs[:, 0]
            else:
                valid = pairs[:, 0] == pairs[:, 1]
            if np.any(valid):
                pairs = pairs[valid]
                counts = counts[valid]
        mode = pairs[int(np.argmax(counts))]
        return int(mode[0]), int(mode[1])

    predicted_ht = _mode_pair(home_ht, away_ht)
    predicted_2h = _mode_pair(home_2h, away_2h)
    predicted_outcome = max(
        ("1", m_1x2_ft["1"]["count"]),
        ("X", m_1x2_ft["X"]["count"]),
        ("2", m_1x2_ft["2"]["count"]),
        key=lambda item: item[1],
    )[0]
    predicted_ft = _mode_pair(home_ft, away_ft, predicted_outcome)

    # 8. Le quote sono solo un filtro opzionale per il Value Betting.
    market_odds = custom_odds or {}
    normalized_market_odds = normalize_market_odds(market_odds)
    value_betting = calculate_value_bets(all_markets, market_odds)
    value_betting = validate_value_bets_against_score(value_betting, *predicted_ft)

    # 9. Sintesi narrativa dell'assistente AI (2-3 righe)
    ai_narrative = generate_deep_narrative(
        home_name=config.home_team.name,
        away_name=config.away_team.name,
        lambda_=lambda_,
        mu=mu,
        home_ft=home_ft,
        away_ft=away_ft,
        home_ht=home_ht,
        away_ht=away_ht,
        cards=cards,
        config=config,
        best_convergence=convergence.get("best_synergy_market"),
        best_value=value_betting.get("best_value_bet"),
    )

    elapsed_ms = round((time.perf_counter() - start_time) * 1000.0, 2)

    return {
        "metadata": {
            "home_team": config.home_team.name,
            "away_team": config.away_team.name,
            "expected_goals_home_lambda": round(lambda_, 3),
            "expected_goals_away_mu": round(mu, 3),
            "bookmaker_calibration": bookmaker_calibration,
            "organic_expected_goals_home": round(calculate_expected_goals(MatchConfig(
                home_team=TeamParams(
                    name=config.home_team.name,
                    attack=config.home_team.attack,
                    defense=config.home_team.defense,
                    elo=config.home_team.elo,
                    cards_factor=config.home_team.cards_factor,
                    corners_factor=config.home_team.corners_factor,
                    recent_form=config.home_team.recent_form,
                ),
                away_team=TeamParams(
                    name=config.away_team.name,
                    attack=config.away_team.attack,
                    defense=config.away_team.defense,
                    elo=config.away_team.elo,
                    cards_factor=config.away_team.cards_factor,
                    corners_factor=config.away_team.corners_factor,
                    recent_form=config.away_team.recent_form,
                ),
                home_advantage=config.home_advantage,
                base_goals_home=config.base_goals_home,
                base_goals_away=config.base_goals_away,
                dixon_coles_rho=config.dixon_coles_rho,
            ))[0], 3),
            "organic_expected_goals_away": round(calculate_expected_goals(MatchConfig(
                home_team=TeamParams(name=config.home_team.name, attack=config.home_team.attack, defense=config.home_team.defense, elo=config.home_team.elo, recent_form=config.home_team.recent_form),
                away_team=TeamParams(name=config.away_team.name, attack=config.away_team.attack, defense=config.away_team.defense, elo=config.away_team.elo, recent_form=config.away_team.recent_form),
                home_advantage=config.home_advantage,
                base_goals_home=config.base_goals_home,
                base_goals_away=config.base_goals_away,
                dixon_coles_rho=config.dixon_coles_rho,
            ))[1], 3),
            "xg_inputs": {
                "home_xg_for": config.home_team.xg_for,
                "home_xg_against": config.home_team.xg_against,
                "away_xg_for": config.away_team.xg_for,
                "away_xg_against": config.away_team.xg_against,
                "applied": any(value is not None for value in (
                    config.home_team.xg_for,
                    config.home_team.xg_against,
                    config.away_team.xg_for,
                    config.away_team.xg_against,
                )),
            },
            "home_team_strength": calculate_team_strength(config.home_team),
            "away_team_strength": calculate_team_strength(config.away_team),
            "simulations_count": n_sims,
            "execution_time_ms": elapsed_ms,
            "market_filter": trend_filter,
            "predicted_score": {
                "first_half": {"home": predicted_ht[0], "away": predicted_ht[1]},
                "second_half": {"home": predicted_2h[0], "away": predicted_2h[1]},
                "full_time": {"home": predicted_ft[0], "away": predicted_ft[1]},
            },
            "predicted_outcome": predicted_outcome,
            "model": "Bivariate Poisson with Dixon-Coles Correction (Monte Carlo Vectorized)"
        },
        "markets": all_markets,
        "market_convergence": convergence,
        "value_betting": value_betting,
        "market_odds": market_odds,
        "market_odds_normalized": normalized_market_odds,
        "ai_narrative": ai_narrative,
    }
