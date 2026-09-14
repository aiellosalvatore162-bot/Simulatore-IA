"""Sincronizzazione dati calcistici da football-data.org."""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import date
from pathlib import Path
from typing import Any, Dict, Iterable, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from database import DB_FILE, get_db_connection, init_db

FOOTBALL_DATA_BASE_URL = "https://api.football-data.org/v4"
SOFASCORE_BASE_URL = "https://www.sofascore.com/api/v1"
DEFAULT_SEASON = date.today().year

# Codici ufficiali football-data.org. Le competizioni non disponibili per il
# piano/API in uso vengono riportate come errore, senza dati inventati.
COMPETITIONS = {
    "SA": "Serie A",
    "PL": "Premier League",
    "FL1": "Ligue 1",
    "PD": "La Liga",
    "PPL": "Campionato Portoghese",
    "BL1": "Bundesliga",
    "DED": "Eredivisie",
    "CL": "Champions League",
}

SOFASCORE_TOURNAMENTS = {
    "SA": 23,
    "PL": 17,
    "FL1": 34,
    "PD": 8,
    "PPL": 238,
    "BL1": 35,
    "DED": 37,
    "CL": 7,
}


class FootballDataError(RuntimeError):
    """Errore leggibile restituito dal provider football-data.org."""

    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


def _request_json(path: str, api_key: str) -> Dict[str, Any]:
    query = urlencode({"season": os.getenv("FOOTBALL_DATA_SEASON", str(DEFAULT_SEASON))})
    request = Request(
        f"{FOOTBALL_DATA_BASE_URL}{path}?{query}",
        headers={"X-Auth-Token": api_key, "Accept": "application/json"},
    )
    try:
        with urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise FootballDataError(
            f"football-data.org HTTP {exc.code}: {detail[:300]}",
            status_code=exc.code,
        ) from exc
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise FootballDataError(f"football-data.org non raggiungibile: {exc}") from exc


def _sofascore_request(path: str) -> Dict[str, Any]:
    request = Request(
        f"{SOFASCORE_BASE_URL}{path}",
        headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
    )
    try:
        with urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise FootballDataError(
            f"SofaScore HTTP {exc.code}: {detail[:300]}", status_code=exc.code
        ) from exc
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise FootballDataError(f"SofaScore non raggiungibile: {exc}") from exc


def _sofascore_season(code: str, season: int) -> int:
    payload = _sofascore_request(f"/unique-tournament/{SOFASCORE_TOURNAMENTS[code]}/seasons")
    seasons = payload.get("seasons", [])
    wanted = str(season)
    for item in seasons:
        name = str(item.get("name", ""))
        if wanted in name or f"{season - 1}/{str(season)[-2:]}" in name:
            return int(item["id"])
    raise FootballDataError(f"SofaScore: stagione {season} non trovata per {code}")


def _sofascore_events(code: str, season_id: int) -> Iterable[Dict[str, Any]]:
    events: list[Dict[str, Any]] = []
    for direction in ("last", "next"):
        for page in range(0, 10):
            payload = _sofascore_request(
                f"/unique-tournament/{SOFASCORE_TOURNAMENTS[code]}/season/{season_id}/events/{direction}/{page}"
            )
            batch = payload.get("events", [])
            events.extend(batch)
            if not payload.get("hasNextPage") or not batch:
                break
    return {event["id"]: event for event in events if event.get("id")}.values()


