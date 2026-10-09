"""Minimal on-demand Streamlit interface."""

import pandas as pd
import streamlit as st

from engine import config_from_input, simulate_match
from parser import MatchInputError, MatchInput, ParsedReferee, ParsedTeam, parse_match_input


EXAMPLE = """CASA: Inter
Attacco: 1.34 | Difesa: 0.78 | Elo: 1835 | Forma: W-W-D-W-W | xG Fatti: 2.15 | xG Subiti: 0.85 | Corner pro/sub: 1.25/0.95 | Cartellini pro: 0.95

OSPITE: Milan
Attacco: 1.22 | Difesa: 0.92 | Elo: 1765 | Forma: W-W-L-D-W | xG Fatti: 1.85 | xG Subiti: 1.10 | Corner pro/sub: 1.15/1.10 | Cartellini pro: 1.10

ARBITRO: Gialli medi 4.5 | Falli medi 24
"""

st.set_page_config(page_title="Simulatore IA · On-demand", page_icon="⚽", layout="wide")
st.markdown(
    """
    <style>
    .score-card {
        background: linear-gradient(145deg, #172235 0%, #101827 100%);
        border: 1px solid #2b3b55;
        border-radius: 16px;
        padding: 16px 18px;
        min-height: 142px;
        margin-bottom: 14px;
        box-shadow: 0 8px 24px rgba(7, 14, 28, .20);
    }
    .score-card .eyebrow { color: #93a4bf; font-size: .74rem; text-transform: uppercase; letter-spacing: .08em; }
    .score-card .market { color: #f4f7fb; font-size: 1.05rem; font-weight: 650; margin: 6px 0 10px; }
    .score-card .prob { color: #fff; font-size: 2rem; line-height: 1; font-weight: 800; }
    .score-card .meta { color: #aebbd0; font-size: .78rem; margin-top: 10px; }
    .score-card .badge { display: inline-block; border-radius: 999px; padding: 4px 9px; margin-top: 9px; font-size: .7rem; font-weight: 750; }
    .score-card .positive { color: #b8f7d1; background: #124b38; }
    .score-card .neutral { color: #c2ccdb; background: #29374c; }
    .section-kicker { color: #6f83a2; font-weight: 750; letter-spacing: .08em; text-transform: uppercase; font-size: .78rem; margin: 18px 0 8px; }
    </style>
    """,
    unsafe_allow_html=True,
)
st.title("Motore on-demand")
st.caption("Dashboard analitica senza calendario o database: input dichiarato, calcolo riproducibile e quote opzionali.")

input_mode = st.radio("Modalità input", ["Copia-incolla", "Crea partita"], horizontal=True)
if input_mode == "Copia-incolla":
    text = st.text_area("Incolla i dati della partita", value=EXAMPLE, height=260)
else:
    st.info("I campi guidati costruiscono lo stesso contratto usato dal parser.")
    home_col, away_col = st.columns(2)

    def guided_team(label: str, key: str, defaults: tuple) -> ParsedTeam:
        with (home_col if key == "home" else away_col):
            st.subheader(label)
            name = st.text_input("Nome", defaults[0], key=f"{key}_name")
            attack = st.slider("Attacco", 0.2, 3.0, defaults[1], 0.01, key=f"{key}_attack")
            defense = st.slider("Difesa", 0.2, 3.0, defaults[2], 0.01, key=f"{key}_defense")
            elo = st.number_input("Elo", 800, 2400, defaults[3], 5, key=f"{key}_elo")
            form = st.text_input("Forma W-D-L", defaults[4], key=f"{key}_form")
            xg_for = st.number_input("xG fatti", 0.0, 10.0, defaults[5], 0.01, key=f"{key}_xgf")
            xg_against = st.number_input("xG subiti", 0.0, 10.0, defaults[6], 0.01, key=f"{key}_xga")
            corners_for = st.number_input("Corner pro", 0.0, 20.0, defaults[7], 0.01, key=f"{key}_cf")
            corners_against = st.number_input("Corner sub", 0.0, 20.0, defaults[8], 0.01, key=f"{key}_ca")
            cards_for = st.number_input("Cartellini pro", 0.0, 20.0, defaults[9], 0.01, key=f"{key}_cards")
        return ParsedTeam(name, attack, defense, elo, form, xg_for, xg_against, corners_for, corners_against, cards_for)

    home = guided_team("Casa", "home", ("Inter", 1.34, 0.78, 1835, "W-W-D-W-W", 2.15, 0.85, 1.25, 0.95, 0.95))
    away = guided_team("Ospite", "away", ("Milan", 1.22, 0.92, 1765, "W-W-L-D-W", 1.85, 1.10, 1.15, 1.10, 1.10))
    ref_col1, ref_col2 = st.columns(2)
    yellow = ref_col1.number_input("Gialli medi", 0.0, 15.0, 4.5, 0.1)
    fouls = ref_col2.number_input("Falli medi", 0.0, 60.0, 24.0, 0.5)
    text = ""

