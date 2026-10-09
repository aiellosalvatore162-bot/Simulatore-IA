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