def _sofascore_team(event_team: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not event_team or not event_team.get("id") or not event_team.get("name"):
        return None
    return {
        "id": event_team["id"],
        "name": event_team["name"],
        "crest": event_team.get("avatar") or event_team.get("logo") or "",
    }


def _recalculate_imported_team_stats(conn: sqlite3.Connection, league_ids: Iterable[int]) -> None:
    """Ricalcola forma e partite giocate dai risultati appena importati."""
    for league_id in league_ids:
        teams = conn.execute("SELECT id FROM teams WHERE league_id = ?", (league_id,)).fetchall()
        for team in teams:
            rows = conn.execute(
                """SELECT home_team_id, away_team_id, home_goals, away_goals
                   FROM matches
                   WHERE league_id = ? AND status = 'completed'
                     AND (home_team_id = ? OR away_team_id = ?)
                   ORDER BY match_date DESC, id DESC LIMIT 5""",
                (league_id, team["id"], team["id"]),
            ).fetchall()
            form = []
            for row in reversed(rows):
                if row["home_goals"] is None or row["away_goals"] is None:
                    continue
                if row["home_team_id"] == team["id"]:
                    result = "W" if row["home_goals"] > row["away_goals"] else "L" if row["home_goals"] < row["away_goals"] else "D"
                else:
                    result = "W" if row["away_goals"] > row["home_goals"] else "L" if row["away_goals"] < row["home_goals"] else "D"
                form.append(result)
            played = conn.execute(
                """SELECT COUNT(*) AS count FROM matches
                   WHERE league_id = ? AND status = 'completed'
                     AND (home_team_id = ? OR away_team_id = ?)""",
                (league_id, team["id"], team["id"]),
            ).fetchone()["count"]
            conn.execute(
                "UPDATE teams SET recent_form = ?, matches_played_stats = ?, xg_source = 'not_available' WHERE id = ?",
                ("-".join(form) or "D-D-D-D-D", played, team["id"]),
            )


def _sync_sofascore_competition(
    conn: sqlite3.Connection,
    code: str,
    season: int,
    teams: Dict[tuple[int, int], int],
    used_names: set[str],
) -> Dict[str, Any]:
    league_name = COMPETITIONS[code]
    league_id = _competition_id(conn, league_name)
    season_id = _sofascore_season(code, season)
    events = _sofascore_events(code, season_id)
    if not events:
        raise FootballDataError(f"SofaScore: nessuna partita trovata per {league_name}")

    for event in events:
        home = _team_id(conn, _sofascore_team(event.get("homeTeam")), league_id, league_name, teams, used_names)
        away = _team_id(conn, _sofascore_team(event.get("awayTeam")), league_id, league_name, teams, used_names)
        if not home or not away:
            continue
        status = "completed" if event.get("status", {}).get("type") == "finished" else "scheduled"
        score = event.get("homeScore", {})
        away_score = event.get("awayScore", {})
        timestamp = event.get("startTimestamp")
        match_date = date.fromtimestamp(timestamp).isoformat() if timestamp else ""
        conn.execute(
            """INSERT INTO matches
            (league_id, matchday, match_date, home_team_id, away_team_id, status,
             home_goals, away_goals, home_xg, away_xg)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL)""",
            (league_id, str(event.get("roundInfo", {}).get("round", "")), match_date,
             home, away, status,
             score.get("current") if status == "completed" else None,
             away_score.get("current") if status == "completed" else None),
        )

    standings_payload = _sofascore_request(
        f"/unique-tournament/{SOFASCORE_TOURNAMENTS[code]}/season/{season_id}/standings/overall"
    )
    rows = standings_payload.get("standings", [{}])[0].get("rows", [])
    for row in rows:
        team_id = _team_id(conn, _sofascore_team(row.get("team")), league_id, league_name, teams, used_names)
        if not team_id:
            continue
        conn.execute(
            """INSERT INTO standings
            (league_id, team_id, played, won, drawn, lost, goals_for, goals_against, goal_diff, points)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(team_id) DO UPDATE SET played=excluded.played, won=excluded.won,
            drawn=excluded.drawn, lost=excluded.lost, goals_for=excluded.goals_for,
            goals_against=excluded.goals_against, goal_diff=excluded.goal_diff, points=excluded.points""",
            (league_id, team_id, row.get("matches", 0), row.get("wins", 0), row.get("draws", 0),
             row.get("losses", 0), row.get("scoresFor", 0), row.get("scoresAgainst", 0),
             row.get("scoresFor", 0) - row.get("scoresAgainst", 0), row.get("points", 0)),
        )

    scorer_payload = _sofascore_request(
        f"/unique-tournament/{SOFASCORE_TOURNAMENTS[code]}/season/{season_id}/top-players/overall?accumulation=total&fields=goals"
    )
    scorer_rows = scorer_payload.get("topPlayers", {}).get("goals", [])
    for row in scorer_rows:
        player = row.get("statistics", {}).get("player") or row.get("player") or {}
        team = _sofascore_team(row.get("team"))
        team_id = _team_id(conn, team, league_id, league_name, teams, used_names)
        if team_id and player.get("name"):
            conn.execute(
                "INSERT INTO top_scorers (league_id, team_id, player_name, goals, assists) VALUES (?, ?, ?, ?, ?)",
                (league_id, team_id, player["name"], row.get("statistics", {}).get("goals", row.get("goals", 0)) or 0, 0),
            )
    return {"code": code, "league": league_name, "source": "SofaScore", "matches": len(events), "standings": len(rows), "scorers": len(scorer_rows)}


def _competition_id(conn: sqlite3.Connection, name: str) -> int:
    row = conn.execute("SELECT id FROM leagues WHERE name = ?", (name,)).fetchone()
    if row:
        return int(row["id"])
    cursor = conn.execute(
        "INSERT INTO leagues (name, country, type, logo) VALUES (?, ?, ?, ?)",
        (name, "Europa" if name in {"Champions League", "Europa League", "Conference League"} else "", "cup" if name in {"Champions League", "Europa League", "Conference League"} else "domestic", ""),
    )
    return int(cursor.lastrowid)


def _team_name(api_name: str, league_name: str, used_names: set[str]) -> str:
    """Mantiene nomi ufficiali, disambiguando solo il vincolo storico globale."""
    if api_name not in used_names:
        return api_name
    candidate = f"{api_name} [{league_name}]"
    counter = 2
    while candidate in used_names:
        candidate = f"{api_name} [{league_name} {counter}]"
        counter += 1
    return candidate


def _status(api_status: str) -> str:
    return "completed" if api_status in {"FINISHED", "AWARDED"} else "scheduled"


def _team_id(
    conn: sqlite3.Connection,
    team: Optional[Dict[str, Any]],
    league_id: int,
    league_name: str,
    teams: Dict[tuple[int, int], int],
    used_names: set[str],
) -> Optional[int]:
    if not team or not team.get("id") or not team.get("name"):
        return None
    provider_id = int(team["id"])
    key = (league_id, provider_id)
    if key in teams:
        return teams[key]
    display_name = _team_name(str(team["name"]), league_name, used_names)
    cursor = conn.execute(
        """INSERT INTO teams
        (league_id, name, logo, elo, attack, defense, home_advantage,
         recent_form, xg_for, xg_against, matches_played_stats, cards_factor, corners_factor)
        VALUES (?, ?, ?, 1500, 1, 1, 1.15, 'D-D-D-D-D', 1.35, 1.20, 0, 1, 1)""",
        (league_id, display_name, team.get("crest") or ""),
    )
    team_id = int(cursor.lastrowid)
    teams[key] = team_id
    used_names.add(display_name)
    return team_id


def _sync_competition(
    conn: sqlite3.Connection,
    code: str,
    season: int,
    api_key: str,
    teams: Dict[tuple[int, int], int],
    used_names: set[str],
) -> Dict[str, Any]:
    league_name = COMPETITIONS[code]
    league_id = _competition_id(conn, league_name)
    matches_payload = _request_json(f"/competitions/{code}/matches", api_key)
    standings_payload = _request_json(f"/competitions/{code}/standings", api_key)
    scorers_payload = _request_json(f"/competitions/{code}/scorers", api_key)

    matches = matches_payload.get("matches", [])
    table = next((item for item in standings_payload.get("standings", []) if item.get("type") == "TOTAL"), None)
    standings = (table or {}).get("table", [])
    scorers = scorers_payload.get("scorers", [])

    for match in matches:
        home_id = _team_id(conn, match.get("homeTeam"), league_id, league_name, teams, used_names)
        away_id = _team_id(conn, match.get("awayTeam"), league_id, league_name, teams, used_names)
        if not home_id or not away_id or not match.get("id"):
            continue
        score = match.get("score", {}).get("fullTime", {})
        status = _status(str(match.get("status", "SCHEDULED")))
        conn.execute(
            """INSERT INTO matches
            (league_id, matchday, match_date, home_team_id, away_team_id, status,
             home_goals, away_goals, home_xg, away_xg)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL)""",
            (league_id, str(match.get("matchday") or ""), str(match.get("utcDate", ""))[:10],
             home_id, away_id, status,
             score.get("home") if status == "completed" else None,
             score.get("away") if status == "completed" else None),
        )

    for row in standings:
        team_id = _team_id(conn, row.get("team"), league_id, league_name, teams, used_names)
        if not team_id:
            continue
        conn.execute(
            """INSERT INTO standings
            (league_id, team_id, played, won, drawn, lost, goals_for, goals_against, goal_diff, points)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(team_id) DO UPDATE SET
                played=excluded.played, won=excluded.won, drawn=excluded.drawn,
                lost=excluded.lost, goals_for=excluded.goals_for,
                goals_against=excluded.goals_against, goal_diff=excluded.goal_diff,
                points=excluded.points""",
            (league_id, team_id, row.get("playedGames", 0), row.get("won", 0),
             row.get("draw", 0), row.get("lost", 0), row.get("goalsFor", 0),
             row.get("goalsAgainst", 0), row.get("goalDifference", 0), row.get("points", 0)),
        )

    for scorer in scorers:
        team_id = _team_id(conn, scorer.get("team"), league_id, league_name, teams, used_names)
        player = scorer.get("player") or {}
        if team_id and player.get("name"):
            goals = scorer.get("goals") or 0
            assists = scorer.get("assists") or 0
            conn.execute(
                "INSERT INTO top_scorers (league_id, team_id, player_name, goals, assists) VALUES (?, ?, ?, ?, ?)",
                (league_id, team_id, player["name"], goals, assists),
            )

    return {"code": code, "league": league_name, "matches": len(matches), "standings": len(standings), "scorers": len(scorers)}


def sync_current_season(
    season: Optional[int] = None,
    db_path: Optional[str | Path] = None,
    competition_codes: Optional[Iterable[str]] = None,
) -> Dict[str, Any]:
    """Scarica e sostituisce i dati delle competizioni richieste."""
    api_key = os.getenv("FOOTBALL_DATA_API_KEY")
    selected_season = season or int(os.getenv("FOOTBALL_DATA_SEASON", DEFAULT_SEASON))
    os.environ["FOOTBALL_DATA_SEASON"] = str(selected_season)
    configured_competitions = os.getenv("FOOTBALL_DATA_COMPETITIONS")
    if competition_codes:
        selected = list(competition_codes)
    elif configured_competitions:
        selected = [code.strip() for code in configured_competitions.split(",") if code.strip()]
    else:
        selected = list(COMPETITIONS)
    unknown = [code for code in selected if code not in COMPETITIONS]
    if unknown:
        raise FootballDataError(f"Codici competizione non supportati: {', '.join(unknown)}")

    init_db(db_path)
    conn = get_db_connection(db_path)
    results = []
    errors = []
    fatal_errors = []
    try:
        with conn:
            selected_league_ids = [_competition_id(conn, COMPETITIONS[code]) for code in selected]
            placeholders = ",".join("?" for _ in selected_league_ids)
            conn.execute(
                f"""DELETE FROM h2h_matches
                WHERE home_team_id IN (SELECT id FROM teams WHERE league_id IN ({placeholders}))
                   OR away_team_id IN (SELECT id FROM teams WHERE league_id IN ({placeholders}))""",
                selected_league_ids + selected_league_ids,
            )
            conn.execute(f"DELETE FROM matches WHERE league_id IN ({placeholders})", selected_league_ids)
            conn.execute(f"DELETE FROM top_scorers WHERE league_id IN ({placeholders})", selected_league_ids)
            conn.execute(f"DELETE FROM standings WHERE league_id IN ({placeholders})", selected_league_ids)
            conn.execute(f"DELETE FROM teams WHERE league_id IN ({placeholders})", selected_league_ids)
            teams: Dict[tuple[int, int], int] = {}
            used_names = {row["name"] for row in conn.execute("SELECT name FROM teams")}
            for code in selected:
                try:
                    if api_key:
                        results.append(_sync_competition(conn, code, selected_season, api_key, teams, used_names))
                    else:
                        results.append(_sync_sofascore_competition(conn, code, selected_season, teams, used_names))
                except FootballDataError as exc:
                    if api_key and exc.status_code in {403, 404}:
                        try:
                            results.append(_sync_sofascore_competition(conn, code, selected_season, teams, used_names))
                            continue
                        except FootballDataError as fallback_exc:
                            exc = fallback_exc
                    errors.append({"code": code, "league": COMPETITIONS[code], "error": str(exc)})
                    if exc.status_code not in {403, 404}:
                        fatal_errors.append(exc)
            if fatal_errors:
                summary = "; ".join(str(error) for error in fatal_errors)
                raise FootballDataError(f"Sincronizzazione annullata: {summary}")
            _recalculate_imported_team_stats(conn, selected_league_ids)
    finally:
        conn.close()

    return {"season": selected_season, "synced": results, "errors": errors}


if __name__ == "__main__":
    print(json.dumps(sync_current_season(), ensure_ascii=False, indent=2))