col1, col2 = st.columns(2)
with col1:
    simulations = st.number_input("Simulazioni Monte Carlo", min_value=1_000, max_value=200_000, value=50_000, step=1_000)
with col2:
    seed = st.number_input("Seed riproducibile", min_value=0, value=42, step=1)

st.subheader("Quote opzionali e analisi valore")
st.caption("Inserisci solo quote decimali. I mercati senza quota non vengono valutati finanziariamente.")
odds_input = {}
odds_cols = st.columns(4)
for column, market in zip(odds_cols, ("1", "1X", "X2", "Over 2.5 gol")):
    value = column.number_input(market, min_value=0.0, value=0.0, step=0.01, key=f"odd_{market}")
    if value > 1.0:
        odds_input[market] = value
extra_cols = st.columns(4)
for column, market in zip(extra_cols, ("Under 2.5 gol", "Multigol 2-4", "Over 8.5 corner", "Over 4.5 cartellini")):
    value = column.number_input(market, min_value=0.0, value=0.0, step=0.01, key=f"odd_{market}")
    if value > 1.0:
        odds_input[market] = value

if st.button("Esegui simulazione", type="primary", use_container_width=True):
    try:
        if input_mode == "Copia-incolla":
            parsed = parse_match_input(text)
        else:
            parsed = MatchInput(home, away, ParsedReferee(yellow, fouls))
        config = config_from_input(parsed, simulations=int(simulations), seed=int(seed))
        config = config.__class__(**{**config.__dict__, "odds": odds_input})
        result = simulate_match(config)
        st.session_state["result"] = result
        st.session_state["warnings"] = parsed.warnings
    except MatchInputError as exc:
        st.error(str(exc))

if st.session_state.get("warnings"):
    st.warning("Fallback applicati: " + " · ".join(st.session_state["warnings"]))

def _card(
    eyebrow: str,
    label: str,
    market: dict[str, float | int],
    financial: dict[str, dict[str, float | bool]],
) -> None:
    probability = float(market["percentage"])
    quote = financial.get("odds")
    implied = financial.get("implied_probability_pct")
    ev = financial.get("ev_pct")
    if quote is None:
        comparison = "Quota: non inserita"
        badge = '<span class="badge neutral">SOLO MODELLO</span>'
    else:
        comparison = f"Quota {float(quote):.2f} · Implicita {float(implied):.2f}%"
        badge_class = "positive" if float(ev) > 0 else "neutral"
        badge_text = f"VALORE +{float(ev):.2f}%" if float(ev) > 0 else f"EDGE {float(ev):.2f}%"
        badge = f'<span class="badge {badge_class}">{badge_text}</span>'
    st.markdown(
        f"""
        <div class="score-card">
          <div class="eyebrow">{eyebrow}</div>
          <div class="market">{label}</div>
          <div class="prob">{probability:.2f}%</div>
          <div class="meta">Score Modello · {comparison}</div>
          {badge}
        </div>
        """,
        unsafe_allow_html=True,
    )


def _cards_section(
    title: str,
    items: dict[str, dict[str, float | int]],
    labels: dict[str, str],
    event_names: dict[str, str],
    financial_rows: dict[str, dict[str, float | bool]],
    columns: int = 3,
) -> None:
    st.markdown(f'<div class="section-kicker">{title}</div>', unsafe_allow_html=True)
    entries = list(items.items())
    for start in range(0, len(entries), columns):
        row = entries[start:start + columns]
        cols = st.columns(columns)
        for column, (key, market) in zip(cols, row):
            with column:
                _card(title, labels.get(key, key), market, financial_rows.get(event_names.get(key, ""), {}))


