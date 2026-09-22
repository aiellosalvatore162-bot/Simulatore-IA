"""Interfaccia Streamlit standalone per il motore di simulazione calcistica."""

from datetime import datetime
from dataclasses import asdict
import json
import re
from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st
import database
from engine import MatchConfig, TeamParams, calculate_team_strength, simulate_match


st.set_page_config(
    page_title="Simulatore IA",
    page_icon="⚽",
    layout="wide",
)

st.markdown(
    """
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&display=swap');

        :root {
            --sim-bg-primary: #070d1e;
            --sim-bg-secondary: #0c1836;
            --sim-bg-card: rgba(16, 29, 66, 0.75);
            --sim-border: rgba(0, 240, 255, 0.12);
            --sim-border-hover: rgba(0, 240, 255, 0.45);
            --sim-azure: #00f0ff;
            --sim-blue: #0284c7;
            --sim-bright: #38bdf8;
            --sim-text: #f8fafc;
            --sim-muted: #94a3b8;
        }

        html, body, .stApp, [data-testid="stAppViewContainer"],
        [data-testid="stAppViewContainer"] > .main, [data-testid="stHeader"] {
            background: var(--sim-bg-primary) !important;
            color: var(--sim-text) !important;
            font-family: 'Outfit', sans-serif !important;
        }
        [data-testid="stAppViewContainer"] > .main {
            background-color: var(--sim-bg-primary) !important;
            background-image: radial-gradient(at 10% 20%, rgba(3, 64, 120, .35) 0, transparent 50%),
                radial-gradient(at 90% 80%, rgba(0, 240, 255, .15) 0, transparent 50%),
                radial-gradient(at 50% 50%, rgba(12, 24, 54, .5) 0, transparent 100%) !important;
            background-attachment: fixed !important;
        }
        [data-testid="stHeader"] { background: transparent !important; }
        .block-container { max-width: 1440px; min-height: 100vh; padding-top: 1.2rem; }
        [data-testid="stSidebar"] { display: none !important; }
        [data-testid="stToolbar"] { right: 1rem; }
        .stMarkdown, .stText, label, p, span, div { font-family: 'Outfit', sans-serif; }
        h1, h2, h3 { font-family: 'Outfit', sans-serif !important; color: var(--sim-text) !important; }
        .stButton > button {
            background: rgba(2, 132, 199, .20);
            color: var(--sim-azure);
            border: 1px solid rgba(0, 240, 255, .30);
            border-radius: 12px;
            font-family: 'Outfit', sans-serif;
            font-weight: 700;
            transition: all .2s ease;
        }
        .stButton > button:hover { background: rgba(2, 132, 199, .42); border-color: var(--sim-azure); box-shadow: 0 0 20px rgba(0, 240, 255, .25); }
        .stButton > button[kind="primary"] { background: linear-gradient(135deg, #0284c7 0%, #00f0ff 100%); color: #031326; border: 0; box-shadow: 0 0 15px rgba(0, 240, 255, .35); }
        [data-testid="stDataFrame"] { border: 1px solid var(--sim-border); border-radius: 12px; overflow: hidden; }
        [data-testid="stMetricValue"] { font-size: 1.55rem; }
        .hero { padding: 1.4rem 1.6rem; border: 1px solid #26364a; border-radius: 14px;
            background: var(--sim-bg-card); backdrop-filter: blur(12px); margin-bottom: 1.1rem; text-align: center;
            box-shadow: 0 8px 32px rgba(0, 0, 0, .37); }
        .hero h1 { margin: 0; letter-spacing: -0.03em; }
        .hero p { color: #a7bac7; margin: 0.35rem 0 0; }
        .match-header { text-align: center; padding: 1.35rem 1rem 1rem; border: 1px solid #26364a;
                border-radius: 16px; background: #101a27; margin: .8rem 0 .65rem; }
        .match-teams { display: flex; justify-content: center; align-items: center; gap: 2.5rem; }
        .team-name { color: #e8f0f4; font-size: 1.12rem; font-weight: 700; min-width: 150px; }
        .team-logo { width: 48px; height: 48px; object-fit: contain; vertical-align: middle; margin: 0 .4rem; }
        .predicted-score { color: #f4b942; font-size: 2.45rem; font-weight: 800; line-height: 1.1; }
        .confidence { margin-top: .8rem; color: #70e1c1; font-size: .82rem; font-weight: 800; letter-spacing: .08em; }
        .probability-bar { display: flex; height: 28px; border-radius: 8px; overflow: hidden; margin: .45rem 0 .25rem; }
        .prob-home { background: #26b99a; } .prob-draw { background: #718096; } .prob-away { background: #d66a5d; }
        .probability-labels { display: flex; justify-content: space-between; color: #9db0bc; font-size: .76rem; }
        .prop-card { border: 1px solid var(--sim-border); border-radius: 16px; background: var(--sim-bg-card); padding: .75rem .8rem; min-height: 78px; box-shadow: 0 8px 32px rgba(0, 0, 0, .25); }
        .prop-label { color: #9db0bc; font-size: .74rem; text-transform: uppercase; letter-spacing: .05em; }
        .prop-value { color: #f2f7f8; font-size: 1.25rem; font-weight: 750; margin-top: .28rem; }
        .league-card { border: 1px solid var(--sim-border); border-radius: 16px; background: var(--sim-bg-card);
            padding: .95rem; min-height: 96px; box-shadow: 0 8px 32px rgba(0,0,0,.37); }
        .matchday-caption { color: #a7bad4; font-size: .74rem; text-align: center; margin-top: .25rem; }
        .welcome-card { padding: 1.2rem 1.4rem; border: 1px solid var(--sim-border); border-radius: 16px;
            background: var(--sim-bg-card); backdrop-filter: blur(12px); margin-bottom: 1rem; box-shadow: 0 8px 32px rgba(0,0,0,.37); }
        .welcome-card h2 { margin: 0; color: #f3f7f8; }
        .welcome-card p { color: #a7bac7; margin: .35rem 0 0; }
        .main-nav { background: var(--sim-bg-card); border: 1px solid var(--sim-border); border-radius: 16px;
            padding: .55rem; margin: .7rem 0 1.2rem; backdrop-filter: blur(12px); box-shadow: 0 8px 32px rgba(0,0,0,.25); }
        .nav-caption { color: #8fa5c4; font-size: .72rem; text-align: center; margin-top: .25rem; }
    </style>
    """,
    unsafe_allow_html=True,
)


def _number(value: Any, default: float) -> float:
    """Converte un campo API incompleto senza propagare None nel motore."""
    try:
        number = float(value)
        return number if pd.notna(number) else default
    except (TypeError, ValueError):
        return default


def _optional_number(value: Any) -> Optional[float]:
    number = _number(value, float("nan"))
    return None if pd.isna(number) else number


