import data_sync
import database

CURRENT_SEASON = 2026
CURRENT_SEASON_LABEL = "2026/2027"


def test_sync_populates_complete_local_snapshot(tmp_path):
    result = data_sync.sync_current_season(
        season=CURRENT_SEASON,
        db_path=tmp_path / "sync.db",
        competition_codes=["SA"],
    )

    assert result["season"] == CURRENT_SEASON
    assert result["source"] == "local-seed"
    assert result["synced"][0]["source"] == "local-seed"
    assert len(database.get_matches(league_id=1, db_path=tmp_path / "sync.db", limit=1000)) == 380


def test_sync_rejects_unknown_competition(monkeypatch, tmp_path):
    monkeypatch.setenv("FOOTBALL_DATA_API_KEY", "test-key")
    try:
        data_sync.sync_current_season(db_path=tmp_path / "sync.db", competition_codes=["UNKNOWN"])
    except data_sync.FootballDataError as exc:
        assert "UNKNOWN" in str(exc)
    else:
        raise AssertionError("La sincronizzazione deve rifiutare codici sconosciuti")


def test_sync_rejects_previous_season(tmp_path):
    """Una stagione precedente deve essere rifiutata senza toccare il DB."""
    try:
        data_sync.sync_current_season(
            season=2025, db_path=tmp_path / "previous.db", competition_codes=["SA"]
        )
    except data_sync.FootballDataError as exc:
        assert "2026/2027" in str(exc)
    else:
        raise AssertionError("La sincronizzazione non deve accettare la stagione 2025")


def test_sync_rebuilds_all_competitions_from_local_seed(tmp_path):
    result = data_sync.sync_current_season(
        season=CURRENT_SEASON,
        db_path=tmp_path / "offline.db",
        competition_codes=["SA", "PL"],
    )

    assert result["season"] == CURRENT_SEASON
    assert all(item["source"] == "local-seed" for item in result["synced"])
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


def test_local_snapshot_covers_all_managed_competitions(tmp_path):
    data_sync.sync_current_season(db_path=tmp_path / "all.db")
    expected = {
        "Serie A": 380,
        "Premier League": 380,
        "Ligue 1": 306,
        "La Liga": 380,
        "Campionato Portoghese": 306,
        "Campionato Belga": 240,
        "Bundesliga": 306,
        "Eredivisie": 306,
        "Süper Lig": 306,
        "Champions League": 1260,
        "Europa League": 1260,
        "Conference League": 1260,
    }
    leagues = {row["name"]: row["id"] for row in database.get_all_leagues(tmp_path / "all.db")}
    assert set(expected).issubset(leagues)
    for name, expected_matches in expected.items():
        assert len(database.get_matches(leagues[name], db_path=tmp_path / "all.db", limit=2000)) == expected_matches


def test_startup_rebuilds_non_current_database(tmp_path):
    db_path = tmp_path / "legacy.db"
    data_sync.sync_current_season(db_path=db_path)
    conn = database.get_db_connection(db_path)
    conn.execute(
        "UPDATE app_metadata SET value = '2025/2026' WHERE key = 'season'"
    )
    conn.execute(
        "UPDATE matches SET matchday = 'Legacy giornata' WHERE league_id = 1 LIMIT 1"
    )
    conn.execute(
        "UPDATE matches SET match_date = '2025-09-01' WHERE league_id = 2 LIMIT 1"
    )
    conn.commit()
    conn.close()

    assert database.ensure_production_database(db_path) is True

    conn = database.get_db_connection(db_path)
    season = conn.execute(
        "SELECT value FROM app_metadata WHERE key = 'season'"
    ).fetchone()["value"]
    conn.close()
    assert season == CURRENT_SEASON_LABEL
    assert not database.get_matches(
        league_id=1, db_path=db_path, limit=1000
    )[0]["matchday"].startswith("Legacy")
    assert all(
        match["match_date"] >= "2026-07-01"
        for match in database.get_matches(league_id=2, db_path=db_path, limit=1000)
    )
    assert all(
        match["season"] == CURRENT_SEASON_LABEL
        for match in database.get_matches(league_id=1, db_path=db_path, limit=1000)
    )


def test_force_database_reset_rebuilds_complete_snapshot(tmp_path):
    db_path = tmp_path / "forced.db"
    data_sync.sync_current_season(db_path=db_path)
    conn = database.get_db_connection(db_path)
    conn.execute("DELETE FROM matches")
    conn.commit()
    conn.close()

    assert database.ensure_production_database(db_path, force=True) is True
    conn = database.get_db_connection(db_path)
    assert conn.execute("SELECT COUNT(*) FROM leagues").fetchone()[0] == 12
    assert conn.execute("SELECT COUNT(*) FROM matches").fetchone()[0] == 6690
    assert conn.execute(
        "SELECT COUNT(*) FROM matches WHERE season != ?",
        (CURRENT_SEASON_LABEL,),
    ).fetchone()[0] == 0
    conn.close()