result = st.session_state.get("result")
if result:
    model = result["model"]
    summary = result["summary"]
    st.subheader("Score-style match center")
    metrics = st.columns(5)
    metrics[0].metric("Casa λ", model["lambda"])
    metrics[1].metric("Ospite μ", model["mu"])
    metrics[2].metric("Score modale", f'{summary["modal_score"]["home"]} - {summary["modal_score"]["away"]}')
    metrics[3].metric("Quota score modale", f'{summary["modal_score"]["share_pct"]}%')
    metrics[4].metric("Affidabilità campionaria", f'{summary["reliability"]["index_pct"]}%')

    financial_rows = {row["market"]: row for row in result["financial"]["markets"]}
    tabs = st.tabs(["Esito", "Gol", "Goal / Multigol", "Corner", "Cartellini", "Dashboard"])
    with tabs[0]:
        _cards_section(
            "1X2 finale",
            result["markets"]["1x2"],
            {"1": "Vittoria Casa", "X": "Pareggio", "2": "Vittoria Ospite"},
            {"1": "1", "X": "X", "2": "2"},
            financial_rows,
        )
        _cards_section(
            "1X2 primo tempo",
            result["markets"]["first_half_1x2"],
            {"1": "Casa 1° tempo", "X": "Pareggio 1° tempo", "2": "Ospite 1° tempo"},
            {},
            financial_rows,
        )
    with tabs[1]:
        _cards_section(
            "Over / Under gol",
            result["markets"]["over_under"],
            {key: key.replace("_", " ") for key in result["markets"]["over_under"]},
            {key: f"{key.replace('_', ' ').replace('Over ', 'Over ').replace('Under ', 'Under ')} gol" for key in result["markets"]["over_under"]},
            financial_rows,
        )
    with tabs[2]:
        _cards_section(
            "Goal / No Goal",
            result["markets"]["goal_no_goal"],
            {"Goal": "Entrambe le squadre segnano", "No_Goal": "No Goal"},
            {"Goal": "Goal", "No_Goal": "No Goal"},
            financial_rows,
        )
        _cards_section(
            "Multigol",
            result["markets"]["multigol"],
            {key: f"Multigol {key}" for key in result["markets"]["multigol"]},
            {key: f"Multigol {key}" for key in result["markets"]["multigol"]},
            financial_rows,
        )
    with tabs[3]:
        corner_labels = {key: key.replace("_", " ") for key in result["markets"]["corners"] if key != "mean"}
        _cards_section(
            f"Calci d'angolo · media {result['markets']['corners']['mean']}",
            {key: value for key, value in result["markets"]["corners"].items() if key != "mean"},
            corner_labels,
            {key: f"{key.replace('_', ' ')} corner" for key in corner_labels},
            financial_rows,
        )
    with tabs[4]:
        card_labels = {key: key.replace("_", " ") for key in result["markets"]["cards"] if key != "mean"}
        _cards_section(
            f"Cartellini · media {result['markets']['cards']['mean']}",
            {key: value for key, value in result["markets"]["cards"].items() if key != "mean"},
            card_labels,
            {key: f"{key.replace('_', ' ')} cartellini" for key in card_labels},
            financial_rows,
        )
    with tabs[5]:
        st.caption("Probabilità e confronto tra forza delle squadre")
        chart_col1, chart_col2 = st.columns(2)
        with chart_col1:
            st.bar_chart(pd.DataFrame({"Probabilità": [result["markets"]["1x2"][key]["percentage"] for key in ("1", "X", "2")]}, index=["1", "X", "2"]))
        with chart_col2:
            goals = result["dashboard"]["goals_distribution"]
            st.line_chart(pd.DataFrame({"Casa": goals["home"], "Ospite": goals["away"]}, index=goals["goals"]))
        strength = result["dashboard"]["strength_comparison"]
        st.bar_chart(pd.DataFrame({"Casa": strength["home"], "Ospite": strength["away"]}, index=strength["labels"]))
        st.caption(summary["reliability"]["warning"])

    st.subheader("Schedina mista")
    st.write(result["smart_combo"]["message"])
    if result["smart_combo"].get("recommendation"):
        st.dataframe(pd.DataFrame([result["smart_combo"]["recommendation"]]), use_container_width=True)
    else:
        st.info(result["smart_combo"]["message"])

    st.subheader("Value bet e rischio")
    if result["financial"]["markets"]:
        st.dataframe(pd.DataFrame(result["financial"]["markets"]), use_container_width=True)
    else:
        st.info("Nessuna quota valida inserita.")
    st.caption(result["financial"]["risk_note"])

    st.subheader("Sintesi statistica del modello")
    st.write(result["statistical_report"])
    st.subheader("IA interattiva: lettura dei numeri")
    question = st.selectbox(
        "Seleziona una domanda",
        ("Qual è l'esito più frequente?", "Il modello vede una partita da Over 2.5?", "Qual è il rischio principale?"),
    )
    if question == "Qual è l'esito più frequente?":
        one_x_two = result["markets"]["1x2"]
        best = max(one_x_two, key=lambda key: one_x_two[key]["percentage"])
        st.info(f"Il mercato più frequente è {best} con {one_x_two[best]['percentage']:.2f}% sui campioni.")
    elif question == "Il modello vede una partita da Over 2.5?":
        over = result["markets"]["over_under"]["Over_2.5"]["percentage"]
        st.info(f"Over 2.5: {over:.2f}%. La risposta è descrittiva; non equivale a una raccomandazione.")
    else:
        st.info(
            f"Il rischio principale è l'incertezza del campione: l'indice campionario è "
            f"{result['summary']['reliability']['index_pct']:.2f}% e non valuta la qualità degli input."
        )

    with st.expander("Audit del calcolo"):
        st.json({"model": model, "input": result["input"], "confidence_intervals_95": summary["confidence_intervals_95"]})
