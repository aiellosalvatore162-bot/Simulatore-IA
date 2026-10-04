"""Sincronizzazione locale deterministica per la stagione 2026/2027.

Il recupero online e' stato rimosso: i provider esterni restituivano
stagioni incoerenti o calendari incompleti. Il seed locale genera invece uno
snapshot completo e ripetibile per tutte le competizioni supportate.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from database import DB_FILE

CURRENT_SEASON = 2026
DEFAULT_SEASON = CURRENT_SEASON

COMPETITIONS = {
    "SA": "Serie A",
    "PL": "Premier League",
    "FL1": "Ligue 1",
    "PD": "La Liga",
    "PPL": "Campionato Portoghese",
    "BL1": "Bundesliga",
    "DED": "Eredivisie",
    "CL": "Champions League",
}


class FootballDataError(RuntimeError):
    """Errore leggibile della sincronizzazione locale."""

    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


def sync_current_season(
    season: Optional[int] = None,
    db_path: Optional[str | Path] = None,
    competition_codes: Optional[Iterable[str]] = None,
) -> Dict[str, Any]:
    """Ricrea lo snapshot locale completo della stagione 2026/2027.

    ``competition_codes`` limita soltanto l'elenco restituito: il seed viene
    sempre eseguito integralmente per mantenere coerenti classifiche,
    calendari, squadre e marcatori tra tutte le competizioni.
    """
    if season is not None and season != CURRENT_SEASON:
        raise FootballDataError(
            f"La sincronizzazione supporta esclusivamente la stagione {CURRENT_SEASON}/2027"
        )

    selected = list(competition_codes) if competition_codes is not None else list(COMPETITIONS)
    unknown = [code for code in selected if code not in COMPETITIONS]
    if unknown:
        raise FootballDataError(f"Codici competizione non supportati: {', '.join(unknown)}")

    os.environ["FOOTBALL_DATA_SEASON"] = str(CURRENT_SEASON)
    target_path = Path(db_path or DB_FILE)
    from seed import seed_database

    try:
        seed_database(target_path)
    except (OSError, RuntimeError) as exc:
        raise FootballDataError(
            f"Impossibile creare lo snapshot locale 2026/2027: {exc}"
        ) from exc

    synced = [
        {
            "code": code,
            "league": COMPETITIONS[code],
            "source": "local-seed",
            "season": CURRENT_SEASON,
        }
        for code in selected
    ]
    return {
        "season": CURRENT_SEASON,
        "source": "local-seed",
        "synced": synced,
        "errors": [],
    }


if __name__ == "__main__":
    print(json.dumps(sync_current_season(), ensure_ascii=False, indent=2))
