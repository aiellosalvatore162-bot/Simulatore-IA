"""Minimal on-demand Streamlit interface."""

import streamlit as st

from engine import config_from_input, simulate_match
from parser import MatchInputError, parse_match_input


EXAMPLE = """CASA: Inter
Attacco: 1.34 | Difesa: 0.78 | Elo: 1835 | Forma: W-W-D-W-W | xG Fatti: 2.15 | xG Subiti: 0.85 | Corner pro/sub: 1.25/0.95 | Cartellini pro: 0.95

OSPITE: Milan
Attacco: 1.22 | Difesa: 0.92 | Elo: 1765 | Forma: W-W-L-D-W | xG Fatti: 1.85 | xG Subiti: 1.10 | Corner pro/sub: 1.15/1.10 | Cartellini pro: 1.10

ARBITRO: Gialli medi 4.5 | Falli medi 24
"""

st.set_page_config(page_title="Simulatore IA · On-demand", page_icon="⚽", layout="wide")
st.title("Motore on-demand")
st.caption("Nessun calendario, database o report generato: solo input dichiarato e calcolo riproducibile.")

text = st.text_area("Incolla i dati della partita", value=EXAMPLE, height=260)
col1, col2 = st.columns(2)
with col1:
    simulations = st.number_input("Simulazioni Monte Carlo", min_value=1_000, max_value=200_000, value=50_000, step=1_000)
with col2:
    seed = st.number_input("Seed riproducibile", min_value=0, value=42, step=1)

if st.button("Esegui simulazione", type="primary", use_container_width=True):
    try:
        parsed = parse_match_input(text)
        config = config_from_input(parsed, simulations=int(simulations), seed=int(seed))
        result = simulate_match(config)
        st.session_state["result"] = result
        st.session_state["warnings"] = parsed.warnings
    except MatchInputError as exc:
        st.error(str(exc))

if st.session_state.get("warnings"):
    st.warning("Fallback applicati: " + " · ".join(st.session_state["warnings"]))

result = st.session_state.get("result")
if result:
    model = result["model"]
    summary = result["summary"]
    st.subheader("Risultato numerico")
    metrics = st.columns(4)
    metrics[0].metric("Casa λ", model["lambda"])
    metrics[1].metric("Ospite μ", model["mu"])
    metrics[2].metric("Score modale", f'{summary["modal_score"]["home"]} - {summary["modal_score"]["away"]}')
    metrics[3].metric("Quota score modale", f'{summary["modal_score"]["share_pct"]}%')

    st.subheader("Probabilità")
    st.dataframe(result["markets"]["1x2"], use_container_width=True)
    st.dataframe(result["markets"]["over_under"], use_container_width=True)
    st.dataframe(result["markets"]["goal_no_goal"], use_container_width=True)
    st.subheader("Corner e cartellini")
    st.json({"corners": result["markets"]["corners"], "cards": result["markets"]["cards"]})

    with st.expander("Audit del calcolo"):
        st.json({"model": model, "input": result["input"], "confidence_intervals_95": summary["confidence_intervals_95"]})
