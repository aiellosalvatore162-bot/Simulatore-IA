from parser import MatchInputError, parse_match_input


VALID = """CASA: Inter
Attacco: 1,34 | Difesa: 0.78 | Elo: 1835 | Forma: W-W-D-W-W | xG Fatti: 2.15 | xG Subiti: 0.85 | Corner pro/sub: 1.25/0.95 | Cartellini pro: 0.95

OSPITE: Milan
Attacco: 1.22 | Difesa: 0.92 | Elo: 1765 | Forma: W-W-L-D-W | xG Fatti: 1.85 | xG Subiti: 1.10 | Corner pro/sub: 1.15/1.10 | Cartellini pro: 1.10

ARBITRO: Gialli medi 4.5 | Falli medi 24
"""


def test_parser_preserves_values_and_decimal_comma():
    match = parse_match_input(VALID)
    assert match.home.attack == 1.34
    assert match.away.elo == 1765.0
    assert match.home.corners_against == 0.95
    assert match.warnings == ()


def test_parser_reports_secondary_fallbacks():
    text = VALID.replace(" | Corner pro/sub: 1.25/0.95 | Cartellini pro: 0.95", "")
    match = parse_match_input(text)
    assert match.home.corners_for == 1.0
    assert len(match.warnings) == 2


def test_parser_rejects_missing_required_field():
    try:
        parse_match_input(VALID.replace("xG Fatti: 2.15 | ", ""))
    except MatchInputError as error:
        assert "xG Fatti" in str(error)
    else:
        raise AssertionError("Missing required data must fail explicitly")


def test_parser_reads_optional_bookmaker_quotes_from_team_headers():
    text = VALID.replace(
        "CASA: Inter",
        "CASA: Inter | Quota 1: 1,85 | Quota Over 2.5: 2.10",
    ).replace(
        "OSPITE: Milan",
        "OSPITE: Milan | Quota X: 3.40 | Quota 2: 4.20",
    )
    match = parse_match_input(text)
    assert match.odds == {"1": 1.85, "Over 2.5 gol": 2.10, "X": 3.40, "2": 4.20}


def test_parser_rejects_invalid_duplicate_and_unknown_quotes_with_warnings():
    text = VALID.replace(
        "CASA: Inter",
        "CASA: Inter | Quota 1: 1.85 | Quota 1: 1.90 | Quota Casa Over 1.5: 2.00 | Quota Sconosciuta: 5.00 | Quota X: 1.00",
    )
    match = parse_match_input(text)
    assert match.odds == {"1": 1.85, "Casa Over 1.5 gol": 2.00}
    assert any("duplicata" in warning for warning in match.warnings)
    assert any("non supportato" in warning for warning in match.warnings)
    assert any("maggiore di 1.0" in warning for warning in match.warnings)


def test_parser_isolates_repeated_team_headers_and_reads_quote_sections():
    text = VALID.replace("CASA: Inter", "CASA: InterCASA: Genoa").replace(
        "ARBITRO: Gialli medi 4.5 | Falli medi 24",
        """ARBITRO: Gialli medi 4.5 | Falli medi 24

QUOTE_MERCATI_PRINCIPALI:
Quota 1: 1.85 | DNB Casa: 1.70 | Over 2.5: 2.10

QUOTE_MULTIGOL_TOTALI_E_SQUADRA:
Multigol Totale 1-3: 1.55 | Multigol Casa 1-2: 1.80 | Multigol Ospite 1-2: 1.90

QUOTE_SOMMA_GOL:
Somma gol 0: 4.00 | Somma gol 5+: 8.00

QUOTE_CORNER_E_CARTELLINI:
Over 8.5 corner: 1.90 | 1 corner: 2.00 | Under 4.5 cartellini: 1.80

QUOTE_COMBO:
1 + Over 1.5: 2.50""",
    )
    match = parse_match_input(text)

    assert match.home.name == "Inter"
    assert match.away.name == "Milan"
    assert match.odds == {
        "1": 1.85,
        "Casa DNB": 1.70,
        "Over 2.5 gol": 2.10,
        "Multigol 1-3": 1.55,
        "Multigol Casa 1-2": 1.80,
        "Multigol Ospite 1-2": 1.90,
        "Somma gol 0": 4.00,
        "Somma gol 5+": 8.00,
        "Over 8.5 corner": 1.90,
        "1 corner": 2.00,
        "Under 4.5 cartellini": 1.80,
        "1 + Over 1.5": 2.50,
    }


def test_parser_reads_unprefixed_quotes_with_multiple_separators():
    text = VALID.replace(
        "ARBITRO: Gialli medi 4.5 | Falli medi 24",
        "ARBITRO: Gialli medi 4.5 | Falli medi 24\n"
        "Quota Multigol Totale 1-2 2.10 | Quota Multigol Casa 1-2: 1.80 | "
        "Quota Somma Gol 0 - 4.00 | Quota Over 8.5 Corner 1.90 | "
        "Quota 1 + Over 1.5 2.50\n"
        "Over 2.5 - 2.10 | DNB Casa 1.70",
    )
    match = parse_match_input(text)

    assert match.odds["Multigol 1-2"] == 2.10
    assert match.odds["Multigol Casa 1-2"] == 1.80
    assert match.odds["Somma gol 0"] == 4.00
    assert match.odds["Over 8.5 corner"] == 1.90
    assert match.odds["1 + Over 1.5"] == 2.50
    assert match.odds["Over 2.5 gol"] == 2.10
    assert match.odds["Casa DNB"] == 1.70
