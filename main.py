"""
FastAPI Web App per la Simulazione di Pronostici Calcistici (Stagione 2026/2027)
Espone:
- Endpoint di simulazione Monte Carlo con correzione Dixon-Coles su 50.000 iterazioni
  integrato direttamente con i parametri delle squadre salvati nel database SQLite (data.db).
- Endpoint REST per consultazione leghe, squadre, classifiche, marcatori e calendario match.
- Endpoint per concludere i match con ricalcolo automatico di classifiche, Elo e forma recente.
"""

from pathlib import Path
import time
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException, Query, Path as FPath
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import database
import data_sync
from engine import MatchConfig, TeamParams, simulate_match
import updater

app = FastAPI(
    title="Football Predictor API 2026/2027 - Monte Carlo Dixon-Coles",
    description="Motore di simulazione calcistica vettorializzato su 50.000 iterazioni con SQLite, 12 competizioni, classifica automatica ed Elo dinamico.",
    version="2.0.0",
)

# Configurazione CORS per consentire l'accesso da qualsiasi frontend web
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount della cartella static per file frontend (CSS, JS, assets)
STATIC_DIR = Path(__file__).resolve().parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# --- MODELLI PYDANTIC ---

class TeamInput(BaseModel):
    name: Optional[str] = Field(None, description="Nome della squadra", examples=["Inter"])
    attack: Optional[float] = Field(None, description="Forza offensiva (1.0 = media)", ge=0.2, le=3.0, examples=[1.34])
    defense: Optional[float] = Field(None, description="Indice difensivo / gol subiti (1.0 = media, <1.0 solido)", ge=0.2, le=3.0, examples=[0.78])
    elo: Optional[float] = Field(None, description="Rating Elo della squadra", ge=800.0, le=2400.0, examples=[1835.0])
    cards_factor: Optional[float] = Field(None, description="Fattore propensione cartellini", ge=0.2, le=2.5, examples=[0.95])
    corners_factor: Optional[float] = Field(None, description="Fattore propensione corner", ge=0.2, le=2.5, examples=[1.25])
    recent_form: Optional[str] = Field(None, description="Forma recente W-D-L, ultime cinque partite", examples=["W-D-W-D-L"])
    xg_for: Optional[float] = Field(None, description="xG medi fatti inseriti dall'utente", ge=0.0, le=10.0)
    xg_against: Optional[float] = Field(None, description="xG medi subiti inseriti dall'utente", ge=0.0, le=10.0)


class SimulationPayload(BaseModel):
    match_id: Optional[int] = Field(None, description="ID del match in calendario da simulare (preleva automaticamente le due squadre)")
    home_team_id: Optional[int] = Field(None, description="ID squadra di casa nel database")
    away_team_id: Optional[int] = Field(None, description="ID squadra ospite nel database")
    home_team: Optional[TeamInput] = Field(None, description="Override parametri o squadra personalizzata")
    away_team: Optional[TeamInput] = Field(None, description="Override parametri o squadra personalizzata")
    home_advantage: Optional[float] = Field(1.15, description="Fattore vantaggio casalingo", ge=1.0, le=1.5)
    base_goals_home: float = Field(1.38, description="Media gol base casa", ge=0.5, le=3.0)
    base_goals_away: float = Field(1.12, description="Media gol base trasferta", ge=0.5, le=3.0)
    dixon_coles_rho: float = Field(-0.11, description="Parametro di correlazione Dixon-Coles", ge=-0.35, le=0.35)
    n_simulations: int = Field(50_000, description="Numero esatto di simulazioni Monte Carlo", ge=1000, le=100_000)
    seed: Optional[int] = Field(None, description="Seed opzionale per riproducibilità")
    auto_save_history: bool = Field(False, description="Salva automaticamente la simulazione nello storico")
    custom_odds: Optional[Dict[str, float]] = Field(None, description="Quote reali inserite dall'utente; {} esegue la simulazione senza Value Bet")
    require_xg: bool = Field(False, description="Richiede xG fatti e subiti per entrambe le squadre")


