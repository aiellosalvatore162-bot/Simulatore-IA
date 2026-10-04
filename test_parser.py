import pytest
from streamlit_app import PasteParseError, parse_team_paste


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
    with pytest.raises(PasteParseError) as error:
        parse_team_paste(
            """
            CASA:
            Etichetta inesistente: 42
            Attacco senza valore:
            """
        )

    captured = capsys.readouterr()
    assert "etichetta non riconosciuta" in captured.err
    assert "chiave o valore vuoto" in captured.err
    assert len(error.value.issues) == 2


def test_parse_team_paste_maps_advanced_and_referee_fields():
    parsed = parse_team_paste(
        """
        CASA:
        Momentum recente: 8,5
        Impatto assenze chiave %: 35%
        Motivazione / obiettivo: Lotta Scudetto e qualificazione Europa
        PROFILO ARBITRALE:
        Gialli arbitro: 6,2
        Rossi medi: 0,35
        Falli arbitro: 31
        """
    )

    assert parsed["home_momentum"] == 8.5
    assert parsed["home_absence_impact"] == 0.35
    assert "Scudetto" in parsed["home_stakes"]
    assert parsed["referee_yellow_avg"] == 6.2
    assert parsed["referee_red_avg"] == 0.35
    assert parsed["referee_fouls_avg"] == 31.0
