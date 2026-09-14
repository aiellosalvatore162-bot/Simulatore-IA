"""
Modulo database.py - Gestione SQLite (data.db) per il simulatore calcistico.
Definisce lo schema e le operazioni CRUD per:
Leagues, Teams, Matches, Standings, TopScorers.
"""

from pathlib import Path
import sqlite3
from typing import Any, Dict, List, Optional

DB_FILE = Path(__file__).resolve().parent / "data.db"


def get_db_connection(db_path: Optional[str | Path] = None) -> sqlite3.Connection:
    """Restituisce una connessione al database SQLite con row_factory attivo."""
    target_path = db_path or DB_FILE
    conn = sqlite3.connect(str(target_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(db_path: Optional[str | Path] = None) -> None:
    """Inizializza le tabelle relazionali nel database SQLite."""
    conn = get_db_connection(db_path)
    with conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS leagues (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            country TEXT NOT NULL,
            type TEXT NOT NULL, -- 'domestic' o 'cup'
            logo TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS teams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            league_id INTEGER NOT NULL REFERENCES leagues(id) ON DELETE CASCADE,
            name TEXT NOT NULL UNIQUE,
            logo TEXT NOT NULL,
            elo REAL NOT NULL DEFAULT 1500.0,
            attack REAL NOT NULL DEFAULT 1.0,
            defense REAL NOT NULL DEFAULT 1.0,
            home_advantage REAL NOT NULL DEFAULT 1.15,
            recent_form TEXT NOT NULL DEFAULT 'D-D-D-D-D',
            xg_for REAL NOT NULL DEFAULT 1.35,
            xg_against REAL NOT NULL DEFAULT 1.20,
            matches_played_stats INTEGER NOT NULL DEFAULT 0,
            cards_factor REAL NOT NULL DEFAULT 1.0,
            corners_factor REAL NOT NULL DEFAULT 1.0
        );

        CREATE TABLE IF NOT EXISTS matches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            league_id INTEGER NOT NULL REFERENCES leagues(id) ON DELETE CASCADE,
            matchday TEXT NOT NULL,
            match_date TEXT NOT NULL,
            home_team_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
            away_team_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
            status TEXT NOT NULL DEFAULT 'scheduled', -- 'scheduled' o 'completed'
            home_goals INTEGER DEFAULT NULL,
            away_goals INTEGER DEFAULT NULL,
            home_xg REAL DEFAULT NULL,
            away_xg REAL DEFAULT NULL
        );

        CREATE TABLE IF NOT EXISTS standings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            league_id INTEGER NOT NULL REFERENCES leagues(id) ON DELETE CASCADE,
            team_id INTEGER NOT NULL UNIQUE REFERENCES teams(id) ON DELETE CASCADE,
            played INTEGER NOT NULL DEFAULT 0,
            won INTEGER NOT NULL DEFAULT 0,
            drawn INTEGER NOT NULL DEFAULT 0,
            lost INTEGER NOT NULL DEFAULT 0,
            goals_for INTEGER NOT NULL DEFAULT 0,
            goals_against INTEGER NOT NULL DEFAULT 0,
            goal_diff INTEGER NOT NULL DEFAULT 0,
            points INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS top_scorers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            league_id INTEGER NOT NULL REFERENCES leagues(id) ON DELETE CASCADE,
            team_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
            player_name TEXT NOT NULL,
            goals INTEGER NOT NULL DEFAULT 0,
            assists INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS simulation_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            match_id INTEGER,
            home_team_name TEXT NOT NULL,
            away_team_name TEXT NOT NULL,
            home_elo REAL NOT NULL,
            away_elo REAL NOT NULL,
            simulations_count INTEGER NOT NULL DEFAULT 50000,
            execution_time_ms REAL NOT NULL,
            best_convergence_market TEXT,
            best_convergence_lift REAL,
            best_convergence_prob REAL,
            best_value_bet_market TEXT,
            best_value_bet_odds REAL,
            best_value_bet_ev REAL,
            assistant_narrative TEXT,
            full_results_json TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS h2h_matches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            match_date TEXT NOT NULL,
            competition TEXT NOT NULL,
            home_team_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
            away_team_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
            home_goals INTEGER NOT NULL,
            away_goals INTEGER NOT NULL,
            outcome TEXT NOT NULL, -- '1', 'X', '2'
            total_goals INTEGER NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_teams_league ON teams(league_id);
        CREATE INDEX IF NOT EXISTS idx_matches_league ON matches(league_id);
        CREATE INDEX IF NOT EXISTS idx_matches_status ON matches(status);
        CREATE INDEX IF NOT EXISTS idx_standings_league ON standings(league_id, points DESC, goal_diff DESC);
        CREATE INDEX IF NOT EXISTS idx_scorers_league ON top_scorers(league_id, goals DESC);
        CREATE INDEX IF NOT EXISTS idx_history_created ON simulation_history(created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_h2h_teams ON h2h_matches(home_team_id, away_team_id);
        """)
    conn.close()


# Funzioni di utilità per query di lettura

def get_all_leagues(db_path: Optional[str | Path] = None) -> List[Dict[str, Any]]:
    conn = get_db_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT * FROM leagues ORDER BY id ASC")
    rows = [dict(row) for row in cur.fetchall()]
    conn.close()
    return rows


def get_league_by_id(league_id: int, db_path: Optional[str | Path] = None) -> Optional[Dict[str, Any]]:
    conn = get_db_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT * FROM leagues WHERE id = ?", (league_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def get_teams_by_league(league_id: int, db_path: Optional[str | Path] = None) -> List[Dict[str, Any]]:
    conn = get_db_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT * FROM teams WHERE league_id = ? ORDER BY elo DESC", (league_id,))
    rows = [dict(row) for row in cur.fetchall()]
    conn.close()
    return rows


def get_team_by_id(team_id: int, db_path: Optional[str | Path] = None) -> Optional[Dict[str, Any]]:
    conn = get_db_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT * FROM teams WHERE id = ?", (team_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def get_team_by_name(team_name: str, db_path: Optional[str | Path] = None) -> Optional[Dict[str, Any]]:
    conn = get_db_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT * FROM teams WHERE LOWER(name) = LOWER(?)", (team_name.strip(),))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def get_standings_by_league(league_id: int, db_path: Optional[str | Path] = None) -> List[Dict[str, Any]]:
    conn = get_db_connection(db_path)
    cur = conn.cursor()
    cur.execute("""
        SELECT 
            s.*,
            t.name as team_name,
            t.logo as team_logo,
            t.recent_form,
            t.elo,
            t.xg_for,
            t.xg_against
        FROM standings s
        JOIN teams t ON s.team_id = t.id
        WHERE s.league_id = ?
        ORDER BY s.points DESC, s.goal_diff DESC, s.goals_for DESC
    """, (league_id,))
    rows = [dict(row) for row in cur.fetchall()]
    conn.close()
    return rows


def get_top_scorers_by_league(league_id: int, limit: int = 15, db_path: Optional[str | Path] = None) -> List[Dict[str, Any]]:
    conn = get_db_connection(db_path)
    cur = conn.cursor()
    cur.execute("""
        SELECT 
            ts.*,
            t.name as team_name,
            t.logo as team_logo
        FROM top_scorers ts
        JOIN teams t ON ts.team_id = t.id
        WHERE ts.league_id = ?
        ORDER BY ts.goals DESC, ts.assists DESC
        LIMIT ?
    """, (league_id, limit))
    rows = [dict(row) for row in cur.fetchall()]
    conn.close()
    return rows


def get_matches(
    league_id: Optional[int] = None,
    status: Optional[str] = None,
    matchday: Optional[str] = None,
    limit: int = 50,
    db_path: Optional[str | Path] = None
) -> List[Dict[str, Any]]:
    conn = get_db_connection(db_path)
    cur = conn.cursor()
    query = """
        SELECT 
            m.*,
            l.name as league_name,
            ht.name as home_team_name,
            ht.logo as home_team_logo,
            ht.elo as home_team_elo,
            at.name as away_team_name,
            at.logo as away_team_logo,
            at.elo as away_team_elo
        FROM matches m
        JOIN leagues l ON m.league_id = l.id
        JOIN teams ht ON m.home_team_id = ht.id
        JOIN teams at ON m.away_team_id = at.id
        WHERE 1=1
    """
    params = []
    if league_id is not None:
        query += " AND m.league_id = ?"
        params.append(league_id)
    if status is not None:
        query += " AND m.status = ?"
        params.append(status)
    if matchday is not None:
        query += " AND m.matchday = ?"
        params.append(matchday)
    
    query += " ORDER BY m.match_date ASC, m.id ASC LIMIT ?"
    params.append(limit)

    cur.execute(query, params)
    rows = [dict(row) for row in cur.fetchall()]
    conn.close()
    return rows


def get_match_by_id(match_id: int, db_path: Optional[str | Path] = None) -> Optional[Dict[str, Any]]:
    conn = get_db_connection(db_path)
    cur = conn.cursor()
    cur.execute("""
        SELECT 
            m.*,
            l.name as league_name,
            ht.name as home_team_name,
            ht.attack as home_attack,
            ht.defense as home_defense,
            ht.elo as home_elo,
            ht.cards_factor as home_cards_factor,
            ht.corners_factor as home_corners_factor,
            ht.home_advantage as home_advantage,
            at.name as away_team_name,
            at.attack as away_attack,
            at.defense as away_defense,
            at.elo as away_elo,
            at.cards_factor as away_cards_factor,
            at.corners_factor as away_corners_factor
        FROM matches m
        JOIN leagues l ON m.league_id = l.id
        JOIN teams ht ON m.home_team_id = ht.id
        JOIN teams at ON m.away_team_id = at.id
        WHERE m.id = ?
    """, (match_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


# --- GESTIONE SIMULATION HISTORY ---

def save_simulation_history(
    home_team_name: str,
    away_team_name: str,
    home_elo: float,
    away_elo: float,
    execution_time_ms: float,
    full_results_json: str,
    match_id: Optional[int] = None,
    simulations_count: int = 50_000,
    best_convergence_market: Optional[str] = None,
    best_convergence_lift: Optional[float] = None,
    best_convergence_prob: Optional[float] = None,
    best_value_bet_market: Optional[str] = None,
    best_value_bet_odds: Optional[float] = None,
    best_value_bet_ev: Optional[float] = None,
    assistant_narrative: Optional[str] = None,
    created_at: Optional[str] = None,
    db_path: Optional[str | Path] = None
) -> int:
    import datetime
    conn = get_db_connection(db_path)
    now_iso = created_at or datetime.datetime.now(datetime.timezone.utc).isoformat()
    with conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO simulation_history (
                created_at, match_id, home_team_name, away_team_name,
                home_elo, away_elo, simulations_count, execution_time_ms,
                best_convergence_market, best_convergence_lift, best_convergence_prob,
                best_value_bet_market, best_value_bet_odds, best_value_bet_ev,
                assistant_narrative, full_results_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            now_iso, match_id, home_team_name, away_team_name,
            home_elo, away_elo, simulations_count, execution_time_ms,
            best_convergence_market, best_convergence_lift, best_convergence_prob,
            best_value_bet_market, best_value_bet_odds, best_value_bet_ev,
            assistant_narrative, full_results_json
        ))
        inserted_id = cur.lastrowid
    conn.close()
    return inserted_id


def get_simulation_history(limit: int = 50, offset: int = 0, db_path: Optional[str | Path] = None) -> List[Dict[str, Any]]:
    conn = get_db_connection(db_path)
    cur = conn.cursor()
    cur.execute("""
        SELECT 
            id, created_at, match_id, home_team_name, away_team_name,
            home_elo, away_elo, simulations_count, execution_time_ms,
            best_convergence_market, best_convergence_lift, best_convergence_prob,
            best_value_bet_market, best_value_bet_odds, best_value_bet_ev,
            assistant_narrative
        FROM simulation_history
        ORDER BY created_at DESC, id DESC
        LIMIT ? OFFSET ?
    """, (limit, offset))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def get_simulation_history_by_id(history_id: int, db_path: Optional[str | Path] = None) -> Optional[Dict[str, Any]]:
    conn = get_db_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT * FROM simulation_history WHERE id = ?", (history_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def delete_simulation_history(history_id: int, db_path: Optional[str | Path] = None) -> bool:
    conn = get_db_connection(db_path)
    with conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM simulation_history WHERE id = ?", (history_id,))
        deleted = cur.rowcount > 0
    conn.close()
    return deleted


# --- GESTIONE HEAD-TO-HEAD (H2H) ---

def get_h2h_matches(team_a_id: int, team_b_id: int, limit: int = 5, db_path: Optional[str | Path] = None) -> Dict[str, Any]:
    conn = get_db_connection(db_path)
    cur = conn.cursor()
    cur.execute("""
        SELECT 
            h.*,
            ht.name as home_team_name,
            at.name as away_team_name
        FROM h2h_matches h
        JOIN teams ht ON h.home_team_id = ht.id
        JOIN teams at ON h.away_team_id = at.id
        WHERE (h.home_team_id = ? AND h.away_team_id = ?)
           OR (h.home_team_id = ? AND h.away_team_id = ?)
        ORDER BY h.match_date DESC, h.id DESC
        LIMIT ?
    """, (team_a_id, team_b_id, team_b_id, team_a_id, limit))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()

    # Calcolo bilancio H2H
    team_a_wins = 0
    team_b_wins = 0
    draws = 0
    total_goals = 0

    for m in rows:
        total_goals += m["total_goals"]
        hg = m["home_goals"]
        ag = m["away_goals"]
        if hg == ag:
            draws += 1
        elif (m["home_team_id"] == team_a_id and hg > ag) or (m["away_team_id"] == team_a_id and ag > hg):
            team_a_wins += 1
        else:
            team_b_wins += 1

    return {
        "matches": rows,
        "summary": {
            "total_matches": len(rows),
            "team_a_wins": team_a_wins,
            "team_b_wins": team_b_wins,
            "draws": draws,
            "avg_goals": round(total_goals / len(rows), 2) if rows else 0.0
        }
    }
