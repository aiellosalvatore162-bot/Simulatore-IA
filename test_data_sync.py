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


def test_sync_rejects_previous_season(monkeypatch, tmp_path):
    monkeypatch.setenv("FOOTBALL_DATA_SEASON", "2025")
    try:
        data_sync.sync_current_season(
            season=2025, db_path=tmp_path / "previous.db", competition_codes=["SA"]
        )
    except data_sync.FootballDataError as exc:
        assert "2026/2027" in str(exc)
    else:
        raise AssertionError("La sincronizzazione non deve accettare la stagione 2025")


def test_sync_falls_back_to_offline_seed_when_providers_fail(monkeypatch, tmp_path):
    monkeypatch.delenv("FOOTBALL_DATA_API_KEY", raising=False)
    monkeypatch.setattr(
        data_sync,
        "_sofascore_season",
        lambda *args: (_ for _ in ()).throw(data_sync.FootballDataError("offline")),
    )
    result = data_sync.sync_current_season(
        season=2026,
        db_path=tmp_path / "offline.db",
        competition_codes=["SA", "PL"],
    )

    assert result["season"] == 2026
    assert all(item["source"] == "offline-seed" for item in result["synced"])
    assert database.get_all_leagues(db_path=tmp_path / "offline.db")
    serie_a_matches = database.get_matches(
        league_id=1, db_path=tmp_path / "offline.db", limit=1000
    )
    premier_matches = database.get_matches(
        league_id=2, db_path=tmp_path / "offline.db", limit=1000
    )
    assert len(serie_a_matches) == 380
    assert len(premier_matches) == 380
    assert len({match["matchday"] for match in serie_a_matches}) == 38
