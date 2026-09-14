"""
Modulo updater.py - Logica di aggiornamento dinamico post-match:
- Ricalcolo automatico Standings (punti, vinte, pareggiate, perse, gf, gs, dr)
- Aggiornamento della forma recente (ultime 5 partite W-D-L)
- Ricalcolo dinamico rating Elo con moltiplicatore margine gol
- Aggiornamento medie xG prodotti e concessi e indici attacco/difesa
"""

from pathlib import Path
import sqlite3
from typing import Any, Dict, Optional
from database import get_db_connection


def recalculate_league_standings(league_id: int, db_path: Optional[str | Path] = None) -> None:
    """
    Ricalcola integralmente la classifica per una determinata lega a partire da tutti i match conclusi.
    Garantisce consistenza totale.
    """
    conn = get_db_connection(db_path)
    with conn:
        cur = conn.cursor()
        # Azzeriamo le statistiche correnti per la lega
        cur.execute("""
            UPDATE standings
            SET played = 0, won = 0, drawn = 0, lost = 0,
                goals_for = 0, goals_against = 0, goal_diff = 0, points = 0
            WHERE league_id = ?
        """, (league_id,))

        # Selezioniamo tutti i match conclusi per la lega
        cur.execute("""
            SELECT home_team_id, away_team_id, home_goals, away_goals
            FROM matches
            WHERE league_id = ? AND status = 'completed'
        """, (league_id,))
        matches = cur.fetchall()

        stats: Dict[int, Dict[str, int]] = {}
        # Recuperiamo tutte le squadre della lega
        cur.execute("SELECT id FROM teams WHERE league_id = ?", (league_id,))
        for row in cur.fetchall():
            stats[row["id"]] = {
                "played": 0, "won": 0, "drawn": 0, "lost": 0,
                "goals_for": 0, "goals_against": 0, "points": 0
            }

        for m in matches:
            h_id = m["home_team_id"]
            a_id = m["away_team_id"]
            hg = m["home_goals"]
            ag = m["away_goals"]

            if h_id not in stats:
                stats[h_id] = {"played": 0, "won": 0, "drawn": 0, "lost": 0, "goals_for": 0, "goals_against": 0, "points": 0}
            if a_id not in stats:
                stats[a_id] = {"played": 0, "won": 0, "drawn": 0, "lost": 0, "goals_for": 0, "goals_against": 0, "points": 0}

            stats[h_id]["played"] += 1
            stats[a_id]["played"] += 1
            stats[h_id]["goals_for"] += hg
            stats[h_id]["goals_against"] += ag
            stats[a_id]["goals_for"] += ag
            stats[a_id]["goals_against"] += hg

            if hg > ag:
                stats[h_id]["won"] += 1
                stats[h_id]["points"] += 3
                stats[a_id]["lost"] += 1
            elif hg == ag:
                stats[h_id]["drawn"] += 1
                stats[h_id]["points"] += 1
                stats[a_id]["drawn"] += 1
                stats[a_id]["points"] += 1
            else:
                stats[a_id]["won"] += 1
                stats[a_id]["points"] += 3
                stats[h_id]["lost"] += 1

        for team_id, st in stats.items():
            gd = st["goals_for"] - st["goals_against"]
            cur.execute("""
                INSERT INTO standings (league_id, team_id, played, won, drawn, lost, goals_for, goals_against, goal_diff, points)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(team_id) DO UPDATE SET
                    played = excluded.played,
                    won = excluded.won,
                    drawn = excluded.drawn,
                    lost = excluded.lost,
                    goals_for = excluded.goals_for,
                    goals_against = excluded.goals_against,
                    goal_diff = excluded.goal_diff,
                    points = excluded.points
            """, (league_id, team_id, st["played"], st["won"], st["drawn"], st["lost"], st["goals_for"], st["goals_against"], gd, st["points"]))

    conn.close()


def update_team_form(old_form: str, new_result: str) -> str:
    """Aggiorna la stringa della forma recente mantenendo le ultime 5 partite (es. W-D-L-W-W)."""
    parts = [p.strip() for p in old_form.split("-") if p.strip()]
    parts.append(new_result)
    last_5 = parts[-5:]
    return "-".join(last_5)


def calculate_elo_delta(home_elo: float, away_elo: float, home_goals: int, away_goals: int, k_factor: float = 32.0) -> tuple[float, float]:
    """
    Calcola la variazione Elo per casa e ospite secondo lo standard World Football Elo Ratings.
    Include moltiplicatore per margine gol.
    """
    # Probabilità attesa
    e_home = 1.0 / (1.0 + 10.0 ** ((away_elo - home_elo) / 400.0))
    e_away = 1.0 - e_home

    # Risultato effettivo
    if home_goals > away_goals:
        s_home = 1.0
        s_away = 0.0
    elif home_goals == away_goals:
        s_home = 0.5
        s_away = 0.5
    else:
        s_home = 0.0
        s_away = 1.0

    # Moltiplicatore margine gol
    goal_diff = abs(home_goals - away_goals)
    if goal_diff <= 1:
        g_mult = 1.0
    elif goal_diff == 2:
        g_mult = 1.5
    else:
        g_mult = (11.0 + goal_diff) / 8.0

    delta_home = k_factor * g_mult * (s_home - e_home)
    delta_away = k_factor * g_mult * (s_away - e_away)

    return round(delta_home, 1), round(delta_away, 1)


