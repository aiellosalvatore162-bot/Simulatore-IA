# Simulatore-IA: motore on-demand

Applicazione Streamlit per analizzare una singola partita a partire da un
blocco di testo dichiarato dall'utente. Non usa calendari, database, seed
automatici, quote sintetiche o report narrativi preconfezionati.

## Avvio

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

## Input

```text
CASA: Inter
Attacco: 1.34 | Difesa: 0.78 | Elo: 1835 | Forma: W-W-D-W-W | xG Fatti: 2.15 | xG Subiti: 0.85 | Corner pro/sub: 1.25/0.95 | Cartellini pro: 0.95

OSPITE: Milan
Attacco: 1.22 | Difesa: 0.92 | Elo: 1765 | Forma: W-W-L-D-W | xG Fatti: 1.85 | xG Subiti: 1.10 | Corner pro/sub: 1.15/1.10 | Cartellini pro: 1.10

ARBITRO: Gialli medi 4.5 | Falli medi 24
```

Attacco e difesa sono coefficienti relativi (`1.0` = riferimento), Elo è in
punti, xG e medie arbitrali sono valori medi per partita, mentre la forma usa
solo `W`, `D`, `L`. I campi secondari mancanti ricevono un fallback neutro
esplicitamente mostrato dalla UI.

## Modello

Il motore:

1. costruisce `lambda` e `mu` con attacco, difesa avversaria, xG, forma ed Elo;
2. applica la correzione Dixon-Coles ai punteggi `0-0`, `0-1`, `1-0`, `1-1`;
3. campiona la matrice con Monte Carlo usando il seed scelto;
4. calcola 1X2, Over/Under, Goal/No Goal, corner e cartellini;
5. mostra score modale, intervalli Wilson e il ledger dei contributi.

Il testo prodotto è una sintesi numerica nell'interfaccia, non viene chiamato
“IA” e non contiene frasi narrative generate da template.
