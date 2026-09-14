"""
Test automatici di integrità per database SQLite, seed, updater e API con simulazione.
"""

from fastapi.testclient import TestClient
import pytest
import database
from main import app
import updater

client = TestClient(app)


def test_database_and_seed_integrity():
    """Verifica che tutte le 12 leghe e le relative squadre/classifiche siano caricate."""
    leagues = database.get_all_leagues()
    assert len(leagues) == 12, f"Attese 12 leghe, trovate {len(leagues)}"

    league_names = [l["name"] for l in leagues]
    expected_leagues = [
        "Serie A", "Premier League", "Ligue 1", "La Liga",
        "Campionato Portoghese", "Campionato Belga", "Bundesliga",
        "Eredivisie", "Süper Lig", "Champions League", "Europa League", "Conference League"
    ]
    for el in expected_leagues:
        assert el in league_names, f"Lega mancante: {el}"

    # Verifica squadre Serie A
    serie_a_teams = database.get_teams_by_league(1)
    assert len(serie_a_teams) == 20
    # Verifica che le big abbiano Elo alto e non appiattito
    inter = [t for t in serie_a_teams if t["name"] == "Inter"][0]
    assert inter["elo"] > 1800.0
    assert inter["attack"] > 1.30

    # Verifica classifica Serie A
    standings = database.get_standings_by_league(1)
    assert len(standings) == 20
    assert standings[0]["points"] >= standings[-1]["points"]

    # Verifica marcatori
    scorers = database.get_top_scorers_by_league(1)
    assert len(scorers) > 0
    assert scorers[0]["goals"] >= 1


def test_updater_complete_match():
    """Verifica che la conclusione di un match aggiorni classifica, Elo, forma e medie xG."""
    # Cerchiamo un match 'scheduled' in Serie A
    scheduled = database.get_matches(league_id=1, status="scheduled")
    assert len(scheduled) > 0
    target_match = scheduled[0]
    m_id = target_match["id"]
    h_id = target_match["home_team_id"]
    a_id = target_match["away_team_id"]

    h_team_before = database.get_team_by_id(h_id)
    a_team_before = database.get_team_by_id(a_id)

    # Concludiamo il match con vittoria casa 2-0
    update_res = updater.complete_match(
        match_id=m_id,
        home_goals=2,
        away_goals=0,
        home_xg=2.1,
        away_xg=0.5
    )
    assert update_res["score"] == "2-0"
    assert update_res["home_team"]["elo_change"] > 0
    assert update_res["away_team"]["elo_change"] < 0

    h_team_after = database.get_team_by_id(h_id)
    a_team_after = database.get_team_by_id(a_id)

    # Verifica Elo aggiornato
    assert h_team_after["elo"] > h_team_before["elo"]
    assert a_team_after["elo"] < a_team_before["elo"]

    # Verifica forma recente aggiornata
    assert h_team_after["recent_form"].endswith("W")
    assert a_team_after["recent_form"].endswith("L")

    # Verifica match marcato come completed nel DB
    completed_m = database.get_match_by_id(m_id)
    assert completed_m["status"] == "completed"
    assert completed_m["home_goals"] == 2
    assert completed_m["away_goals"] == 0


def test_api_simulate_with_database():
    """Verifica che /api/simulate peschi automaticamente i parametri dal DB SQLite."""
    inter = [t for t in database.get_teams_by_league(1) if t["name"] == "Inter"][0]
    juve = [t for t in database.get_teams_by_league(1) if t["name"] == "Juventus"][0]

    payload = {
        "home_team_id": inter["id"],
        "away_team_id": juve["id"],
        "n_simulations": 50_000
    }
    response = client.post("/api/simulate", json=payload)
    assert response.status_code == 200
    data = response.json()
    meta = data["metadata"]

    assert meta["simulations_count"] == 50_000
    assert meta["database_source"]["home_team_name"] == "Inter"
    assert meta["database_source"]["away_team_name"] == "Juventus"
    assert meta["database_source"]["home_team_elo"] > 1750.0

    # Verifica mercati
    assert len(data["markets"]) == 15
    assert "best_synergy_market" in data["market_convergence"]


def test_api_simulate_get_endpoint():
    """Verifica endpoint GET /api/simulate."""
    inter = [t for t in database.get_teams_by_league(1) if t["name"] == "Inter"][0]
    milan = [t for t in database.get_teams_by_league(1) if t["name"] == "Milan"][0]

    r = client.get(f"/api/simulate?home_team_id={inter['id']}&away_team_id={milan['id']}")
    assert r.status_code == 200
    data = r.json()
    assert data["metadata"]["database_source"]["home_team_name"] == "Inter"
    assert data["metadata"]["database_source"]["away_team_name"] == "Milan"


def test_api_rest_endpoints():
    """Verifica endpoint REST /api/leagues, /api/matches, ecc."""
    r_leagues = client.get("/api/leagues")
    assert r_leagues.status_code == 200
    assert len(r_leagues.json()) == 12

    r_standings = client.get("/api/leagues/1/standings")
    assert r_standings.status_code == 200
    assert len(r_standings.json()) == 20

    r_scorers = client.get("/api/leagues/1/top-scorers")
    assert r_scorers.status_code == 200
    assert len(r_scorers.json()) > 0

    r_matches = client.get("/api/matches?league_id=1")
    assert r_matches.status_code == 200
    assert len(r_matches.json()) > 0