def parse_team_paste(text: str) -> Dict[str, Any]:
    """Estrae campi squadra e avanzati da testo libero senza inventare valori."""
    parsed: Dict[str, Any] = {"bookmaker_odds": parse_bookmaker_odds(text)}
    section = "home"
    aliases = {
        "nome": "name", "squadra": "name", "nome casa": "home_name", "nome ospite": "away_name",
        "casa": "home_name", "home": "home_name", "ospite": "away_name", "away": "away_name",
        "attacco": "attack", "difesa": "defense", "elo": "elo", "forma": "recent_form",
        "forma recente": "recent_form", "fattore cartellini": "cards_factor", "cartellini": "cards_factor",
        "fattore corner": "corners_factor", "corner": "corners_factor", "xg fatti": "xg_for",
        "xg subiti": "xg_against", "xg fatti casa": "home_xg_for", "xg subiti casa": "home_xg_against",
        "xg fatti ospite": "away_xg_for", "xg subiti ospite": "away_xg_against",
        "momentum recente": "momentum", "impatto assenze": "absence", "assenze": "absence",
        "motivazione": "stakes", "obiettivo": "stakes", "motivazione obiettivo": "stakes", "gialli medi": "referee_yellow_avg",
        "rossi medi": "referee_red_avg", "falli medi": "referee_fouls_avg",
    }
    numeric_fields = {
        "attack", "defense", "elo", "cards_factor", "corners_factor", "xg_for", "xg_against",
        "home_xg_for", "home_xg_against", "away_xg_for", "away_xg_against", "momentum",
        "absence", "referee_yellow_avg", "referee_red_avg", "referee_fouls_avg",
    }
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        section_match = re.match(r"^(?:\[?\s*)?(casa|home|ospite|away)(?:\s*\]?)\s*:?\s*$", line, re.I)
        if section_match:
            section = "home" if section_match.group(1).lower() in {"casa", "home"} else "away"
            continue
        match = re.match(r"^\s*([^:=\-]+?)\s*[:=\-]\s*(.*?)\s*$", line)
        if not match:
            continue
        raw_key, raw_value = match.groups()
        key = re.sub(r"\s+", " ", raw_key.lower().replace("_", " ").replace("/", " ").replace("%", "").strip())
        field = aliases.get(key)
        if field is None:
            continue
        if field in {"home_name", "away_name"}:
            parsed[field] = raw_value.strip()
            section = "home" if field == "home_name" else "away"
            continue
        if field == "name":
            parsed[f"{section}_name"] = raw_value.strip()
            continue
        if field == "recent_form" or field == "stakes":
            parsed[f"{section}_{field}"] = raw_value.strip()
            continue
        value_text = raw_value.replace(",", ".")
        if field in numeric_fields:
            number_match = re.search(r"-?\d+(?:\.\d+)?", value_text)
            if not number_match:
                continue
            number = float(number_match.group())
            if field == "absence" and "%" in raw_value:
                number /= 100.0
            if field == "absence":
                parsed[f"{section}_absence_impact"] = number
            elif field == "momentum":
                parsed[f"{section}_momentum"] = number
            elif field.startswith("referee_"):
                parsed[field] = number
            else:
                parsed[f"{section}_{field}"] = number
    return parsed


def parse_bookmaker_odds(text: str) -> Dict[str, float]:
    """Legge quote bookmaker in formato libero e restituisce categoria:selezione."""
    odds: Dict[str, float] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        lowered = line.lower().replace(",", ".")
        number_matches = list(re.finditer(r"(?<![\d.])\d+(?:\.\d+)?", lowered))
        if not number_matches:
            continue
        quote_match = number_matches[-1]
        quote = float(quote_match.group())
        if quote <= 1.0:
            continue
        before_quote = lowered[:quote_match.start()]
        category = None
        selection = None
        if "1x2" in before_quote:
            category = "1x2_primo_tempo" if "primo" in before_quote or "1t" in before_quote else "1x2_finale"
            selection_match = re.search(r"(?:^|[:=@\s])([12x])\s*(?:[@:=]|$)", before_quote)
            selection = selection_match.group(1).upper() if selection_match else None
        elif "goal" in before_quote or "no goal" in before_quote:
            category = "goal_nogoal_primo_tempo" if "primo" in before_quote or "1t" in before_quote else "goal_nogoal_finale"
            selection = "No_Goal" if "no goal" in before_quote else "Goal"
        elif "over" in before_quote or "under" in before_quote:
            side = "finale"
            if "primo" in before_quote or "1t" in before_quote:
                side = "primo_tempo"
            elif "casa" in before_quote:
                side = "squadra_casa"
            elif "ospite" in before_quote or "trasferta" in before_quote:
                side = "squadra_ospite"
            if "cartell" in before_quote:
                category = "cartellini"
            elif "corner" in before_quote:
                category = "calci_dangolo"
            elif "fall" in before_quote:
                category = "falli"
            elif side == "finale":
                category = "over_under_finale"
            elif side == "primo_tempo":
                category = "over_under_primo_tempo"
            else:
                category = f"over_under_{side}"
            market_match = re.search(
                r"\b(over|under)(?:\s+(?:finale|primo\s+tempo|casa|ospite|trasferta|cartellini|corner|angoli|falli))*\s*(\d+(?:\.\d+)?)",
                before_quote,
            )
            selection = f"{market_match.group(1).capitalize()}_{market_match.group(2)}" if market_match else None
        elif "multigol" in before_quote or "multi gol" in before_quote:
            if "tempi" in before_quote or "1t" in before_quote or "2t" in before_quote:
                category = "multigol_primo_tempo_combo_secondo_tempo"
                ranges = re.findall(r"\d+\s*[-/]\s*\d+", before_quote)
                if len(ranges) >= 2:
                    first_range = re.sub(r"\s*[-/]\s*", "_", ranges[0])
                    second_range = re.sub(r"\s*[-/]\s*", "_", ranges[1])
                    selection = f"1T_{first_range}_e_2T_{second_range}"
            elif "casa + ospite" in before_quote or "casa e ospite" in before_quote:
                category = "multigol_casa_combo_ospite"
                ranges = re.findall(r"\d+\s*[-/]\s*\d+", before_quote)
                if len(ranges) >= 2:
                    first_range = re.sub(r"\s*[-/]\s*", "_", ranges[0])
                    second_range = re.sub(r"\s*[-/]\s*", "_", ranges[1])
                    selection = f"Casa_{first_range}_e_Ospite_{second_range}"
            else:
                category = "multigol_casa" if "casa" in before_quote else "multigol_ospite" if "ospite" in before_quote else "multigol_partita"
                range_match = re.search(r"(\d+)\s*[-/]\s*(\d+)", before_quote)
                selection = f"{range_match.group(1)}_{range_match.group(2)}" if range_match else None
        if category and selection:
            odds[f"{category}:{selection}"] = quote
    return odds


def apply_pasted_values(parsed: Dict[str, Any], widget_prefix: str) -> None:
    """Aggiorna soltanto le chiavi riconosciute; gli altri input restano intatti."""
    team_fields = ("name", "attack", "defense", "elo", "cards_factor", "corners_factor", "xg_for", "xg_against", "recent_form")
    for side in ("home", "away"):
        for field in team_fields:
            key = f"{side}_{field}"
            if key in parsed:
                st.session_state[f"{widget_prefix}_{side}_{field if field != 'cards_factor' else 'cards'}"] = parsed[key]
    advanced_keys = {
        "home_momentum": f"{widget_prefix}_home_momentum", "away_momentum": f"{widget_prefix}_away_momentum",
        "home_absence_impact": f"{widget_prefix}_home_absence", "away_absence_impact": f"{widget_prefix}_away_absence",
        "referee_yellow_avg": f"{widget_prefix}_ref_yellows", "referee_red_avg": f"{widget_prefix}_ref_reds",
        "referee_fouls_avg": f"{widget_prefix}_ref_fouls",
    }
    for field, widget_key in advanced_keys.items():
        if field in parsed:
            value = parsed[field]
            if field.endswith("absence_impact"):
                value *= 100.0
            st.session_state[widget_key] = value
    for side in ("home", "away"):
        stakes = parsed.get(f"{side}_stakes")
        if stakes:
            options = ["Tranquilla a meta classifica", "Lotta Scudetto / Europa", "Salvezza disperata", "Derby / alta rivalita"]
            normalized = stakes.lower()
            selected = next((option for option in options if option.lower() in normalized or normalized in option.lower()), None)
            if selected:
                st.session_state[f"{widget_prefix}_{side}_stakes"] = selected
    for quote_key, quote in parsed.get("bookmaker_odds", {}).items():
        st.session_state[f"odds_{quote_key.replace(':', '_')}"] = quote


