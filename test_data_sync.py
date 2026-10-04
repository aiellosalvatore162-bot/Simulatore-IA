import data_sync
import database


def test_sync_populates_complete_local_snapshot(tmp_path):
    result = data_sync.sync_current_season(
        season=2026,
        db_path=tmp_path / "sync.db",
        competition_codes=["SA"],
    )

    assert result["season"] == 2026
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


def test_sync_rebuilds_all_competitions_from_local_seed(tmp_path):
    result = data_sync.sync_current_season(
        season=2026,
        db_path=tmp_path / "offline.db",
        competition_codes=["SA", "PL"],
    )

    assert result["season"] == 2026
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
        "Ligue 1": 132,
        "La Liga": 132,
        "Campionato Portoghese": 56,
        "Bundesliga": 90,
        "Eredivisie": 56,
        "Champions League": 56,
    }
    leagues = {row["name"]: row["id"] for row in database.get_all_leagues(tmp_path / "all.db")}
    assert set(expected).issubset(leagues)
    for name, expected_matches in expected.items():
        assert len(database.get_matches(leagues[name], db_path=tmp_path / "all.db", limit=1000)) == expected_matches
