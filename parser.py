"""Parser for the on-demand match input format.

The parser deliberately keeps user values as floats/strings and reports every
fallback. It never consults a database or invents team data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Optional

from market_catalog import definition_for_event, event_keys, normalize_market_label

@dataclass(frozen=True)
class ParsedTeam:
    name: str
    attack: float
    defense: float
    elo: float
    form: str
    xg_for: float
    xg_against: float
    corners_for: float
    corners_against: float
    cards_for: float


@dataclass(frozen=True)
class ParsedReferee:
    yellow_avg: float
    fouls_avg: float


@dataclass(frozen=True)
class MatchInput:
    home: ParsedTeam
    away: ParsedTeam
    referee: ParsedReferee
    odds: dict[str, float] = field(default_factory=dict)
    warnings: tuple[str, ...] = field(default_factory=tuple)


class MatchInputError(ValueError):
    """Raised when required input cannot be parsed."""


_NUMBER = r"[-+]?(?:\d+(?:[.,]\d+)?|[.,]\d+)"
_TEAM_LINE = re.compile(
    rf"^(?P<label>Attacco|Difesa|Elo|Forma|xG\s+Fatti|xG\s+Subiti|"
    rf"Corner\s+pro/sub|Cartellini\s+pro)\s*:\s*(?P<value>.+?)\s*$",
    re.IGNORECASE,
)
_REF_LINE = re.compile(
    rf"^(?P<label>Gialli\s+medi|Falli\s+medi)\s+(?P<value>{_NUMBER})\s*$",
    re.IGNORECASE,
)
_ODDS_LINE = re.compile(
    rf"^(?:Quota\s+)?(?P<label>.+?)(?:\s*:\s*|\s+[-–—]\s+|\s+)(?P<value>{_NUMBER})\s*$",
    re.IGNORECASE,
)
_MATCH_HEADER = re.compile(r"(?P<label>CASA|OSPITE|ARBITRO)\s*:", re.IGNORECASE)
_QUOTE_SECTION = re.compile(
    r"^\s*(?:#+\s*)?(?:QUOTE_MERCATI_PRINCIPALI|"
    r"QUOTE_MULTIGOL_TOTALI_E_SQUADRA|QUOTE_SOMMA_GOL|"
    r"QUOTE_CORNER_E_CARTELLINI|QUOTE_COMBO)\s*:?\s*$",
    re.IGNORECASE,
)
def _normalize_quote_label(label: str) -> str:
    normalized = re.sub(r"\s+", " ", label.strip().replace("_", " "))
    normalized = re.sub(r"^quota\s+", "", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"\bcorner\b", "corner", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"\bcartellini\b", "cartellini", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"\bgol\b", "gol", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"^DNB\s+(Casa|Ospite)$", r"\1 DNB", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"^Multigol\s+(?:Totale|Totali)\s+", "Multigol ", normalized, flags=re.IGNORECASE)
    normalized = normalize_market_label(normalized)
    for event_key in event_keys():
        if event_key.casefold() == normalized.casefold():
            return event_key
    return normalized


def _collect_odds(item: str, *, allow_unprefixed: bool = False) -> tuple[str, str] | None:
    match = _ODDS_LINE.match(item.strip())
    if not match:
        return None
    explicit = item.strip().lower().startswith("quota ")
    key = _normalize_quote_label(match.group("label"))
    if not explicit and not allow_unprefixed:
        return None
    if not explicit and key not in event_keys():
        return None
    return key, match.group("value")


def _number(value: str, field_name: str) -> float:
    normalized = value.strip().replace(",", ".")
    try:
        return float(normalized)
    except ValueError as exc:
        raise MatchInputError(f"{field_name}: valore numerico non valido: {value!r}") from exc


def _section_lines(text: str) -> tuple[dict[str, str], dict[str, str], dict[str, str], list[tuple[str, str]]]:
    sections: dict[str, dict[str, str]] = {"home": {}, "away": {}, "referee": {}}
    odds: list[tuple[str, str]] = []
    section: Optional[str] = None
    quote_section = False

    def process_content(content: str, current_section: Optional[str], *, allow_unprefixed_odds: bool) -> None:
        if current_section in ("home", "away"):
            parts = [part.strip() for part in content.split("|")]
            for item in parts:
                quote = _collect_odds(item, allow_unprefixed=allow_unprefixed_odds)
                if quote:
                    odds.append(quote)
                    continue
                match = _TEAM_LINE.match(item)
                if match:
                    sections[current_section][match.group("label").lower()] = match.group("value")
        elif current_section == "referee":
            for item in content.split("|"):
                quote = _collect_odds(item, allow_unprefixed=allow_unprefixed_odds)
                if quote:
                    odds.append(quote)
                    continue
                match = _REF_LINE.match(item.strip())
                if match:
                    sections["referee"][match.group("label").lower()] = match.group("value")
        elif allow_unprefixed_odds:
            for item in content.split("|"):
                quote = _collect_odds(item, allow_unprefixed=True)
                if quote:
                    odds.append(quote)

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if _QUOTE_SECTION.match(line):
            quote_section = True
            section = None
            continue
        if quote_section and not re.match(r"^(?:CASA|OSPITE|ARBITRO)\s*:", line, re.IGNORECASE):
            process_content(line, None, allow_unprefixed_odds=True)
            continue
        headers = list(_MATCH_HEADER.finditer(line))
        if headers and headers[0].start() != 0:
            headers = []
        if headers:
            quote_section = False
            for index, header in enumerate(headers):
                content_end = headers[index + 1].start() if index + 1 < len(headers) else len(line)
                content = line[header.end():content_end].strip(" |")
                section = {"casa": "home", "ospite": "away", "arbitro": "referee"}[header.group("label").lower()]
                if section in ("home", "away"):
                    name = content.split("|", 1)[0].strip()
                    if name and "name" not in sections[section]:
                        sections[section]["name"] = name
                process_content(content, section, allow_unprefixed_odds=False)
            continue
        process_content(line, section, allow_unprefixed_odds=True)
    return sections["home"], sections["away"], sections["referee"], odds


def _team(section: dict[str, str], label: str, warnings: list[str]) -> ParsedTeam:
    required = {
        "name": "Nome",
        "attacco": "Attacco",
        "difesa": "Difesa",
        "elo": "Elo",
        "forma": "Forma",
        "xg fatti": "xG Fatti",
        "xg subiti": "xG Subiti",
    }
    missing = [name for key, name in required.items() if not section.get(key)]
    if missing:
        raise MatchInputError(f"{label}: campi obbligatori mancanti: {', '.join(missing)}")

    values = {
        key: _number(section[key], f"{label} {name}")
        for key, name in required.items()
        if key != "name" and key != "forma"
    }
    form = section["forma"].strip().upper().replace(" ", "")
    if not re.fullmatch(r"[WDL](?:-[WDL]){0,4}", form):
        raise MatchInputError(f"{label} Forma: usare token W-D-L, massimo cinque risultati")

    corners = section.get("corner pro/sub")
    if corners:
        parts = re.split(r"\s*/\s*", corners)
        if len(parts) != 2:
            raise MatchInputError(f"{label} Corner pro/sub: usare il formato valore/valore")
        corners_for, corners_against = (
            _number(parts[0], f"{label} Corner pro"),
            _number(parts[1], f"{label} Corner sub"),
        )
    else:
        corners_for = corners_against = 1.0
        warnings.append(f"{label}: Corner pro/sub mancante, fallback neutro 1.0/1.0")

    cards = section.get("cartellini pro")
    if cards:
        cards_for = _number(cards, f"{label} Cartellini pro")
    else:
        cards_for = 1.0
        warnings.append(f"{label}: Cartellini pro mancante, fallback neutro 1.0")

    return ParsedTeam(
        name=section["name"],
        attack=values["attacco"],
        defense=values["difesa"],
        elo=values["elo"],
        form=form,
        xg_for=values["xg fatti"],
        xg_against=values["xg subiti"],
        corners_for=corners_for,
        corners_against=corners_against,
        cards_for=cards_for,
    )


def parse_match_input(text: str) -> MatchInput:
    """Parse one complete match block and return explicit fallback warnings."""
    home_section, away_section, referee_section, raw_odds = _section_lines(text)
    warnings: list[str] = []
    home = _team(home_section, "CASA", warnings)
    away = _team(away_section, "OSPITE", warnings)

    yellow_raw = referee_section.get("gialli medi")
    fouls_raw = referee_section.get("falli medi")
    if yellow_raw is None:
        yellow = 4.5
        warnings.append("ARBITRO: Gialli medi mancante, fallback neutro 4.5")
    else:
        yellow = _number(yellow_raw, "ARBITRO Gialli medi")
    if fouls_raw is None:
        fouls = 24.0
        warnings.append("ARBITRO: Falli medi mancante, fallback neutro 24.0")
    else:
        fouls = _number(fouls_raw, "ARBITRO Falli medi")

    odds: dict[str, float] = {}
    for market, raw_value in raw_odds:
        if definition_for_event(market) is None:
            warnings.append(f"Quota {market}: mercato non supportato, quota scartata")
            continue
        value = _number(raw_value, f"Quota {market}")
        if value <= 1.0:
            warnings.append(f"Quota {market}: deve essere maggiore di 1.0, quota scartata")
            continue
        if market in odds:
            warnings.append(f"Quota {market}: duplicata, mantenuta la prima quota")
            continue
        odds[market] = value

    return MatchInput(
        home=home,
        away=away,
        referee=ParsedReferee(yellow_avg=yellow, fouls_avg=fouls),
        odds=odds,
        warnings=tuple(warnings),
    )