@st.cache_data(ttl=15, show_spinner=False)
def load_competitions() -> List[Dict[str, Any]]:
    return database.get_all_leagues()


@st.cache_data(ttl=15, show_spinner=False)
def load_matches(league_id: int) -> List[Dict[str, Any]]:
    return database.get_matches(league_id=league_id, limit=500)


@st.cache_data(ttl=15, show_spinner=False)
def load_standings(league_id: int) -> List[Dict[str, Any]]:
    return database.get_standings_by_league(league_id)


@st.cache_data(ttl=15, show_spinner=False)
def load_scorers(league_id: int) -> List[Dict[str, Any]]:
    return database.get_top_scorers_by_league(league_id, limit=20)


def load_team(team_id: int) -> Dict[str, Any]:
    return database.get_team_by_id(team_id) or {}


def team_defaults(record: Dict[str, Any], fallback_name: str) -> Dict[str, Any]:
    """Prepara valori UI e motore anche quando l'API omette campi secondari."""
    return {
        "name": record.get("name") or record.get("team_name") or fallback_name,
        "attack": _number(record.get("attack"), 1.0),
        "defense": _number(record.get("defense"), 1.0),
        "elo": _number(record.get("elo"), 1500.0),
        "cards_factor": _number(record.get("cards_factor"), 1.0),
        "corners_factor": _number(record.get("corners_factor"), 1.0),
        "recent_form": record.get("recent_form") or "D-D-D-D-D",
        "xg_for": _optional_number(record.get("xg_for")),
        "xg_against": _optional_number(record.get("xg_against")),
    }


def team_params_from_record(record: Dict[str, Any], fallback_name: str) -> TeamParams:
    values = team_defaults(record, fallback_name)
    return TeamParams(**values)


def team_editor(label: str, defaults: Dict[str, Any], widget_key: str) -> TeamParams:
    """Renderizza un editor di squadra e restituisce i parametri del motore."""
    st.markdown(f"### {label}")
    name = st.text_input("Nome", value=defaults["name"], key=f"{widget_key}_name")
    col_a, col_b = st.columns(2)
    with col_a:
        attack = st.number_input("Attacco", min_value=0.2, max_value=3.0, value=defaults["attack"], step=0.01, key=f"{widget_key}_attack")
        elo = st.number_input("Elo", min_value=800.0, max_value=2400.0, value=defaults["elo"], step=5.0, key=f"{widget_key}_elo")
        cards_factor = st.number_input("Fattore cartellini", min_value=0.2, max_value=5.0, value=defaults["cards_factor"], step=0.01, key=f"{widget_key}_cards")
        xg_for = st.number_input("xG fatti (opzionale)", min_value=0.0, max_value=10.0, value=defaults.get("xg_for"), step=0.01, key=f"{widget_key}_xg_for")
    with col_b:
        defense = st.number_input("Difesa", min_value=0.2, max_value=3.0, value=defaults["defense"], step=0.01, key=f"{widget_key}_defense")
        recent_form = st.text_input("Forma recente", value=defaults["recent_form"], key=f"{widget_key}_form")
        corners_factor = st.number_input("Fattore corner", min_value=0.0, max_value=100.0, value=defaults["corners_factor"], step=0.1, key=f"{widget_key}_corners")
        xg_against = st.number_input("xG subiti (opzionale)", min_value=0.0, max_value=10.0, value=defaults.get("xg_against"), step=0.01, key=f"{widget_key}_xg_against")
    return TeamParams(
        name=name.strip() or label,
        attack=attack,
        defense=defense,
        elo=elo,
        cards_factor=cards_factor,
        corners_factor=corners_factor,
        recent_form=recent_form.strip() or "D-D-D-D-D",
        xg_for=xg_for,
        xg_against=xg_against,
    )


def advanced_match_editor(widget_key: str) -> Dict[str, float]:
    """Input avanzati che alimentano direttamente xG e le Poisson accessorie."""
    st.markdown("#### Parametri avanzati del match")
    home_col, away_col = st.columns(2)
    with home_col:
        st.caption("Casa")
        home_momentum = st.slider("Momentum recente (0-10)", 0.0, 10.0, 5.0, 0.5, key=f"{widget_key}_home_momentum")
        home_absence = st.slider("Impatto assenze chiave (%)", 0.0, 100.0, 0.0, 5.0, key=f"{widget_key}_home_absence")
        home_stakes_label = st.selectbox(
            "Motivazione / obiettivo",
            ["Tranquilla a meta classifica", "Lotta Scudetto / Europa", "Salvezza disperata", "Derby / alta rivalita"],
            key=f"{widget_key}_home_stakes",
        )
    with away_col:
        st.caption("Ospite")
        away_momentum = st.slider("Momentum recente (0-10)", 0.0, 10.0, 5.0, 0.5, key=f"{widget_key}_away_momentum")
        away_absence = st.slider("Impatto assenze chiave (%)", 0.0, 100.0, 0.0, 5.0, key=f"{widget_key}_away_absence")
        away_stakes_label = st.selectbox(
            "Motivazione / obiettivo",
            ["Tranquilla a meta classifica", "Lotta Scudetto / Europa", "Salvezza disperata", "Derby / alta rivalita"],
            key=f"{widget_key}_away_stakes",
        )
    stakes = {
        "Tranquilla a meta classifica": 1.00,
        "Lotta Scudetto / Europa": 1.06,
        "Salvezza disperata": 1.08,
        "Derby / alta rivalita": 1.05,
    }
    st.caption("Profilo arbitrale designato")
    referee_col1, referee_col2, referee_col3 = st.columns(3)
    with referee_col1:
        referee_yellows = st.number_input("Gialli medi", 0.0, 15.0, 4.5, 0.1, key=f"{widget_key}_ref_yellows")
    with referee_col2:
        referee_reds = st.number_input("Rossi medi", 0.0, 3.0, 0.15, 0.01, key=f"{widget_key}_ref_reds")
    with referee_col3:
        referee_fouls = st.number_input("Falli medi", 5.0, 60.0, 24.0, 0.5, key=f"{widget_key}_ref_fouls")
    return {
        "home_momentum": home_momentum,
        "away_momentum": away_momentum,
        "home_absence_impact": home_absence / 100.0,
        "away_absence_impact": away_absence / 100.0,
        "home_stakes_multiplier": stakes[home_stakes_label],
        "away_stakes_multiplier": stakes[away_stakes_label],
        "referee_yellow_avg": referee_yellows,
        "referee_red_avg": referee_reds,
        "referee_fouls_avg": referee_fouls,
    }


ADVANCED_MATCH_FIELDS = (
    "home_momentum",
    "away_momentum",
    "home_absence_impact",
    "away_absence_impact",
    "home_stakes_multiplier",
    "away_stakes_multiplier",
    "referee_yellow_avg",
    "referee_red_avg",
    "referee_fouls_avg",
)


def normalize_advanced_config(values: Dict[str, float]) -> Dict[str, float]:
    """Passa a MatchConfig solo campi dichiarati dal contratto del motore."""
    defaults = {
        "home_momentum": 5.0,
        "away_momentum": 5.0,
        "home_absence_impact": 0.0,
        "away_absence_impact": 0.0,
        "home_stakes_multiplier": 1.0,
        "away_stakes_multiplier": 1.0,
        "referee_yellow_avg": 4.5,
        "referee_red_avg": 0.15,
        "referee_fouls_avg": 24.0,
    }
    return {
        field_name: float(values.get(field_name, default_value))
        for field_name, default_value in defaults.items()
        if field_name in ADVANCED_MATCH_FIELDS
    }


