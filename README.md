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
CASA: Inter | Quota 1: 1.85
Attacco: 1.34 | Difesa: 0.78 | Elo: 1835 | Forma: W-W-D-W-W | xG Fatti: 2.15 | xG Subiti: 0.85 | Corner pro/sub: 1.25/0.95 | Cartellini pro: 0.95

OSPITE: Milan | Quota X: 3.40 | Quota 2: 4.20
Attacco: 1.22 | Difesa: 0.92 | Elo: 1765 | Forma: W-W-L-D-W | xG Fatti: 1.85 | xG Subiti: 1.10 | Corner pro/sub: 1.15/1.10 | Cartellini pro: 1.10

ARBITRO: Gialli medi 4.5 | Falli medi 24
```

Attacco e difesa sono coefficienti relativi (`1.0` = riferimento), Elo è in
punti, xG e medie arbitrali sono valori medi per partita, mentre la forma usa
solo `W`, `D`, `L`. I campi secondari mancanti ricevono un fallback neutro
esplicitamente mostrato dalla UI.

Le quote sono opzionali e possono essere aggiunte alle righe `CASA` e
`OSPITE`, ad esempio `Quota 1`, `Quota X`, `Quota 2`, `Quota Over 2.5` o
`Quota Under 3.5`. Vengono normalizzate dal parser e passate automaticamente
al motore per l'analisi Value Bet.

Il catalogo dichiarativo condiviso è in [`market_catalog.py`](./market_catalog.py):
le sue definizioni vengono usate per normalizzare le quote, validare i mercati,
materializzare il gruppo `markets["catalog"]` e generare le card del tab
Catalogo. Per i mercati DNB il risultato distingue vittoria, perdita e
rimborso (`push`); il Kelly e l'EV usano il settlement a tre esiti invece di
trattare il pareggio come una perdita.

## Modello

Il motore:

1. costruisce `lambda` e `mu` con attacco, difesa avversaria, xG, forma ed Elo;
2. applica la correzione Dixon-Coles ai punteggi `0-0`, `0-1`, `1-0`, `1-1`;
3. campiona la matrice con Monte Carlo usando il seed scelto;
4. calcola 1X2, Over/Under, Goal/No Goal, corner e cartellini;
5. mostra score modale, intervalli Wilson e il ledger dei contributi;
6. espone per ogni mercato l'intervallo Wilson 95% e l'affidabilità campionaria;
7. calcola EV e Kelly frazionato (Quarter-Kelly, 25% del Kelly pieno) per le
   Value Bet e per la Schedina Mista.

Il catalogo `result["markets"]` espone inoltre tutti i mercati richiesti,
raggruppati in esiti finali e parziali, goal e multigol, somme e combo,
corner e cartellini. Ogni voce di mercato contiene conteggio, percentuale,
intervallo Wilson 95% e indice di affidabilità; le quote fornite dall'utente
vengono analizzate con EV e Quarter-Kelly.

Il testo prodotto è una sintesi numerica nell'interfaccia, non viene chiamato
“IA” e non contiene frasi narrative generate da template.

## Gestione del rischio

L'indice di affidabilità è una misura della stabilità del campione Monte Carlo:
`100 - ampiezza dell'intervallo Wilson 95%`, limitata a `0-100`. Non misura la
qualità dei dati inseriti né la correttezza del modello. Il Kelly pieno usa
`f* = (b·p - q) / b` con `b = quota - 1`; la dashboard mostra esclusivamente
Quarter-Kelly (il 25% del valore pieno) come stake massimo indicativo del
bankroll, mai come garanzia di profitto.

Ogni card mostra inoltre la quota equa stimata dal modello (`1 / probabilità`)
anche quando non è stata inserita una quota bookmaker.

Gli intervalli Wilson e l'indice mostrato come stabilità sono riferiti alla
variabilità del campione Monte Carlo. Non sono una stima dell'incertezza dei
parametri del modello: questa richiede una distribuzione sui parametri e una
validazione out-of-sample, non ancora inclusa nell'applicazione.
