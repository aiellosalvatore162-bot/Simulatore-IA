from streamlit_app import parse_team_paste


def test_parse_team_paste_accepts_case_accents_and_dash_separators():
    parsed = parse_team_paste(
        """
        CASA -
        Nome - Inter
        Fattore-CORNERS - 1,25
        Forma-recente - W-D-W-L-W

        OSPITE:
        Squadra - Milan
        Calci d'angolo: 8
        Fattore CARTELLINI = 1,10
        """
    )

    assert parsed["home_name"] == "Inter"
    assert parsed["home_corners_factor"] == 1.25
    assert parsed["home_recent_form"] == "W-D-W-L-W"
    assert parsed["away_name"] == "Milan"
    assert parsed["away_corners_factor"] == 8.0
    assert parsed["away_cards_factor"] == 1.1


def test_parse_team_paste_logs_unmatched_lines(capsys):
    parsed = parse_team_paste(
        """
        CASA:
        Etichetta inesistente: 42
        Attacco senza valore:
        """
    )

    captured = capsys.readouterr()
    assert "etichetta non riconosciuta" in captured.err
    assert "chiave o valore vuoto" in captured.err
    assert "home_attack" not in parsed