def odds_editor() -> Dict[str, float]:
    """Raccoglie solo quote compilate: un campo vuoto non entra nel payload."""
    odds: Dict[str, float] = {}
    st.markdown("### Quote bookmaker <span style='color:#91a4b2;font-size:.8rem'>(opzionali)</span>", unsafe_allow_html=True)
    st.caption("Lascia vuoti i mercati che non vuoi usare per il filtro value bet.")

    def ranges(values: tuple[str, ...]) -> list[tuple[str, str]]:
        return [(f"{side}_{threshold}", f"{side} {threshold}") for threshold in values for side in ("Over", "Under")]

    groups = {
        "1x2_finale": ("1X2 finale", [("1", "Casa"), ("X", "Pareggio"), ("2", "Ospite")]),
        "1x2_primo_tempo": ("1X2 primo tempo", [("1", "Casa"), ("X", "Pareggio"), ("2", "Ospite")]),
        "over_under_finale": ("Over / Under finale", ranges(("0.5", "1.5", "2.5", "3.5", "4.5"))),
        "over_under_primo_tempo": ("Over / Under primo tempo", ranges(("0.5", "1.5", "2.5", "3.5", "4.5"))),
        "goal_nogoal_finale": ("Goal / No Goal", [("Goal", "Goal"), ("No_Goal", "No Goal")]),
        "goal_nogoal_primo_tempo": ("Goal / No Goal primo tempo", [("Goal", "Goal"), ("No_Goal", "No Goal")]),
        "multigol_partita": ("Multigol partita", [(key, key.replace("_", "-")) for key in ("0_2", "1_3", "2_4", "2_5", "3_6")]),
        "multigol_casa": ("Multigol casa", [(key, key.replace("_", "-")) for key in ("0_2", "1_3", "2_4", "2_5", "3_6")]),
        "multigol_ospite": ("Multigol ospite", [(key, key.replace("_", "-")) for key in ("0_2", "1_3", "2_4", "2_5", "3_6")]),
        "over_under_squadra_casa": ("Over / Under casa", ranges(("0.5", "1.5", "2.5", "3.5"))),
        "over_under_squadra_ospite": ("Over / Under ospite", ranges(("0.5", "1.5", "2.5", "3.5"))),
        "cartellini": ("Cartellini", ranges(("3.5", "4.5", "5.5"))),
        "calci_dangolo": ("Calci d'angolo", ranges(("8.5", "9.5", "10.5", "11.5"))),
        "falli": ("Falli", ranges(("19.5", "24.5", "29.5"))),
    }
    for category, (title, markets) in groups.items():
        with st.expander(title):
            columns = st.columns(len(markets))
            for column, (market_key, market_label) in zip(columns, markets):
                with column:
                    value = st.number_input(
                        market_label,
                        min_value=1.01,
                        max_value=100.0,
                        value=st.session_state.get(f"odds_{category}_{market_key}"),
                        step=0.01,
                        format="%.2f",
                        key=f"odds_{category}_{market_key}",
                    )
                    if value is not None:
                        odds[f"{category}:{market_key}"] = float(value)
    return odds


