import data_sync
import database


def test_sync_imports_official_payload(monkeypatch, tmp_path):
    payloads = {
        "/competitions/SA/matches": {
            "matches": [{
                "id": 11,
                "matchday": 1,
                "utcDate": "2026-08-23T18:00:00Z",
                "status": "FINISHED",
                "homeTeam": {"id": 1, "name": "Inter", "crest": "inter.png"},
                "awayTeam": {"id": 2, "name": "Torino", "crest": "torino.png"},
                "score": {"fullTime": {"home": 2, "away": 0}},
            }]
        },
        "/competitions/SA/standings": {
            "standings": [{"type": "TOTAL", "table": [{
                "position": 1,
                "team": {"id": 1, "name": "Inter", "crest": "inter.png"},
                "playedGames": 1,
                "won": 1,
                "draw": 0,
                "lost": 0,
                "goalsFor": 2,
                "goalsAgainst": 0,
                "goalDifference": 2,
                "points": 3,
            }]}]
        },
        "/competitions/SA/scorers": {
            "scorers": [{
                "player": {"name": "Lautaro Martinez"},
                "team": {"id": 1, "name": "Inter", "crest": "inter.png"},
                "goals": 1,
                "assists": None,
            }]
        },
    }

    monkeypatch.setenv("FOOTBALL_DATA_API_KEY", "test-key")
    monkeypatch.setattr(
        data_sync,
        "_request_json",
        lambda path, api_key: payloads[path],
    )

    result = data_sync.sync_current_season(
        season=2026,
        db_path=tmp_path / "sync.db",
        competition_codes=["SA"],
    )

    assert result["season"] == 2026
    assert result["synced"][0]["matches"] == 1
    assert database.get_matches(league_id=1, db_path=tmp_path / "sync.db")[0]["status"] == "completed"
    assert database.get_standings_by_league(1, db_path=tmp_path / "sync.db")[0]["points"] == 3
    assert database.get_top_scorers_by_league(1, db_path=tmp_path / "sync.db")[0]["player_name"] == "Lautaro Martinez"


def test_sync_uses_sofascore_without_football_data_key(monkeypatch, tmp_path):
    monkeypatch.delenv("FOOTBALL_DATA_API_KEY", raising=False)
    monkeypatch.setattr(
        data_sync,
        "_sync_sofascore_competition",
        lambda *args: {"code": "SA", "source": "SofaScore", "matches": 1, "standings": 1, "scorers": 1},
    )
    result = data_sync.sync_current_season(db_path=tmp_path / "sync.db", competition_codes=["SA"])
    assert result["synced"][0]["source"] == "SofaScore"


def test_sync_rejects_unknown_competition(monkeypatch, tmp_path):
    monkeypatch.setenv("FOOTBALL_DATA_API_KEY", "test-key")
    try:
        data_sync.sync_current_season(db_path=tmp_path / "sync.db", competition_codes=["UNKNOWN"])
    except data_sync.FootballDataError as exc:
        assert "UNKNOWN" in str(exc)
    else:
        raise AssertionError("La sincronizzazione deve rifiutare codici sconosciuti")