class SaveHistoryPayload(BaseModel):
    match_id: Optional[int] = Field(None, description="ID del match associato")
    home_team_name: str = Field(..., description="Nome squadra casa")
    away_team_name: str = Field(..., description="Nome squadra ospite")
    home_elo: float = Field(..., description="Elo squadra casa")
    away_elo: float = Field(..., description="Elo squadra ospite")
    simulations_count: int = Field(50_000, description="Numero simulazioni")
    execution_time_ms: float = Field(..., description="Tempo di calcolo in ms")
    best_convergence_market: Optional[str] = Field(None, description="Mercato a maggior convergenza")
    best_convergence_lift: Optional[float] = Field(None, description="Lift della convergenza")
    best_convergence_prob: Optional[float] = Field(None, description="Probabilità % della convergenza")
    best_value_bet_market: Optional[str] = Field(None, description="Mercato consigliato come Value Bet")
    best_value_bet_odds: Optional[float] = Field(None, description="Quota bookmaker del Value Bet")
    best_value_bet_ev: Optional[float] = Field(None, description="Expected Value (%) del Value Bet")
    assistant_narrative: Optional[str] = Field(None, description="Sintesi narrativa generata dall'assistente")
    full_results_json: Optional[str] = Field("{}", description="Snapshot JSON completo dei risultati")


class CompleteMatchPayload(BaseModel):
    home_goals: int = Field(..., ge=0, le=20, description="Gol segnati dalla squadra di casa")
    away_goals: int = Field(..., ge=0, le=20, description="Gol segnati dalla squadra ospite")
    home_xg: Optional[float] = Field(None, ge=0.0, le=15.0, description="xG squadra di casa (opzionale)")
    away_xg: Optional[float] = Field(None, ge=0.0, le=15.0, description="xG squadra ospite (opzionale)")


# --- ENDPOINTS GENERALI & HEALTH ---

@app.get("/")
def read_root():
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return {
        "status": "online",
        "service": "Football Match Predictor Engine 2026/2027",
        "version": "2.0.0",
        "documentation": "/docs",
    }


@app.get("/api/info")
def get_api_info():
    return {
        "status": "online",
        "service": "Football Match Predictor Engine 2026/2027",
        "version": "2.0.0",
        "documentation": "/docs",
        "simulate_endpoint": "/api/simulate",
        "endpoints": {
            "leagues": "/api/leagues",
            "matches": "/api/matches",
            "standings": "/api/leagues/{league_id}/standings",
            "top_scorers": "/api/leagues/{league_id}/top-scorers"
        }
    }


@app.get("/api/health")
def health_check():
    return {"status": "healthy", "timestamp": time.time(), "database_connected": Path(database.DB_FILE).exists()}


@app.post("/api/sync")
def sync_data_endpoint(season: Optional[int] = Query(None, ge=2000, le=2100)):
    """Sincronizza calendario, risultati, classifiche e marcatori da football-data.org."""
    try:
        return data_sync.sync_current_season(season=season)
    except data_sync.FootballDataError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


# --- ENDPOINTS CONSULTAZIONE DATABASE ---

@app.get("/api/leagues")
def get_leagues():
    """Restituisce l'elenco di tutte le 12 competizioni supportate nella stagione 2026/2027."""
    return database.get_all_leagues()


@app.get("/api/leagues/{league_id}")
def get_league(league_id: int = FPath(..., description="ID del campionato")):
    league = database.get_league_by_id(league_id)
    if not league:
        raise HTTPException(status_code=404, detail="Campionato non trovato.")
    return league


@app.get("/api/leagues/{league_id}/teams")
def get_teams(league_id: int = FPath(..., description="ID del campionato")):
    """Restituisce le squadre del campionato con rating Elo, attacco, difesa, forma e medie xG."""
    return database.get_teams_by_league(league_id)


@app.get("/api/leagues/{league_id}/standings")
def get_standings(league_id: int = FPath(..., description="ID del campionato")):
    """Restituisce la classifica aggiornata (punti, vinte, pareggiate, perse, gf, gs, dr)."""
    return database.get_standings_by_league(league_id)


@app.get("/api/leagues/{league_id}/top-scorers")
def get_top_scorers(
    league_id: int = FPath(..., description="ID del campionato"),
    limit: int = Query(15, ge=1, le=50)
):
    """Restituisce la classifica marcatori e assist del campionato."""
    return database.get_top_scorers_by_league(league_id, limit=limit)


@app.get("/api/matches")
def get_matches(
    league_id: Optional[int] = Query(None, description="Filtra per campionato"),
    status: Optional[str] = Query(None, description="Filtra per stato ('scheduled' o 'completed')"),
    matchday: Optional[str] = Query(None, description="Filtra per giornata"),
    limit: int = Query(50, ge=1, le=500)
):
    """Restituisce il calendario e risultati delle partite."""
    return database.get_matches(league_id=league_id, status=status, matchday=matchday, limit=limit)


