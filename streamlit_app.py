"""Minimal on-demand Streamlit interface."""

import pandas as pd
import streamlit as st

from engine import config_from_input, simulate_match
from market_catalog import MARKET_GROUPS, definitions_for_group
from parser import MatchInputError, MatchInput, ParsedTeam, parse_match_input


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
    .score-card .confidence { color: #d6e3f5; font-size: .78rem; font-weight: 650; }
    .score-card .badge { display: inline-block; border-radius: 999px; padding: 4px 9px; margin-top: 9px; font-size: .7rem; font-weight: 750; }
    .score-card .positive { color: #b8f7d1; background: #124b38; }
    .score-card .negative { color: #ffd0d0; background: #632b35; }
    .score-card .neutral { color: #c2ccdb; background: #29374c; }
    .section-kicker { color: #6f83a2; font-weight: 750; letter-spacing: .08em; text-transform: uppercase; font-size: .78rem; margin: 18px 0 8px; }
    .input-card-title { color: #f4f7fb; font-size: 1.15rem; font-weight: 750; margin-bottom: 2px; }
    .input-card-subtitle { color: #93a4bf; font-size: .82rem; margin-bottom: 12px; }
    div[data-testid="stVerticalBlockBorderWrapper"] {
        border-color: #2b3b55;
        border-radius: 16px;
        background: linear-gradient(145deg, rgba(23,34,53,.78), rgba(16,24,39,.78));
    }
    div[data-testid="stVerticalBlockBorderWrapper"] > div { padding: 0.85rem 1rem; }
    div[data-testid="stRadio"] label, div[data-testid="stNumberInput"] label,
    div[data-testid="stSlider"] label, div[data-testid="stTextInput"] label,
    div[data-testid="stTextArea"] label { color: #c7d3e5; font-weight: 600; }
    </style>
    """,
    unsafe_allow_html=True,
)
st.title("Motore on-demand")
st.caption("Dashboard analitica senza calendario o database: input dichiarato, calcolo riproducibile e quote opzionali.")

if "input_text" not in st.session_state:
    st.session_state["input_text"] = EXAMPLE

def _team_block(team: ParsedTeam, label: str) -> str:
    return (
        f"{label.upper()}: {team.name}\n"
        f"Attacco: {team.attack:.2f} | Difesa: {team.defense:.2f} | Elo: {int(team.elo)} | "
        f"Forma: {team.form} | xG Fatti: {team.xg_for:.2f} | xG Subiti: {team.xg_against:.2f} | "
        f"Corner pro/sub: {team.corners_for:.2f}/{team.corners_against:.2f} | "
        f"Cartellini pro: {team.cards_for:.2f}"
    )


with st.container(border=True):
    st.markdown('<div class="input-card-title">Configurazione partita</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="input-card-subtitle">Scegli il flusso più rapido: incolla i dati oppure costruisci la partita campo per campo.</div>',
        unsafe_allow_html=True,
    )
    input_mode = st.radio("Modalità input", ["Copia-incolla", "Crea partita"], horizontal=True, key="input_mode")
if input_mode == "Copia-incolla":
    with st.container(border=True):
        st.markdown('<div class="input-card-title">Input dichiarato</div>', unsafe_allow_html=True)
        st.markdown('<div class="input-card-subtitle">Il testo viene passato al parser senza dati esterni o valori nascosti.</div>', unsafe_allow_html=True)
        text = st.text_area(
            "Blocco CASA / OSPITE / ARBITRO",
            key="input_text",
            height=260,
            help="Usa il formato documentato: i campi obbligatori sono nome, attacco, difesa, Elo, forma e xG.",
        )
else:
    st.markdown('<div class="section-kicker">Builder guidato</div>', unsafe_allow_html=True)
    home_col, away_col = st.columns(2, gap="medium")

    def guided_team(label: str, key: str, defaults: tuple) -> ParsedTeam:
        with (home_col if key == "home" else away_col), st.container(border=True):
            st.markdown(f'<div class="input-card-title">⚽ {label}</div>', unsafe_allow_html=True)
            st.markdown('<div class="input-card-subtitle">Parametri di forza e produzione</div>', unsafe_allow_html=True)
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
    with st.container(border=True):
        st.markdown('<div class="input-card-title">🟨 Profilo arbitrale</div>', unsafe_allow_html=True)
        st.markdown('<div class="input-card-subtitle">Impatto disciplinare medio usato nel modello.</div>', unsafe_allow_html=True)
        ref_col1, ref_col2 = st.columns(2)
        yellow = ref_col1.number_input("Gialli medi", 0.0, 15.0, 4.5, 0.1, key="guided_yellow")
        fouls = ref_col2.number_input("Falli medi", 0.0, 60.0, 24.0, 0.5, key="guided_fouls")
    generated_text = (
        f"{_team_block(home, 'Casa')}\n\n{_team_block(away, 'Ospite')}\n\n"
        f"ARBITRO: Gialli medi {yellow:.1f} | Falli medi {fouls:.1f}"
    )
    with st.container(border=True):
        st.markdown('<div class="input-card-title">Anteprima input motore</div>', unsafe_allow_html=True)
        st.markdown('<div class="input-card-subtitle">Aggiornata automaticamente a ogni modifica dei campi.</div>', unsafe_allow_html=True)
        st.code(generated_text, language="text")
        if st.button("Usa questo blocco nel copia-incolla", use_container_width=True, key="use_generated_input"):
            st.session_state["input_text"] = generated_text
            st.session_state["input_mode"] = "Copia-incolla"
            st.rerun()
    text = generated_text

parsed_preview: MatchInput | None = None
parse_error: str | None = None
try:
    parsed_preview = parse_match_input(text)
except MatchInputError as exc:
    parse_error = str(exc)

with st.expander("🔍 Diagnostica Parser & Quote", expanded=True):
    if parsed_preview is None:
        st.error(f"Parser non pronto: {parse_error}")
        st.caption("Completa i campi obbligatori per visualizzare i dati estratti.")
    else:
        st.caption("Anteprima live del risultato del parser sul blocco attualmente in input.")
        team_columns = st.columns(2)
        for column, label, team in (
            (team_columns[0], "Casa", parsed_preview.home),
            (team_columns[1], "Ospite", parsed_preview.away),
        ):
            with column:
                st.markdown(f"**{label}: {team.name}**")
                st.dataframe(
                    pd.DataFrame(
                        {
                            "Campo": ["Elo", "xG fatti", "xG subiti", "Forma", "Attacco", "Difesa", "Corner pro/sub", "Cartellini pro"],
                            "Valore": [
                                team.elo,
                                team.xg_for,
                                team.xg_against,
                                team.form,
                                team.attack,
                                team.defense,
                                f"{team.corners_for:.2f} / {team.corners_against:.2f}",
                                team.cards_for,
                            ],
                        }
                    ),
                    hide_index=True,
                    use_container_width=True,
                )
        referee_col, odds_col = st.columns(2)
        with referee_col:
            st.markdown("**Arbitro**")
            st.dataframe(
                pd.DataFrame(
                    {
                        "Campo": ["Gialli medi", "Falli medi"],
                        "Valore": [parsed_preview.referee.yellow_avg, parsed_preview.referee.fouls_avg],
                    }
                ),
                hide_index=True,
                use_container_width=True,
            )
        with odds_col:
            st.markdown(f"**Quote valide lette ({len(parsed_preview.odds)})**")
            if parsed_preview.odds:
                st.dataframe(
                    pd.DataFrame(
                        [{"Chiave": key, "Quota": value} for key, value in parsed_preview.odds.items()]
                    ),
                    hide_index=True,
                    use_container_width=True,
                )
            else:
                st.info("Nessuna quota valida nel testo.")
        if parsed_preview.warnings:
            st.warning("Warning e fallback: " + " · ".join(parsed_preview.warnings))
        else:
            st.success("Nessun warning: tutti i campi letti sono validi.")

with st.container(border=True):
    st.markdown('<div class="input-card-title">Parametri simulazione</div>', unsafe_allow_html=True)
    st.markdown('<div class="input-card-subtitle">Controlla precisione e riproducibilità del calcolo.</div>', unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    with col1:
        simulations = st.number_input("Simulazioni Monte Carlo", min_value=1_000, max_value=200_000, value=100000, step=1_000)
    with col2:
        seed = st.number_input("Seed riproducibile", min_value=0, value=42, step=1)

with st.container(border=True):
    st.markdown('<div class="input-card-title">Quote e analisi valore</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="input-card-subtitle">Il testo viene importato automaticamente. '
        'Ogni campo valorizzato qui sotto sovrascrive la quota letta; lascia 0 per non inserirla.</div>',
        unsafe_allow_html=True,
    )
    quote_source = parsed_preview.odds if parsed_preview else {}
    quote_editor_token = str(abs(hash(text)))
    quote_categories = {
        "Esiti": ("1x2", "double_chance", "draw_no_bet", "first_half_1x2", "first_half_double_chance", "second_half_1x2", "second_half_double_chance"),
        "Goal": ("goal_no_goal", "first_half_goal_no_goal", "over_under", "first_half_over_under", "team_goals", "team_scoring"),
        "Multigol e somme": ("multigol_complete", "team_multigol", "goal_sums"),
        "Corner": ("corners", "corner_1x2", "team_corners"),
        "Cartellini": ("cards", "card_1x2", "team_cards"),
        "Combo": ("combos", "both_teams"),
    }
    odds_input: dict[str, float] = {}
    quote_tabs = st.tabs(list(quote_categories))
    for tab, groups in zip(quote_tabs, quote_categories.values()):
        with tab:
            for group in groups:
                definitions = definitions_for_group(group)
                if not definitions:
                    continue
                with st.expander(group.replace("_", " ").title(), expanded=group in {"1x2", "over_under"}):
                    for start in range(0, len(definitions), 3):
                        columns = st.columns(3)
                        for column, definition in zip(columns, definitions[start:start + 3]):
                            current = float(quote_source.get(definition.event_key, 0.0))
                            value = column.number_input(
                                definition.label,
                                min_value=0.0,
                                value=current,
                                step=0.01,
                                format="%.2f",
                                key=f"odd_{quote_editor_token}_{definition.key}",
                                help=f"Chiave motore: {definition.event_key}",
                            )
                            if value > 1.0:
                                odds_input[definition.event_key] = float(value)

if st.button("Esegui simulazione", type="primary", use_container_width=True):
    try:
        if parsed_preview is None:
            raise MatchInputError(parse_error or "Input non valido")
        parsed = parsed_preview
        config = config_from_input(parsed, simulations=int(simulations), seed=int(seed))
        config = config.__class__(**{**config.__dict__, "odds": {**parsed.odds, **odds_input}})
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
    market: dict,
    financial: dict,
) -> None:
    probability = float(market["percentage"])
    interval = market.get("confidence_interval_95", [0.0, 0.0])
    reliability = float(market.get("reliability_pct", 0.0))
    quote = financial.get("odds")
    implied = financial.get("implied_probability_pct")
    ev = financial.get("ev_pct")
    stake = financial.get("recommended_stake_pct")
    push = financial.get("push_probability_pct")
    fair_odds = market.get("fair_odds")
    if quote is None:
        comparison = "Quota: non inserita"
        badge = '<span class="badge neutral">SOLO MODELLO</span>'
    else:
        comparison = f"Quota {float(quote):.2f} · Implicita {float(implied):.2f}%"
        badge_class = "positive" if float(ev) > 0 else "negative"
        badge_text = f"VALORE +{float(ev):.2f}%" if float(ev) > 0 else f"EV {float(ev):.2f}%"
        badge = f'<span class="badge {badge_class}">{badge_text}</span>'
    fair_meta = f" · Quota equa {float(fair_odds):.3f}" if fair_odds is not None else ""
    push_meta = f" · Push {float(push):.2f}%" if push is not None and float(push) > 0 else ""
    stake_meta = f" · Quarter-Kelly {float(stake):.2f}% bankroll" if stake is not None else ""
    st.markdown(
        f"""
        <div class="score-card">
          <div class="eyebrow">{eyebrow}</div>
          <div class="confidence">Affidabilità {reliability:.2f}% · Wilson 95% [{float(interval[0]):.2f}%, {float(interval[1]):.2f}%]</div>
          <div class="market">{label}</div>
          <div class="prob">{probability:.2f}%</div>
          <div class="meta">Score Modello · {comparison}{fair_meta}{push_meta}{stake_meta}</div>
          {badge}
        </div>
        """,
        unsafe_allow_html=True,
    )


def _cards_section(
    title: str,
    items: dict[str, dict],
    labels: dict[str, str],
    event_names: dict[str, str],
    financial_rows: dict[str, dict],
    columns: int = 3,
) -> None:
    st.markdown(f'<div class="section-kicker">{title}</div>', unsafe_allow_html=True)
    rows = []
    for key, market in items.items():
        event_name = event_names.get(key, key)
        financial = financial_rows.get(event_name, financial_rows.get(key.replace("_", " "), {}))
        interval = market.get("confidence_interval_95", [0.0, 0.0])
        quote = financial.get("odds")
        ev = financial.get("ev_pct")
        stake = financial.get("recommended_quarter_kelly_pct")
        rows.append(
            {
                "Mercato": labels.get(key, key),
                "Quota": f"{float(quote):.2f}" if quote is not None else "—",
                "Probabilità": f'{float(market["percentage"]):.2f}%',
                "Wilson 95%": f"[{float(interval[0]):.2f}%, {float(interval[1]):.2f}%]",
                "EV": f"{float(ev):+.2f}%" if ev is not None else "—",
                "Badge Valore": (
                    f"VALORE +{float(ev):.2f}%" if ev is not None and float(ev) > 0
                    else "NESSUN VALORE" if ev is not None
                    else "SOLO MODELLO"
                ),
                "Quarter-Kelly": f"{float(stake):.2f}%" if stake is not None else "—",
            }
        )
    if rows:
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)


def _catalog_cards_section(group: str, result: dict, financial_rows: dict) -> None:
    definitions = definitions_for_group(group)
    catalog_group = result["markets"]["catalog"].get(group, {})
    entries = [
        (definition, catalog_group[definition.key])
        for definition in definitions
        if definition.key in catalog_group
    ]
    if not entries:
        return
    st.markdown(f'<div class="section-kicker">{group.replace("_", " ").title()}</div>', unsafe_allow_html=True)
    rows = []
    for definition, market in entries:
        financial = financial_rows.get(definition.event_key, {})
        interval = market.get("confidence_interval_95", [0.0, 0.0])
        quote = financial.get("odds")
        ev = financial.get("ev_pct")
        stake = financial.get("recommended_quarter_kelly_pct")
        rows.append(
            {
                "Mercato": definition.label,
                "Quota": f"{float(quote):.2f}" if quote is not None else "—",
                "Probabilità": f'{float(market["percentage"]):.2f}%',
                "Wilson 95%": f"[{float(interval[0]):.2f}%, {float(interval[1]):.2f}%]",
                "EV": f"{float(ev):+.2f}%" if ev is not None else "—",
                "Badge Valore": (
                    f"VALORE +{float(ev):.2f}%" if ev is not None and float(ev) > 0
                    else "NESSUN VALORE" if ev is not None
                    else "SOLO MODELLO"
                ),
                "Quarter-Kelly": f"{float(stake):.2f}%" if stake is not None else "—",
            }
        )
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)


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
    tabs = st.tabs([
        "Esiti & Doppia Chance",
        "Gol & Under/Over",
        "Multigol Totali & Squadra",
        "Corner",
        "Cartellini",
        "Dashboard",
        "Parziali",
        "Squadre",
        "Catalogo completo",
    ])
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
            {"1": "1 1T", "X": "X 1T", "2": "2 1T"},
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
        _cards_section(
            "Multigol completo",
            result["markets"]["multigol_complete"],
            {key: f"Multigol totale {key}" for key in result["markets"]["multigol_complete"]},
            {key: f"Multigol {key}" for key in result["markets"]["multigol_complete"]},
            financial_rows,
        )
        team_multigol_tabs = st.tabs(["Multigol Casa", "Multigol Ospite"])
        for team_tab, team_name in zip(team_multigol_tabs, ("Casa", "Ospite")):
            with team_tab:
                team_items = {
                    key: market
                    for key, market in result["markets"]["team_multigol"].items()
                    if key.startswith(f"{team_name} ")
                }
                _cards_section(
                    f"Tutte le fasce · {team_name}",
                    team_items,
                    {key: f"Multigol {key}" for key in team_items},
                    {key: f"Multigol {key}" for key in team_items},
                    financial_rows,
                )
        _cards_section(
            "Combo",
            result["markets"]["combos"],
            {key: key for key in result["markets"]["combos"]},
            {key: key for key in result["markets"]["combos"]},
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
        _cards_section(
            "1X2 corner",
            result["markets"]["corner_1x2"],
            {"1": "Più corner Casa", "X": "Parità corner", "2": "Più corner Ospite"},
            {"1": "1 corner", "X": "X corner", "2": "2 corner"},
            financial_rows,
        )
        _cards_section(
            "Corner per squadra",
            result["markets"]["team_corners"],
            {key: key.replace("_", " ") for key in result["markets"]["team_corners"]},
            {key: key.replace("_", " ") for key in result["markets"]["team_corners"]},
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
        _cards_section(
            "1X2 cartellini",
            result["markets"]["card_1x2"],
            {"1": "Più cartellini Casa", "X": "Parità cartellini", "2": "Più cartellini Ospite"},
            {"1": "1 cartellini", "X": "X cartellini", "2": "2 cartellini"},
            financial_rows,
        )
        _cards_section(
            "Cartellini per squadra",
            result["markets"]["team_cards"],
            {key: key.replace("_", " ") for key in result["markets"]["team_cards"]},
            {key: key.replace("_", " ") for key in result["markets"]["team_cards"]},
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
        st.info(f"Stabilità campionaria Wilson: {summary['reliability']['sampling_stability_pct']:.2f}%. Incertezza di modello: {summary['reliability']['model_uncertainty']}")
    with tabs[6]:
        _cards_section("1X2 e doppia chance 1° tempo", result["markets"]["first_half_1x2"], {}, {key: f"{key} 1T" for key in ("1", "X", "2")}, financial_rows)
        _cards_section("Doppia chance 1° tempo", result["markets"]["first_half_double_chance"], {}, {key: f"{key} 1T" for key in ("1X", "X2", "12")}, financial_rows)
        _cards_section("1X2 e doppia chance 2° tempo", result["markets"]["second_half_1x2"], {}, {key: f"{key} 2T" for key in ("1", "X", "2")}, financial_rows)
        _cards_section("Doppia chance 2° tempo", result["markets"]["second_half_double_chance"], {}, {key: f"{key} 2T" for key in ("1X", "X2", "12")}, financial_rows)
        _cards_section("Draw No Bet", result["markets"]["draw_no_bet"], {"Casa": "Casa DNB", "Ospite": "Ospite DNB"}, {"Casa": "Casa DNB", "Ospite": "Ospite DNB"}, financial_rows)
        _cards_section("Over / Under 1° tempo", result["markets"]["first_half_over_under"], {}, {key: f"{key.replace('_', ' ')} gol 1T" for key in result["markets"]["first_half_over_under"]}, financial_rows)
        _cards_section("Goal / No Goal 1° tempo", result["markets"]["first_half_goal_no_goal"], {"Goal": "Entrambe segnano 1° tempo", "No_Goal": "No Goal 1° tempo"}, {"Goal": "Goal 1T", "No_Goal": "No Goal 1T"}, financial_rows)
    with tabs[7]:
        _cards_section("Goal squadra", result["markets"]["team_scoring"], {"Casa segna": "Casa segna", "Casa non segna": "Casa non segna", "Ospite segna": "Ospite segna", "Ospite non segna": "Ospite non segna"}, {}, financial_rows)
        _cards_section("Goal squadra · Over / Under", result["markets"]["team_goals"], {key: key for key in result["markets"]["team_goals"]}, {key: key for key in result["markets"]["team_goals"]}, financial_rows)
        _cards_section("Somma gol esatta", result["markets"]["goal_sums"], {key: f"Somma gol {key}" for key in result["markets"]["goal_sums"]}, {key: f"Somma gol {key}" for key in result["markets"]["goal_sums"]}, financial_rows)
        _cards_section("BTTS nei tempi", result["markets"]["both_teams"], {key: key for key in result["markets"]["both_teams"]}, {}, financial_rows)
    with tabs[8]:
        st.caption("Catalogo centrale: le card sono generate dalle definizioni condivise da parser, motore e dashboard.")
        for group in MARKET_GROUPS:
            _catalog_cards_section(group, result, financial_rows)

    st.subheader("Schedina mista")
    st.write(result["smart_combo"]["message"])
    recommendation = result["smart_combo"].get("recommendation")
    if recommendation:
        combo_interval = recommendation["confidence_interval_95"]
        combo_label = " + ".join(recommendation["legs"])
        st.markdown(
            f"""
            <div class="score-card">
              <div class="eyebrow">Schedina mista · 2 leg</div>
              <div class="confidence">Affidabilità {recommendation["reliability_pct"]:.2f}% · Wilson 95% [{combo_interval[0]:.2f}%, {combo_interval[1]:.2f}%]</div>
              <div class="market">{combo_label}</div>
              <div class="prob">{recommendation["simulated_probability_pct"]:.2f}%</div>
              <div class="meta">Quota combinata {recommendation["combined_odds"]:.3f} · EV {recommendation["ev_pct"]:+.2f}% · Quarter-Kelly {recommendation["recommended_stake_pct"]:.2f}% bankroll</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.dataframe(pd.DataFrame([recommendation]), use_container_width=True)
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
