# Simulatore Pronostici Calcistici - Architettura FastAPI & Monte Carlo Dixon-Coles (2026/2027)

Motore di pronostici calcistici basato su:
- **Simulazione Monte Carlo vettorializzata (NumPy)** a **50.000 iterazioni**.
- Distribuzione **Poisson bivariata con correzione Dixon-Coles** per i punteggi bassi (0 e 1).
- **Database relazionale SQLite (`data.db`)** con le 12 competizioni della stagione 2026/2027:
  Serie A, Premier League, Ligue 1, La Liga, Campionato Portoghese, Campionato Belga, Bundesliga, Eredivisie, Süper Lig, Champions League, Europa League, Conference League.
- **Ricalcolo dinamico**: classifica (`Standings`), rating Elo, forma recente (ultime 5 partite W-D-L) e medie xG post-partita (`updater.py`).

---

## 🚀 Avvio Rapido

### 1. Installazione dipendenze
```bash
pip install -r requirements.txt
```

### 2. Seeding del database (Stagione 2026/2027)
```bash
python seed.py
```

Il seed contiene dati dimostrativi e non deve essere usato come fonte reale. Per
sincronizzare calendario, risultati, classifiche e marcatori ufficiali, configura
le chiavi nel terminale (non inserirle nei file del progetto):

```bash
export FOOTBALL_DATA_API_KEY="..."
export FOOTBALL_DATA_SEASON="2026"
export THE_ODDS_API_KEY="..."
export THE_ODDS_API_SPORT_KEY="soccer_italy_serie_a"
curl -X POST "http://127.0.0.1:8000/api/sync?season=2026"
# In alternativa, con il server fermo:
python data_sync.py
```

Il piano gratuito di football-data.org limita le richieste al minuto. Per
sincronizzare tutte le competizioni senza superare il limite, esegui blocchi da
tre competizioni (le competizioni già sincronizzate vengono conservate):

```bash
export FOOTBALL_DATA_COMPETITIONS="SA,PL,FL1"
python data_sync.py
export FOOTBALL_DATA_COMPETITIONS="PD,PPL"
python data_sync.py
export FOOTBALL_DATA_COMPETITIONS="BL1,DED"
python data_sync.py
export FOOTBALL_DATA_COMPETITIONS="CL"
python data_sync.py
```

`football-data.org` è la fonte per calendario, risultati, classifiche e marcatori.
`The Odds API` viene usata esclusivamente per le quote; non fornisce classifiche
o marcatori. La sincronizzazione è atomica: se il piano API non consente una
competizione, i dati precedenti non vengono cancellati.

Per le competizioni non incluse nel piano `football-data.org`, il sincronizzatore
prova automaticamente SofaScore come fallback web gratuito. Se vuoi usare solo
SofaScore, puoi rimuovere temporaneamente `FOOTBALL_DATA_API_KEY`; in quel caso
la risposta riporterà `source: "SofaScore"`. SofaScore non offre un contratto API
pubblico stabile: se restituisce HTTP 403 o cambia gli endpoint, la competizione
viene segnalata in `errors` e non vengono inseriti dati inventati.

### 3. Avvio del server FastAPI
```bash
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```
- **Documentazione Swagger interattiva**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **Health check**: [http://127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health)

---

## 📡 Endpoint Principali

### 1. Simulazione con squadre da Database (`/api/simulate`)
Puoi passare direttamente `match_id` o `home_team_id` e `away_team_id` (il server preleva automaticamente forza d'attacco, difesa, fattore campo ed Elo da SQLite):

#### Chiamata POST con team_id
```bash
curl -X POST "http://127.0.0.1:8000/api/simulate" \
  -H "Content-Type: application/json" \
  -d '{
    "home_team_id": 1,
    "away_team_id": 2,
    "n_simulations": 50000
  }'
```

#### Chiamata POST per simulare un match in calendario (`match_id`)
```bash
curl -X POST "http://127.0.0.1:8000/api/simulate" \
  -H "Content-Type: application/json" \
  -d '{
    "match_id": 12,
    "n_simulations": 50000
  }'
```

#### Chiamata GET rapida
```bash
curl "http://127.0.0.1:8000/api/simulate?home_team_id=1&away_team_id=2"
```

---

### 2. Consultazione Database

| Metodo | Endpoint | Descrizione |
|---|---|---|
| `GET` | `/api/leagues` | Elenco delle 12 competizioni 2026/2027 |
| `GET` | `/api/leagues/{id}` | Dettaglio singola lega |
| `GET` | `/api/leagues/{id}/teams` | Squadre del campionato con Elo, attacco, difesa, xG e forma |
| `GET` | `/api/leagues/{id}/standings` | Classifica aggiornata con punti, vinte, perse, gol fatti, gol subiti, dr |
| `GET` | `/api/leagues/{id}/top-scorers` | Classifica marcatori e assist del campionato |
| `GET` | `/api/matches` | Calendario e risultati (`?league_id=1&status=scheduled`) |
| `GET` | `/api/matches/{id}` | Dettaglio match |

---

### 3. Conclusione Match e Ricalcolo Dinamico (`POST /api/matches/{id}/complete`)
Segna una partita come conclusa e ricalcola in automatico Classifica, Elo e Forma:
```bash
curl -X POST "http://127.0.0.1:8000/api/matches/12/complete" \
  -H "Content-Type: application/json" \
  -d '{
    "home_goals": 2,
    "away_goals": 1,
    "home_xg": 1.95,
    "away_xg": 1.15
  }'
```

---

## 📊 I 15 Mercati Calcolati

Per ciascun mercato vengono restituiti sia `count` esatto su 50.000 simulazioni che `percentage`:
1. **1X2 finale** (`1`, `X`, `2`)
2. **1X2 primo tempo** (`1`, `X`, `2`)
3. **Over / Under finale** (0.5, 1.5, 2.5, 3.5, 4.5)
4. **Over / Under primo tempo** (0.5, 1.5, 2.5, 3.5, 4.5)
5. **Goal / No Goal finale** (`Goal`, `No_Goal`)
6. **Goal / No Goal primo tempo** (`Goal`, `No_Goal`)
7. **Cartellini**: media attesa, Over/Under (3.5, 4.5, 5.5) e fasce (`0-3`, `4-5`, `6+`)
8. **Calci d'angolo**: media attesa, Over/Under (8.5, 9.5, 10.5, 11.5) e fasce (`0-8`, `9-11`, `12+`)
9. **Multigol partita** da 0-1 a 3-6
10. **Multigol casa** da 0-1 a 3-6
11. **Multigol ospite** da 0-1 a 3-6
12. **Multigol casa + Multigol ospite** (es. `Casa_1_2_e_Ospite_0_1`, ecc.)
13. **Multigol 1° tempo + Multigol 2° tempo** (es. `1T_0_1_e_2T_1_2`, ecc.)
14. **Over squadra casa** da 0.5 a 3.5
15. **Over squadra ospite** da 0.5 a 3.5

---

## 🧠 Convergenza e Sinergia Statistica

Il modulo analizza le co-occorrenze su 50.000 simulazioni calcolando probabilità congiunta $P(A \cap B)$, coefficiente di **Lift** e formulando la spiegazione testuale motivata in linguaggio naturale (`assistant_explanation`).

---

## 🧪 Esecuzione Test Automatici
```bash
pytest test_engine.py test_database.py
```