@app.get("/api/matches/{match_id}")
def get_match_detail(match_id: int = FPath(..., description="ID del match")):
    match = database.get_match_by_id(match_id)
    if not match:
        raise HTTPException(status_code=404, detail="Match non trovato.")
    return match


# --- ENDPOINT AGGIORNAMENTO / CONCLUSIONE MATCH ---

@app.post("/api/matches/{match_id}/complete")
def complete_match_endpoint(
    match_id: int = FPath(..., description="ID del match da completare"),
    payload: CompleteMatchPayload = ...
):
    """
    Segna una partita come conclusa con risultato e xG.
    Innesca in tempo reale il ricalcolo di:
    - Classifica del campionato (Standings)
    - Forma recente delle squadre (W-D-L)
    - Rating Elo dinamico delle due squadre
    - Medie xG prodotti e concessi e coefficienti tattici
    """
    try:
        res = updater.complete_match(
            match_id=match_id,
            home_goals=payload.home_goals,
            away_goals=payload.away_goals,
            home_xg=payload.home_xg,
            away_xg=payload.away_xg
        )
        return {"message": "Match completato e statistiche ricalcolate con successo", "details": res}
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore durante l'aggiornamento: {str(e)}")


# --- ENDPOINTS STORICO SIMULAZIONI & H2H ---

@app.get("/api/history")
def get_history_endpoint(
    limit: int = Query(50, ge=1, le=200, description="Numero massimo di simulazioni da restituire"),
    offset: int = Query(0, ge=0, description="Offset paginazione")
):
    """Restituisce l'elenco cronologico delle simulazioni salvate nello storico."""
    return database.get_simulation_history(limit=limit, offset=offset)