def market_frame(market: Dict[str, Dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for selection, stats in market.items():
        if not isinstance(stats, dict) or "percentage" not in stats:
            continue
        rows.append({
            "Esito": selection.replace("_", " "),
            "Probabilità %": stats["percentage"],
            "Simulazioni": stats.get("count", 0),
        })
    return pd.DataFrame(rows)


def _percentage(result: Dict[str, Any], category: str, selection: str) -> Optional[float]:
    stat = result.get("markets", {}).get(category, {}).get(selection)
    return _optional_number(stat.get("percentage")) if isinstance(stat, dict) else None


def _display_percentage(value: Optional[float]) -> str:
    return f"{value:.1f}%" if value is not None else "N/D"


def natural_convergence_text(result: Dict[str, Any], home_team: TeamParams, away_team: TeamParams) -> str:
    convergence = result.get("market_convergence", {})
    best = convergence.get("best_synergy_market") or {}
    percentage = best.get("percentage")
    if best:
        convergence_sentence = (
            f"La convergenza piu significativa riguarda {best.get('combo', 'la combinazione selezionata')}: "
            f"compare nel {percentage:.2f}% degli scenari, con un indice di sinergia pari a {best.get('lift', 1.0):.2f} volte "
            "la frequenza attesa da eventi indipendenti."
        )
    else:
        convergence_sentence = "Non emerge una combinazione di mercati sufficientemente stabile da essere evidenziata."
    p_home = _percentage(result, "1x2_finale", "1") or 0.0
    p_away = _percentage(result, "1x2_finale", "2") or 0.0
    leader = home_team.name if p_home >= p_away else away_team.name
    leader_probability = max(p_home, p_away)
    return (
        f"Il modello ha completato {result['metadata'].get('simulations_count', 0):,} simulazioni Monte Carlo "
        f"per {home_team.name} contro {away_team.name}. {convergence_sentence} "
        f"L'andamento complessivo indica {leader} come squadra piu probabile, con una probabilita di vittoria del "
        f"{leader_probability:.1f}%. Le quote bookmaker, se inserite, vengono usate esclusivamente per confrontare "
        "il valore atteso e non modificano la simulazione matematica."
    )


def save_history_entry(result: Dict[str, Any], home_team: TeamParams, away_team: TeamParams, match: Optional[Dict[str, Any]]) -> Optional[int]:
    """Salva una simulazione sia nel database locale sia nella cronologia della sessione."""
    if result.get("history_id"):
        return result["history_id"]
    best_convergence = result.get("market_convergence", {}).get("best_synergy_market") or {}
    best_value = result.get("value_betting", {}).get("best_value_bet") or {}
    try:
        history_id = database.save_simulation_history(
            match_id=match.get("id") if match else None,
            home_team_name=home_team.name,
            away_team_name=away_team.name,
            home_elo=home_team.elo,
            away_elo=away_team.elo,
            simulations_count=result["metadata"].get("simulations_count", 100_000),
            execution_time_ms=result["metadata"].get("execution_time_ms", 0.0),
            best_convergence_market=best_convergence.get("combo"),
            best_convergence_lift=best_convergence.get("lift"),
            best_convergence_prob=best_convergence.get("percentage"),
            best_value_bet_market=best_value.get("market"),
            best_value_bet_odds=best_value.get("odds"),
            best_value_bet_ev=best_value.get("ev_pct"),
            assistant_narrative=natural_convergence_text(result, home_team, away_team),
            full_results_json=json.dumps(result),
        )
    except Exception:
        history_id = None
    result["history_id"] = history_id
    entry = {
        "history_id": history_id,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "home_team": home_team.name,
        "away_team": away_team.name,
        "predicted_score": result["metadata"].get("predicted_score", {}).get("full_time", {}),
        "narrative": natural_convergence_text(result, home_team, away_team),
    }
    history = st.session_state.setdefault("session_history", [])
    if not any(item.get("history_id") == history_id and history_id is not None for item in history):
        history.insert(0, entry)
    return history_id


def attach_replay_context(result: Dict[str, Any], home_team: TeamParams, away_team: TeamParams, advanced: Optional[Dict[str, Any]] = None, odds: Optional[Dict[str, Any]] = None) -> None:
    """Conserva nel risultato gli input necessari per ricaricare una sessione."""
    result.setdefault("metadata", {})["replay"] = {
        "home_team": asdict(home_team),
        "away_team": asdict(away_team),
        "advanced": advanced or {},
        "odds": odds or {},
    }


def _history_created_today(item: Dict[str, Any], today: Optional[str] = None) -> bool:
    created = str(item.get("created_at", ""))
    if not created:
        return False
    try:
        created_date = datetime.fromisoformat(created.replace("Z", "+00:00")).astimezone().date().isoformat()
    except ValueError:
        created_date = created[:10]
    return created_date == (today or datetime.now().date().isoformat())


def daily_history() -> List[Dict[str, Any]]:
    """Restituisce tutte le simulazioni salvate nella data locale corrente."""
    return [item for item in database.get_simulation_history(limit=500) if _history_created_today(item)]


def build_sniper_coupon(history: List[Dict[str, Any]], budget: float, system_mode: str = "Multipla standard") -> Dict[str, Any]:
    """Costruisce una copertura giornaliera pesata per probabilita reale."""
    budget = min(100.0, max(1.0, float(budget)))
    candidates: List[Dict[str, Any]] = []
    for item in history:
        detail = database.get_simulation_history_by_id(int(item["id"]))
        if not detail:
            continue
        try:
            result = json.loads(detail.get("full_results_json") or "{}")
        except (TypeError, ValueError):
            continue
        markets = result.get("markets", {})
        for category, selection in (("1x2_finale", "1"), ("1x2_finale", "X"), ("1x2_finale", "2")):
            stat = markets.get(category, {}).get(selection)
            if isinstance(stat, dict) and stat.get("percentage") is not None:
                candidates.append({
                    "partita": f"{item.get('home_team_name', 'Casa')} - {item.get('away_team_name', 'Ospite')}",
                    "segno": selection,
                    "mercato": "1X2",
                    "probabilita": float(stat["percentage"]),
                    "history_id": item["id"],
                })
    best_by_match: Dict[str, Dict[str, Any]] = {}
    for candidate in candidates:
        current = best_by_match.get(candidate["partita"])
        if current is None or candidate["probabilita"] > current["probabilita"]:
            best_by_match[candidate["partita"]] = candidate
    selections = sorted(best_by_match.values(), key=lambda value: value["probabilita"], reverse=True)
    if system_mode == "Sistema integrato":
        selections = selections[: min(8, len(selections))]
        combinations = max(1, len(selections) * (len(selections) - 1) // 2)
    else:
        selections = selections[:10]
        combinations = 1
    total_probability = sum(item["probabilita"] for item in selections) or 1.0
    for item in selections:
        item["quota_budget"] = round(budget * item["probabilita"] / total_probability, 2)
    return {
        "date": datetime.now().date().isoformat(),
        "budget": budget,
        "mode": system_mode,
        "combinations": combinations,
        "selections": selections,
        "covered_matches": len(selections),
    }


def reload_history_item(history_id: int) -> bool:
    """Ricarica una simulazione nello spazio di lavoro personalizzato."""
    detail = database.get_simulation_history_by_id(history_id)
    if not detail:
        return False
    try:
        result = json.loads(detail.get("full_results_json") or "{}")
    except (TypeError, ValueError):
        return False
    replay = result.get("metadata", {}).get("replay", {})
    home = replay.get("home_team")
    away = replay.get("away_team")
    if not home or not away:
        return False
    st.session_state["custom_result"] = result
    st.session_state["custom_context"] = (TeamParams(**home), TeamParams(**away))
    st.session_state["custom_replay_advanced"] = replay.get("advanced", {})
    st.session_state["custom_replay_odds"] = replay.get("odds", {})
    parsed = {}
    for side, team in (("home", home), ("away", away)):
        for field in ("name", "attack", "defense", "elo", "cards_factor", "corners_factor", "xg_for", "xg_against", "recent_form"):
            if team.get(field) is not None:
                parsed[f"{side}_{field}"] = team[field]
    parsed.update(replay.get("advanced", {}))
    apply_pasted_values(parsed, "custom")
    st.session_state["page"] = "custom"
    return True


def _logo_html(team: TeamParams, logo: Optional[str]) -> str:
    if logo:
        return f'<img class="team-logo" src="{logo}" alt="{team.name}">'
    return ""


def render_match_header(result: Dict[str, Any], home_team: TeamParams, away_team: TeamParams, match: Optional[Dict[str, Any]]) -> None:
    predicted = result["metadata"].get("predicted_score", {})
    full_time = predicted.get("full_time", {})
    home_probability = _percentage(result, "1x2_finale", "1") or 0.0
    draw_probability = _percentage(result, "1x2_finale", "X") or 0.0
    away_probability = _percentage(result, "1x2_finale", "2") or 0.0
    outcomes = [(home_probability, f"{home_team.name.upper()} TO WIN"), (draw_probability, "DRAW"), (away_probability, f"{away_team.name.upper()} TO WIN")]
    confidence, confidence_label = max(outcomes, key=lambda item: item[0])
    home_logo = match.get("home_team_logo") if match else None
    away_logo = match.get("away_team_logo") if match else None
    st.markdown(
        f"""
        <div class="match-header">
          <div class="match-teams">
            <div class="team-name">{_logo_html(home_team, home_logo)}{home_team.name}</div>
            <div class="predicted-score">{full_time.get('home', 0)} : {full_time.get('away', 0)}</div>
            <div class="team-name">{_logo_html(away_team, away_logo)}{away_team.name}</div>
          </div>
          <div class="confidence">{confidence_label} - {confidence:.1f}% CONFIDENCE</div>
        </div>
        <div class="probability-bar">
          <div class="prob-home" style="width:{home_probability}%"></div>
          <div class="prob-draw" style="width:{draw_probability}%"></div>
          <div class="prob-away" style="width:{away_probability}%"></div>
        </div>
        <div class="probability-labels"><span>1 · {home_probability:.1f}%</span><span>X · {draw_probability:.1f}%</span><span>2 · {away_probability:.1f}%</span></div>
        """,
        unsafe_allow_html=True,
    )


def render_prop_grid(result: Dict[str, Any], home_team: TeamParams, away_team: TeamParams) -> None:
    over_25 = _percentage(result, "over_under_finale", "Over_2.5")
    both_score = _percentage(result, "goal_nogoal_finale", "Goal")
    corner_mean = result.get("markets", {}).get("calci_dangolo", {}).get("expected_mean")
    cards_mean = result.get("markets", {}).get("cartellini", {}).get("expected_mean")
    fouls_mean = result.get("markets", {}).get("falli", {}).get("expected_mean")
    lambda_value = result["metadata"].get("expected_goals_home_lambda")
    mu_value = result["metadata"].get("expected_goals_away_mu")
    total_xg = (_number(lambda_value, 0.0) + _number(mu_value, 0.0))
    first_goal = None if total_xg <= 0 else _number(lambda_value, 0.0) / total_xg * 100.0
    first_goal_value = "N/D" if first_goal is None else f"{home_team.name} {first_goal:.1f}% · {away_team.name} {100.0 - first_goal:.1f}%"
    props = [
        ("Over 2.5", _display_percentage(over_25)),
        ("Both teams score", _display_percentage(both_score)),
        ("First goal", first_goal_value),
        ("Corners", f"{corner_mean:.2f}" if corner_mean is not None else "N/D"),
        ("Cards", f"{cards_mean:.2f}" if cards_mean is not None else "N/D"),
        ("Fouls", f"{fouls_mean:.2f}" if fouls_mean is not None else "N/D"),
    ]
    cards = "".join(f'<div class="prop-card"><div class="prop-label">{label}</div><div class="prop-value">{value}</div></div>' for label, value in props)
    st.markdown(f'<div style="display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:.65rem">{cards}</div>', unsafe_allow_html=True)


def show_results(result: Dict[str, Any], home_team: TeamParams, away_team: TeamParams, match: Optional[Dict[str, Any]]) -> None:
    metadata = result["metadata"]
    save_history_entry(result, home_team, away_team, match)
    render_match_header(result, home_team, away_team, match)
    st.caption(f"Monte Carlo Dixon-Coles · {metadata['simulations_count']:,} simulazioni · {metadata['execution_time_ms']:.2f} ms")

    st.subheader("Predicted Scoreboard")
    predicted = metadata.get("predicted_score", {})
    scoreboard = pd.DataFrame([
        {"Periodo": "Primo Tempo", home_team.name: predicted.get("first_half", {}).get("home", "N/D"), away_team.name: predicted.get("first_half", {}).get("away", "N/D")},
        {"Periodo": "Secondo Tempo", home_team.name: predicted.get("second_half", {}).get("home", "N/D"), away_team.name: predicted.get("second_half", {}).get("away", "N/D")},
        {"Periodo": "Finale", home_team.name: predicted.get("full_time", {}).get("home", "N/D"), away_team.name: predicted.get("full_time", {}).get("away", "N/D")},
    ])
    st.dataframe(scoreboard, width="stretch", hide_index=True)

    st.subheader("Match Props")
    render_prop_grid(result, home_team, away_team)

    value_bet = result["value_betting"].get("best_value_bet")
    if value_bet:
        st.info(
            f"Value bet migliore: **{value_bet['market']}** @ {value_bet['odds']:.2f} "
            f"(EV {value_bet['ev_pct']:+.2f}%, edge {value_bet['edge_pct']:+.2f}%)."
        )
    else:
        st.info("Nessun value bet calcolato: inserisci una o più quote per attivare il filtro.")

    st.subheader("Analisi mercati")
    market_labels = {
        "1x2_finale": "1X2 finale",
        "1x2_primo_tempo": "1X2 primo tempo",
        "over_under_finale": "Over / Under finale",
        "over_under_primo_tempo": "Over / Under primo tempo",
        "goal_nogoal_finale": "Goal / No Goal finale",
        "goal_nogoal_primo_tempo": "Goal / No Goal primo tempo",
        "cartellini": "Cartellini",
        "calci_dangolo": "Calci d'angolo",
        "falli": "Falli",
        "multigol_partita": "Multigol partita",
        "multigol_casa": "Multigol casa",
        "multigol_ospite": "Multigol ospite",
        "multigol_casa_combo_ospite": "Multigol casa + ospite",
        "multigol_primo_tempo_combo_secondo_tempo": "Multigol tempi",
        "over_under_squadra_casa": "Over / Under casa",
        "over_under_squadra_ospite": "Over / Under ospite",
    }
    tabs = st.tabs(list(market_labels.values()))
    for tab, category in zip(tabs, market_labels):
        with tab:
            st.dataframe(market_frame(result["markets"][category]), width="stretch", hide_index=True)

    st.subheader("Commento Esperto IA")
    st.info(result.get("ai_narrative") or natural_convergence_text(result, home_team, away_team))
    st.subheader("Convergenza del modello")
    st.write(natural_convergence_text(result, home_team, away_team))


def calculate_team_strength_from_result(result: Dict[str, Any], side: str) -> float:
    """Recupera la forza senza conservare oggetti TeamParams nello stato del risultato."""
    # La UI usa questo valore solo per un riepilogo; il motore conserva già gli xG nel metadata.
    return float(result["metadata"].get(f"{side}_team_strength", 0.0))


def input_snapshot(home_team: TeamParams, away_team: TeamParams, match: Optional[Dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for side, team in (("Casa", home_team), ("Ospite", away_team)):
        rows.append({
            "Squadra": side,
            "Nome": team.name,
            "Attacco": team.attack,
            "Difesa": team.defense,
            "Elo": team.elo,
            "Forma": team.recent_form,
            "xG fatti": team.xg_for,
            "xG subiti": team.xg_against,
            "Fonte": "API/database" if match else "Inserimento manuale",
        })
    return pd.DataFrame(rows)


def render_welcome(competitions: List[Dict[str, Any]]) -> None:
    """Home compatta: rende visibili le competizioni disponibili prima dell'analisi."""
    st.markdown(
        "<div class='welcome-card'><h2>Benvenuto in Simulatore IA</h2>"
        "<p>Scegli una partita dai dati sincronizzati oppure crea un confronto personalizzato. "
        "Le quote sono facoltative: la simulazione matematica parte sempre.</p></div>",
        unsafe_allow_html=True,
    )
    st.subheader("Campionati disponibili")
    if not competitions:
        st.info("Nessun campionato sincronizzato. Puoi comunque creare una partita personalizzata.")
        return
    columns = st.columns(2)
    for index, league in enumerate(competitions):
        with columns[index % 2]:
            with st.expander(f"{league.get('name', 'Campionato')} · {league.get('country', 'N/D')}"):
                matches = load_matches(int(league["id"]))
                st.write(f"{len(matches)} partite disponibili")
                if matches:
                    preview = pd.DataFrame([
                        {
                            "Data": match.get("match_date", "N/D"),
                            "Partita": f"{match.get('home_team_name', 'Casa')} - {match.get('away_team_name', 'Ospite')}",
                            "Stato": match.get("status", "N/D"),
                        }
                        for match in matches[:5]
                    ])
                    st.dataframe(preview, width="stretch", hide_index=True)

    st.caption("Per partire subito, seleziona 'Nuova partita personalizzata' nel percorso di analisi qui sotto.")


def render_daily_coupon() -> None:
    st.subheader("Equalizzatore Universale")
    st.caption("Copertura Sniper sulle simulazioni salvate e analizzate oggi.")
    history = daily_history()
    budget_col, mode_col, action_col = st.columns([1, 2, 1])
    with budget_col:
        budget = st.number_input("Budget complessivo (€)", min_value=1.0, max_value=100.0, value=10.0, step=1.0, key="daily_coupon_budget")
    with mode_col:
        mode = st.selectbox("Modalita", ["Multipla standard", "Sistema integrato"], key="daily_coupon_mode")
    with action_col:
        analyze = st.button("Analizza Schedina", type="primary", key="analyze_daily_coupon", width="stretch")
    if analyze:
        st.session_state["daily_coupon"] = build_sniper_coupon(history, budget, mode)
    coupon = st.session_state.get("daily_coupon")
    if not coupon:
        st.info(f"Nessuna analisi odierna disponibile: {len(history)} sessioni salvate oggi.")
        return
    if not coupon["selections"]:
        st.warning("Le sessioni odierne non contengono mercati utilizzabili per la copertura.")
        return
    st.caption(f"{coupon['covered_matches']} partite coperte · {coupon['combinations']} combinazioni · budget allocato: {coupon['budget']:.2f} €")
    st.dataframe(pd.DataFrame(coupon["selections"]), width="stretch", hide_index=True)


def render_history() -> None:
    history = database.get_simulation_history(limit=20)
    if not history:
        return
    with st.expander("Cronologia analisi recenti"):
        for item in history:
            columns = st.columns([3, 2, 1])
            with columns[0]:
                st.write(f"**{item.get('home_team_name', 'Casa')} - {item.get('away_team_name', 'Ospite')}**")
                st.caption(f"{item.get('created_at', 'N/D')} · {item.get('best_convergence_market') or 'Convergenza N/D'}")
            with columns[1]:
                st.caption(f"{item.get('simulations_count', 0):,} simulazioni")
            with columns[2]:
                if st.button("Esplora / Ricarica", key=f"history_reload_home_{item['id']}", width="stretch"):
                    if reload_history_item(int(item["id"])):
                        st.rerun()


def render_main_navigation() -> None:
    """Menu principale centrale, indipendente dalla navigazione interna dei campionati."""
    labels = [
        ("home", "Home / Schedina"),
        ("championships", "Campionati"),
        ("custom", "Crea / Analizza Partita"),
        ("history", "Cronologia Partite Salvate"),
    ]
    st.markdown("<div class='main-nav'>", unsafe_allow_html=True)
    columns = st.columns(4)
    current_page = st.session_state.get("page", "home")
    current_section = "championships" if current_page in {"league", "matchday", "match"} else current_page
    for column, (page, label) in zip(columns, labels):
        with column:
            button_type = "primary" if current_section == page else "secondary"
            if st.button(label, key=f"main_nav_{page}", type=button_type, width="stretch"):
                go_to(page, league_id=None, matchday=None, match_id=None)
    st.markdown("</div>", unsafe_allow_html=True)


def render_championships_page(competitions: List[Dict[str, Any]]) -> None:
    navigation_header("Campionati", "home")
    if not competitions:
        st.info("Nessun campionato disponibile nei dati sincronizzati.")
        return
    options = {f"{league.get('name', 'Campionato')} · {league.get('country', 'N/D')}": int(league["id"]) for league in competitions}
    selected_label = st.selectbox("Seleziona campionato", list(options), key="main_championship_select")
    selected_id = options[selected_label]
    selected_league = next(league for league in competitions if int(league["id"]) == selected_id)
    if st.button("Apri classifiche e calendario", type="primary", key="open_selected_championship", width="stretch"):
        go_to("league", league_id=selected_id, matchday=None, match_id=None)
    st.markdown(
        f"<div class='league-card'><div class='prop-label'>Campionato selezionato</div>"
        f"<div class='prop-value'>{selected_league.get('name', 'Campionato')}</div></div>",
        unsafe_allow_html=True,
    )


def render_saved_history_page() -> None:
    navigation_header("Cronologia Partite Salvate", "home")
    history = database.get_simulation_history(limit=100)
    if not history:
        st.info("Non ci sono ancora simulazioni salvate.")
        return
    for item in history:
        columns = st.columns([3, 2, 2, 1])
        with columns[0]:
            st.write(f"**{item.get('home_team_name', 'Casa')} - {item.get('away_team_name', 'Ospite')}**")
            st.caption(item.get("created_at", "N/D"))
        with columns[1]:
            st.caption(f"{item.get('simulations_count', 0):,} simulazioni")
        with columns[2]:
            st.caption(f"Convergenza: {item.get('best_convergence_market') or 'N/D'}")
            st.caption(f"Value bet: {item.get('best_value_bet_market') or 'N/D'}")
        with columns[3]:
            if st.button("Esplora / Ricarica", key=f"history_reload_{item['id']}", width="stretch"):
                if reload_history_item(int(item["id"])):
                    st.rerun()


def init_navigation() -> None:
    defaults = {"page": "home", "league_id": None, "matchday": None, "match_id": None}
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def go_to(page: str, **values: Any) -> None:
    st.session_state["page"] = page
    for key, value in values.items():
        st.session_state[key] = value
    st.rerun()


def navigation_header(title: str, back_page: Optional[str] = None, **back_values: Any) -> None:
    columns = st.columns([1, 6, 1])
    with columns[0]:
        if back_page and st.button("← Indietro", key=f"back_{back_page}_{title}", width="stretch"):
            go_to(back_page, **back_values)
    with columns[1]:
        st.markdown(f"<h2 style='text-align:center;margin:.2rem 0 1rem'>{title}</h2>", unsafe_allow_html=True)
    with columns[2]:
        if st.button("Home", key=f"home_{title}", width="stretch"):
            go_to("home", league_id=None, matchday=None, match_id=None)


def render_home_page(competitions: List[Dict[str, Any]]) -> None:
    render_welcome(competitions)
    render_daily_coupon()
    if competitions:
        render_history()
    if competitions:
        st.subheader("Scegli un campionato")
        columns = st.columns(3)
        for index, league in enumerate(competitions):
            with columns[index % 3]:
                st.markdown(
                    f"<div class='league-card'><div class='prop-label'>{league.get('country', 'Europa')}</div>"
                    f"<div class='prop-value'>{league.get('name', 'Campionato')}</div></div>",
                    unsafe_allow_html=True,
                )
                if st.button("Apri campionato", key=f"league_{league['id']}", width="stretch"):
                    go_to("league", league_id=int(league["id"]), matchday=None, match_id=None)
    if st.button("＋ Nuova partita personalizzata", type="primary", key="new_match", width="stretch"):
        go_to("custom", league_id=None, matchday=None, match_id=None)


def render_league_page(league: Dict[str, Any]) -> None:
    navigation_header(league.get("name", "Campionato"), "home")
    league_id = int(league["id"])
    refresh_col, status_col = st.columns([1, 4])
    with refresh_col:
        refresh = st.button("Aggiorna dati", key=f"refresh_league_{league_id}", width="stretch")
    if refresh:
        load_standings.clear()
        load_scorers.clear()
        load_matches.clear()
        load_competitions.clear()
        st.session_state["league_data_refresh"] = datetime.now().strftime("%H:%M:%S")
        st.rerun()
    with status_col:
        refreshed_at = st.session_state.get("league_data_refresh")
        message = f"Ultimo aggiornamento locale: {refreshed_at}" if refreshed_at else "Dati letti dalle strutture sincronizzate/API"
        st.caption(message)

    standings = load_standings(league_id)
    scorers = load_scorers(league_id)
    standings_tab, scorers_tab, fixtures_tab = st.tabs(["Classifica generale", "Classifica marcatori", "Calendario"])
    with standings_tab:
        if standings:
            table = pd.DataFrame([
                {"#": index + 1, "Squadra": row.get("team_name", "N/D"), "PG": row.get("played", 0),
                 "V": row.get("won", 0), "N": row.get("drawn", 0), "P": row.get("lost", 0),
                 "GF": row.get("goals_for", 0), "GS": row.get("goals_against", 0),
                 "DR": row.get("goal_diff", 0), "PT": row.get("points", 0)}
                for index, row in enumerate(standings)
            ])
            st.dataframe(table, width="stretch", hide_index=True)
        else:
            st.info("Classifica non ancora disponibile per questo campionato.")
    with scorers_tab:
        if scorers:
            table = pd.DataFrame([
                {"#": index + 1, "Giocatore": row.get("player_name", "N/D"), "Squadra": row.get("team_name", "N/D"),
                 "Gol": row.get("goals", 0), "Assist": row.get("assists", 0)}
                for index, row in enumerate(scorers)
            ])
            st.dataframe(table, width="stretch", hide_index=True)
        else:
            st.info("Classifica marcatori non ancora disponibile.")

    with fixtures_tab:
        matches = load_matches(league_id)
        matchdays: List[str] = []
        for match in matches:
            matchday = str(match.get("matchday") or "N/D")
            if matchday not in matchdays:
                matchdays.append(matchday)
        st.caption(f"{len(matchdays)} giornate presenti nei dati sincronizzati")
        if not matchdays:
            st.info("Nessuna giornata disponibile.")
            return
        day_columns = st.columns(6)
        for index, matchday in enumerate(matchdays):
            with day_columns[index % 6]:
                if st.button(f"{matchday}", key=f"day_{league['id']}_{index}", width="stretch"):
                    go_to("matchday", league_id=int(league["id"]), matchday=matchday, match_id=None)
                st.markdown(f"<div class='matchday-caption'>Giornata {matchday}</div>", unsafe_allow_html=True)


def render_matchday_page(league: Dict[str, Any]) -> None:
    matchday = st.session_state.get("matchday")
    navigation_header(f"{league.get('name', 'Campionato')} · Giornata {matchday}", "league", league_id=int(league["id"]), matchday=None, match_id=None)
    matches = [match for match in load_matches(int(league["id"])) if str(match.get("matchday") or "N/D") == str(matchday)]
    if not matches:
        st.warning("Nessuna partita trovata per questa giornata.")
        return
    for match in matches:
        columns = st.columns([4, 2, 1])
        with columns[0]:
            st.markdown(f"**{match.get('home_team_name', 'Casa')}**  vs  **{match.get('away_team_name', 'Ospite')}**")
            st.caption(f"{match.get('match_date', 'Data N/D')} · {match.get('status', 'stato N/D')}")
        with columns[1]:
            if match.get("status") == "completed":
                st.metric("Risultato", f"{match.get('home_goals', '-')} : {match.get('away_goals', '-')}")
            else:
                st.caption("Da giocare")
        with columns[2]:
            if st.button("Analizza", key=f"match_{match['id']}", width="stretch"):
                go_to("match", league_id=int(league["id"]), matchday=matchday, match_id=int(match["id"]))
        st.divider()


def run_api_match(match: Dict[str, Any], home_team: TeamParams, away_team: TeamParams, advanced: Dict[str, float], simulations: int, seed: int, home_advantage: float, base_home: float, base_away: float, rho: float) -> tuple[Dict[str, Any], TeamParams, TeamParams]:
    advanced_config = normalize_advanced_config(advanced)
    config = MatchConfig(
        home_team=home_team,
        away_team=away_team,
        home_advantage=_number(match.get("home_advantage"), home_advantage),
        base_goals_home=base_home,
        base_goals_away=base_away,
        dixon_coles_rho=rho,
        n_simulations=simulations,
        seed=seed,
        **advanced_config,
    )
    team_key = (
        home_team.name, home_team.attack, home_team.defense, home_team.elo, home_team.xg_for, home_team.xg_against,
        away_team.name, away_team.attack, away_team.defense, away_team.elo, away_team.xg_for, away_team.xg_against,
        tuple(sorted(advanced_config.items())),
    )
    cache_key = f"api_{match['id']}_{simulations}_{seed}_{rho}_{team_key}"
    if st.session_state.get("match_result_key") != cache_key:
        with st.spinner("Calcolo simulazione Monte Carlo..."):
            st.session_state["match_result"] = simulate_match(config, custom_odds={})
            st.session_state["match_result_key"] = cache_key
    return st.session_state["match_result"], home_team, away_team


def render_match_page(league: Dict[str, Any], simulations: int, seed: int, home_advantage: float, base_home: float, base_away: float, rho: float) -> None:
    match = database.get_match_by_id(int(st.session_state["match_id"]))
    if not match:
        st.error("Partita non trovata nei dati sincronizzati.")
        return
    navigation_header("Analisi partita", "matchday", league_id=int(league["id"]), matchday=st.session_state.get("matchday"), match_id=None)
    home_defaults = team_defaults(load_team(int(match["home_team_id"])), match.get("home_team_name", "Casa"))
    away_defaults = team_defaults(load_team(int(match["away_team_id"])), match.get("away_team_name", "Ospite"))
    st.caption("Input manuali forzati: i valori inseriti qui sovrascrivono i dati esterni disponibili per questa analisi.")
    input_columns = st.columns(2)
    with input_columns[0]:
        home_team = team_editor("Casa", home_defaults, f"api_home_{match['id']}")
    with input_columns[1]:
        away_team = team_editor("Ospite", away_defaults, f"api_away_{match['id']}")
    advanced = advanced_match_editor(f"api_match_{match['id']}")
    st.dataframe(input_snapshot(home_team, away_team, match), width="stretch", hide_index=True)
    if st.button("🚀 Esegui Simulazione con Dati Manuali", type="primary", key=f"manual_simulation_{match['id']}", width="stretch"):
        result, home_team, away_team = run_api_match(match, home_team, away_team, advanced, simulations, seed, home_advantage, base_home, base_away, rho)
        attach_replay_context(result, home_team, away_team, advanced)
        st.session_state["manual_analysis_result"] = result
        st.session_state["manual_analysis_context"] = (home_team, away_team, match)
    context = st.session_state.get("manual_analysis_context")
    if context and st.session_state.get("manual_analysis_result"):
        show_results(st.session_state["manual_analysis_result"], *context)


def render_custom_page(simulations: int, seed: int, home_advantage: float, base_home: float, base_away: float, rho: float) -> None:
    navigation_header("Nuova partita personalizzata", "home")
    defaults_home = {"name": "Squadra Casa", "attack": 1.15, "defense": 0.95, "elo": 1550.0, "cards_factor": 1.0, "corners_factor": 1.0, "recent_form": "W-D-W-D-W", "xg_for": None, "xg_against": None}
    defaults_away = {"name": "Squadra Ospite", "attack": 1.05, "defense": 1.05, "elo": 1500.0, "cards_factor": 1.0, "corners_factor": 1.0, "recent_form": "D-W-L-D-W", "xg_for": None, "xg_against": None}
    paste = st.text_area(
        "Incolla dati partita (parser flessibile)",
        placeholder="Casa:\nNome: Inter\nAttacco: 1,30\nElo: 1820\n\nOspite:\nNome: Milan\nDifesa: 1.05",
        key="custom_paste_data",
        height=150,
    )
    if st.button("Mappa dati incollati", key="map_custom_paste", width="stretch"):
        parsed = parse_team_paste(paste)
        apply_pasted_values(parsed, "custom")
        st.session_state["custom_paste_status"] = f"Mappati {len(parsed)} campi; i campi non presenti sono rimasti invariati."
        st.rerun()
    if st.session_state.get("custom_paste_status"):
        st.caption(st.session_state["custom_paste_status"])
    left, right = st.columns(2)
    with left:
        home_team = team_editor("Casa", defaults_home, "custom_home")
    with right:
        away_team = team_editor("Ospite", defaults_away, "custom_away")
    advanced = advanced_match_editor("custom_match")
    odds = odds_editor()
    if st.button("Avvia analisi personalizzata", type="primary", width="stretch"):
        config = MatchConfig(home_team=home_team, away_team=away_team, home_advantage=home_advantage, base_goals_home=base_home, base_goals_away=base_away, dixon_coles_rho=rho, n_simulations=simulations, seed=seed, **normalize_advanced_config(advanced))
        with st.spinner("Calcolo simulazione Monte Carlo..."):
            st.session_state["custom_result"] = simulate_match(config, custom_odds=odds)
            attach_replay_context(st.session_state["custom_result"], home_team, away_team, advanced, odds)
            st.session_state["custom_context"] = (home_team, away_team)
    if "custom_result" in st.session_state:
        home, away = st.session_state["custom_context"]
        show_results(st.session_state["custom_result"], home, away, None)


def main() -> None:
    init_navigation()
    st.markdown(
        "<div class='hero'><h1>Simulatore IA</h1><p>Monte Carlo Dixon-Coles per esplorare scenari, mercati e value bet.</p></div>",
        unsafe_allow_html=True,
    )
    render_main_navigation()

    simulations = 100_000
    seed = 42
    home_advantage = 1.15
    base_goals_home = 1.38
    base_goals_away = 1.12
    dixon_coles_rho = -0.11
    competitions = load_competitions()
    page = st.session_state["page"]
    if page == "home":
        render_home_page(competitions)
    elif page == "championships":
        render_championships_page(competitions)
    elif page == "league":
        league = next((item for item in competitions if int(item["id"]) == int(st.session_state["league_id"])), None)
        if league:
            render_league_page(league)
        else:
            go_to("home")
    elif page == "matchday":
        league = next((item for item in competitions if int(item["id"]) == int(st.session_state["league_id"])), None)
        if league:
            render_matchday_page(league)
        else:
            go_to("home")
    elif page == "match":
        league = next((item for item in competitions if int(item["id"]) == int(st.session_state["league_id"])), None)
        if league:
            render_match_page(league, simulations, int(seed), home_advantage, base_goals_home, base_goals_away, dixon_coles_rho)
        else:
            go_to("home")
    elif page == "custom":
        render_custom_page(simulations, int(seed), home_advantage, base_goals_home, base_goals_away, dixon_coles_rho)
    elif page == "history":
        render_saved_history_page()


if __name__ == "__main__":
    main()