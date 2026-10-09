"""Parser for the on-demand match input format.

The parser deliberately keeps user values as floats/strings and reports every
fallback. It never consults a database or invents team data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Optional


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


def _number(value: str, field_name: str) -> float:
    normalized = value.strip().replace(",", ".")
    try:
        return float(normalized)
    except ValueError as exc:
        raise MatchInputError(f"{field_name}: valore numerico non valido: {value!r}") from exc


def _section_lines(text: str) -> tuple[dict[str, str], dict[str, str], dict[str, str]]:
    sections: dict[str, dict[str, str]] = {"home": {}, "away": {}, "referee": {}}
    section: Optional[str] = None
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        upper = line.upper()
        if upper.startswith("CASA:"):
            sections["home"]["name"] = line.split(":", 1)[1].strip()
            section = "home"
            continue
        if upper.startswith("OSPITE:"):
            sections["away"]["name"] = line.split(":", 1)[1].strip()
            section = "away"
            continue
        if upper.startswith("ARBITRO:"):
            section = "referee"
            remainder = line.split(":", 1)[1].strip()
            if remainder:
                for item in remainder.split("|"):
                    match = _REF_LINE.match(item.strip())
                    if match:
                        sections["referee"][match.group("label").lower()] = match.group("value")
            continue
        if section in ("home", "away"):
            for item in line.split("|"):
                match = _TEAM_LINE.match(item.strip())
                if match:
                    sections[section][match.group("label").lower()] = match.group("value")
        elif section == "referee":
            for item in line.split("|"):
                match = _REF_LINE.match(item.strip())
                if match:
                    sections["referee"][match.group("label").lower()] = match.group("value")
    return sections["home"], sections["away"], sections["referee"]


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
    home_section, away_section, referee_section = _section_lines(text)
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

    return MatchInput(
        home=home,
        away=away,
        referee=ParsedReferee(yellow_avg=yellow, fouls_avg=fouls),
        warnings=tuple(warnings),
    )