@app.post("/api/history")
def save_history_endpoint(payload: SaveHistoryPayload):
    """Salva manualmente una simulazione completata nello storico."""
    try:
        h_id = database.save_simulation_history(
            match_id=payload.match_id,
            home_team_name=payload.home_team_name,
            away_team_name=payload.away_team_name,
            home_elo=payload.home_elo,
            away_elo=payload.away_elo,
            simulations_count=payload.simulations_count,
            execution_time_ms=payload.execution_time_ms,
            best_convergence_market=payload.best_convergence_market,
            best_convergence_lift=payload.best_convergence_lift,
            best_convergence_prob=payload.best_convergence_prob,
            best_value_bet_market=payload.best_value_bet_market,
            best_value_bet_odds=payload.best_value_bet_odds,
            best_value_bet_ev=payload.best_value_bet_ev,
            assistant_narrative=payload.assistant_narrative,
            full_results_json=payload.full_results_json or "{}",
        )
        return {"message": "Simulazione salvata con successo nello storico", "id": h_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore durante il salvataggio: {str(e)}")


@app.get("/api/history/{history_id}")
def get_history_detail_endpoint(history_id: int = FPath(..., description="ID della simulazione nello storico")):
    """Restituisce il dettaglio completo e lo snapshot JSON di una simulazione salvata."""
    item = database.get_simulation_history_by_id(history_id)
    if not item:
        raise HTTPException(status_code=404, detail="Simulazione non trovata nello storico.")
    return item


@app.delete("/api/history/{history_id}")
def delete_history_endpoint(history_id: int = FPath(..., description="ID della simulazione da eliminare")):
    """Elimina una simulazione dallo storico."""
    ok = database.delete_simulation_history(history_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Elemento non trovato nello storico.")
    return {"message": "Simulazione eliminata con successo", "id": history_id}


@app.get("/api/h2h")
def get_h2h_endpoint(
    home_team_id: Optional[int] = Query(None, description="ID squadra casa"),
    away_team_id: Optional[int] = Query(None, description="ID squadra ospite"),
    match_id: Optional[int] = Query(None, description="ID del match (in alternativa agli ID squadra)"),
    limit: int = Query(5, ge=1, le=20, description="Numero di precedenti diretti")
):
    """Restituisce gli ultimi precedenti diretti (H2H) con risultati, gol, segno 1X2 e bilancio."""
    if match_id:
        m = database.get_match_by_id(match_id)
        if not m:
            raise HTTPException(status_code=404, detail=f"Match con ID {match_id} non trovato.")
        home_team_id = m["home_team_id"]
        away_team_id = m["away_team_id"]

    if not home_team_id or not away_team_id:
        raise HTTPException(status_code=400, detail="Fornire home_team_id e away_team_id oppure match_id.")

    return database.get_h2h_matches(home_team_id, away_team_id, limit=limit)


# --- ENDPOINT DI SIMULAZIONE (MONTE CARLO 50.000 ITERAZIONI) ---

def _resolve_team_params(
    team_id: Optional[int],
    explicit_input: Optional[TeamInput],
    default_name: str,
    is_home: bool = True
) -> TeamParams:
    db_team = None
    if team_id is not None:
        db_team = database.get_team_by_id(team_id)
        if not db_team:
            raise HTTPException(status_code=404, detail=f"Squadra con ID {team_id} non trovata nel database.")
    elif explicit_input and explicit_input.name:
        db_team = database.get_team_by_name(explicit_input.name)

    name = default_name
    attack = 1.0
    defense = 1.0
    elo = 1500.0
    cards_factor = 1.0
    corners_factor = 1.0
    recent_form = "D-D-D-D-D"
    xg_for = None
    xg_against = None

    if db_team:
        name = db_team["name"]
        attack = db_team["attack"]
        defense = db_team["defense"]
        elo = db_team["elo"]
        cards_factor = db_team["cards_factor"]
        corners_factor = db_team["corners_factor"]
        recent_form = db_team["recent_form"]
        if "xg_source" in db_team.keys() and db_team["xg_source"] != "not_available":
            xg_for = db_team["xg_for"]
            xg_against = db_team["xg_against"]

    # Se l'utente ha fornito valori espliciti nel payload, essi hanno priorità (override)
    if explicit_input:
        if explicit_input.name is not None:
            name = explicit_input.name
        if explicit_input.attack is not None:
            attack = explicit_input.attack
        if explicit_input.defense is not None:
            defense = explicit_input.defense
        if explicit_input.elo is not None:
            elo = explicit_input.elo
        if explicit_input.cards_factor is not None:
            cards_factor = explicit_input.cards_factor
        if explicit_input.corners_factor is not None:
            corners_factor = explicit_input.corners_factor
        if explicit_input.recent_form is not None:
            recent_form = explicit_input.recent_form
        if explicit_input.xg_for is not None:
            xg_for = explicit_input.xg_for
        if explicit_input.xg_against is not None:
            xg_against = explicit_input.xg_against

    return TeamParams(
        name=name,
        attack=attack,
        defense=defense,
        elo=elo,
        cards_factor=cards_factor,
        corners_factor=corners_factor,
        recent_form=recent_form,
        xg_for=xg_for,
        xg_against=xg_against,
    )


@app.post("/api/simulate")
def run_simulation_post(payload: SimulationPayload) -> Dict[str, Any]:
    """
    Esegue 50.000 simulazioni Monte Carlo della partita con distribuzione bivariata Dixon-Coles.
    Integra automaticamente quote di mercato, Value Betting, sintesi narrativa AI e H2H storico.
    """
    try:
        h_id = payload.home_team_id
        a_id = payload.away_team_id

        # Se viene passato un match_id, risolviamo le squadre dal match
        if payload.match_id:
            m = database.get_match_by_id(payload.match_id)
            if not m:
                raise HTTPException(status_code=404, detail=f"Match ID {payload.match_id} non trovato.")
            h_id = m["home_team_id"]
            a_id = m["away_team_id"]

        home_params = _resolve_team_params(h_id, payload.home_team, default_name="Squadra Casa", is_home=True)
        away_params = _resolve_team_params(a_id, payload.away_team, default_name="Squadra Ospite", is_home=False)

        if payload.require_xg:
            missing_xg = []
            for label, team in (("casa", home_params), ("ospite", away_params)):
                if team.xg_for is None:
                    missing_xg.append(f"xG fatti {label}")
                if team.xg_against is None:
                    missing_xg.append(f"xG subiti {label}")
            if missing_xg:
                raise HTTPException(
                    status_code=422,
                    detail="Inserire tutti gli xG richiesti: " + ", ".join(missing_xg),
                )

        # Se home_advantage non specificato esplicitamente e la squadra è su DB, usa il suo home_advantage
        home_adv = payload.home_advantage or 1.15
        if h_id:
            h_db = database.get_team_by_id(h_id)
            if h_db and payload.home_advantage is None:
                home_adv = h_db["home_advantage"]

        config = MatchConfig(
            home_team=home_params,
            away_team=away_params,
            home_advantage=home_adv,
            base_goals_home=payload.base_goals_home,
            base_goals_away=payload.base_goals_away,
            dixon_coles_rho=payload.dixon_coles_rho,
            n_simulations=payload.n_simulations,
            seed=payload.seed,
        )
        result = simulate_match(config, custom_odds=payload.custom_odds)
        
        # Aggiungiamo riferimenti al database nei metadati
        result["metadata"]["database_source"] = {
            "match_id": payload.match_id,
            "home_team_id": h_id,
            "away_team_id": a_id,
            "home_team_name": home_params.name,
            "away_team_name": away_params.name,
            "home_team_elo": home_params.elo,
            "away_team_elo": away_params.elo,
        }

        # Aggiungiamo H2H storico se squadre identificate
        if h_id and a_id:
            result["h2h"] = database.get_h2h_matches(h_id, a_id, limit=5)
        else:
            result["h2h"] = {"matches": [], "summary": {"total_matches": 0, "team_a_wins": 0, "team_b_wins": 0, "draws": 0, "avg_goals": 0.0}}

        # Auto-salvataggio opzionale nello storico
        if payload.auto_save_history:
            import json
            conv = result.get("market_convergence", {})
            best_c = conv.get("best_synergy_market", {})
            vb = result.get("value_betting", {})
            best_vb = vb.get("best_value_bet", {})

            h_saved_id = database.save_simulation_history(
                match_id=payload.match_id,
                home_team_name=home_params.name,
                away_team_name=away_params.name,
                home_elo=home_params.elo,
                away_elo=away_params.elo,
                simulations_count=payload.n_simulations,
                execution_time_ms=result["metadata"]["execution_time_ms"],
                best_convergence_market=best_c.get("combo"),
                best_convergence_lift=best_c.get("lift"),
                best_convergence_prob=best_c.get("percentage"),
                best_value_bet_market=best_vb.get("market"),
                best_value_bet_odds=best_vb.get("odds"),
                best_value_bet_ev=best_vb.get("ev_pct"),
                assistant_narrative=result.get("ai_narrative"),
                full_results_json=json.dumps(result)
            )
            result["history_id"] = h_saved_id

        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore durante la simulazione: {str(e)}")


@app.get("/api/simulate")
def run_simulation_get(
    match_id: Optional[int] = Query(None, description="ID del match in calendario nel DB"),
    home_team_id: Optional[int] = Query(None, description="ID squadra casa nel DB"),
    away_team_id: Optional[int] = Query(None, description="ID squadra ospite nel DB"),
    home_name: Optional[str] = Query(None, description="Nome squadra casa (se non da DB)"),
    away_name: Optional[str] = Query(None, description="Nome squadra ospite (se non da DB)"),
    home_attack: Optional[float] = Query(None, ge=0.2, le=3.0),
    home_defense: Optional[float] = Query(None, ge=0.2, le=3.0),
    home_elo: Optional[float] = Query(None, ge=800.0, le=2400.0),
    away_attack: Optional[float] = Query(None, ge=0.2, le=3.0),
    away_defense: Optional[float] = Query(None, ge=0.2, le=3.0),
    away_elo: Optional[float] = Query(None, ge=800.0, le=2400.0),
    home_advantage: float = Query(1.15, ge=1.0, le=1.5),
    n_sims: int = Query(50_000, ge=1000, le=100_000),
    seed: Optional[int] = Query(None),
) -> Dict[str, Any]:
    """
    Versione GET di /api/simulate per test immediati:
    - Puoi passare solo `match_id` (es. `?match_id=12`)
    - O gli ID squadre (`?home_team_id=1&away_team_id=2`)
    - Oppure parametri manuali completi.
    """
    home_input = None
    if any(x is not None for x in (home_name, home_attack, home_defense, home_elo)):
        home_input = TeamInput(
            name=home_name,
            attack=home_attack,
            defense=home_defense,
            elo=home_elo,
        )

    away_input = None
    if any(x is not None for x in (away_name, away_attack, away_defense, away_elo)):
        away_input = TeamInput(
            name=away_name,
            attack=away_attack,
            defense=away_defense,
            elo=away_elo,
        )

    # Se non specificato alcun ID e nessun parametro manuale, impostiamo default Inter vs Milan dal DB
    if match_id is None and home_team_id is None and away_team_id is None and home_input is None and away_input is None:
        home_team_id = 1 # Inter
        away_team_id = 3 # Milan

    payload = SimulationPayload(
        match_id=match_id,
        home_team_id=home_team_id,
        away_team_id=away_team_id,
        home_team=home_input,
        away_team=away_input,
        home_advantage=home_advantage,
        n_simulations=n_sims,
        seed=seed,
    )
    return run_simulation_post(payload)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