def complete_match(
    match_id: int,
    home_goals: int,
    away_goals: int,
    home_xg: Optional[float] = None,
    away_xg: Optional[float] = None,
    db_path: Optional[str | Path] = None
) -> Dict[str, Any]:
    """
    Segna un match come concluso, registrando gol e xG.
    Aggiorna automaticamente:
    - Tabella Matches
    - Tabella Standings (classifica)
    - Forma recente delle squadre (W-D-L)
    - Rating Elo dinamico
    - Medie xG e indici attacco/difesa
    """
    conn = get_db_connection(db_path)
    with conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM matches WHERE id = ?", (match_id,))
        match_row = cur.fetchone()
        if not match_row:
            raise ValueError(f"Match con ID {match_id} non trovato.")

        league_id = match_row["league_id"]
        home_team_id = match_row["home_team_id"]
        away_team_id = match_row["away_team_id"]

        # Se xG non forniti, stimiamo un valore realistico
        if home_xg is None:
            home_xg = round(max(0.2, home_goals * 0.75 + 0.35), 2)
        if away_xg is None:
            away_xg = round(max(0.2, away_goals * 0.75 + 0.25), 2)

        # 1. Aggiornamento Match
        cur.execute("""
            UPDATE matches
            SET status = 'completed',
                home_goals = ?,
                away_goals = ?,
                home_xg = ?,
                away_xg = ?
            WHERE id = ?
        """, (home_goals, away_goals, home_xg, away_xg, match_id))

        # Recuperiamo le due squadre
        cur.execute("SELECT * FROM teams WHERE id = ?", (home_team_id,))
        home_team = cur.fetchone()
        cur.execute("SELECT * FROM teams WHERE id = ?", (away_team_id,))
        away_team = cur.fetchone()

        if not home_team or not away_team:
            raise ValueError("Squadre associate al match non trovate.")

        # 2. Esito per la forma recente
        if home_goals > away_goals:
            home_outcome = "W"
            away_outcome = "L"
        elif home_goals == away_goals:
            home_outcome = "D"
            away_outcome = "D"
        else:
            home_outcome = "L"
            away_outcome = "W"

        new_home_form = update_team_form(home_team["recent_form"], home_outcome)
        new_away_form = update_team_form(away_team["recent_form"], away_outcome)

        # 3. Aggiornamento Elo dinamico
        d_home_elo, d_away_elo = calculate_elo_delta(
            home_team["elo"], away_team["elo"], home_goals, away_goals
        )
        new_home_elo = round(home_team["elo"] + d_home_elo, 1)
        new_away_elo = round(away_team["elo"] + d_away_elo, 1)

        # 4. Aggiornamento medie xG e metriche
        h_played = home_team["matches_played_stats"]
        new_h_played = h_played + 1
        new_h_xg_for = round((home_team["xg_for"] * h_played + home_xg) / new_h_played, 2)
        new_h_xg_against = round((home_team["xg_against"] * h_played + away_xg) / new_h_played, 2)

        a_played = away_team["matches_played_stats"]
        new_a_played = a_played + 1
        new_a_xg_for = round((away_team["xg_for"] * a_played + away_xg) / new_a_played, 2)
        new_a_xg_against = round((away_team["xg_against"] * a_played + home_xg) / new_a_played, 2)

        # Calibrazione adattiva degli indici attacco/difesa
        new_h_attack = round(max(0.4, min(2.5, home_team["attack"] * 0.96 + (home_xg / 1.35) * 0.04)), 3)
        new_h_defense = round(max(0.4, min(2.5, home_team["defense"] * 0.96 + (away_xg / 1.20) * 0.04)), 3)
        new_a_attack = round(max(0.4, min(2.5, away_team["attack"] * 0.96 + (away_xg / 1.35) * 0.04)), 3)
        new_a_defense = round(max(0.4, min(2.5, away_team["defense"] * 0.96 + (home_xg / 1.20) * 0.04)), 3)

        # Salvataggio aggiornamenti home team
        cur.execute("""
            UPDATE teams
            SET elo = ?,
                recent_form = ?,
                xg_for = ?,
                xg_against = ?,
                matches_played_stats = ?,
                attack = ?,
                defense = ?
            WHERE id = ?
        """, (new_home_elo, new_home_form, new_h_xg_for, new_h_xg_against, new_h_played, new_h_attack, new_h_defense, home_team_id))

        # Salvataggio aggiornamenti away team
        cur.execute("""
            UPDATE teams
            SET elo = ?,
                recent_form = ?,
                xg_for = ?,
                xg_against = ?,
                matches_played_stats = ?,
                attack = ?,
                defense = ?
            WHERE id = ?
        """, (new_away_elo, new_away_form, new_a_xg_for, new_a_xg_against, new_a_played, new_a_attack, new_a_defense, away_team_id))

    conn.close()

    # 5. Ricalcolo classifica della lega
    recalculate_league_standings(league_id, db_path)

    return {
        "match_id": match_id,
        "score": f"{home_goals}-{away_goals}",
        "home_xg": home_xg,
        "away_xg": away_xg,
        "home_team": {
            "name": home_team["name"],
            "elo_change": d_home_elo,
            "new_elo": new_home_elo,
            "new_form": new_home_form,
            "new_xg_for": new_h_xg_for,
            "new_xg_against": new_h_xg_against,
        },
        "away_team": {
            "name": away_team["name"],
            "elo_change": d_away_elo,
            "new_elo": new_away_elo,
            "new_form": new_away_form,
            "new_xg_for": new_a_xg_for,
            "new_xg_against": new_a_xg_against,
        },
        "standings_updated": True,
    }
