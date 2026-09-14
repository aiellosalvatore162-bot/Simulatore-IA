"""
Modulo seed.py - Popolamento del database SQLite con dati realistici per la stagione 2026/2027.
Include tutte le 12 competizioni richieste:
1. Serie A
2. Premier League
3. Ligue 1
4. La Liga
5. Campionato Portoghese
6. Campionato Belga
7. Bundesliga
8. Eredivisie
9. Süper Lig
10. Champions League
11. Europa League
12. Conference League

Evita l'appiattimento di valori, inserendo rating Elo, xG e fattori d'attacco/difesa
calibrati sulle reali gerarchie europee del 2026/2027.
"""

from pathlib import Path
import sqlite3
from typing import Optional
from database import DB_FILE, init_db, get_db_connection
from updater import recalculate_league_standings


def seed_database(db_path: Optional[str | Path] = None) -> None:
    """Esegue il seeding completo delle 12 competizioni, squadre, calendari e marcatori."""
    target_path = db_path or DB_FILE
    
    # Se il database esiste già ed è popolato, lo azzeriamo per garantire freschezza e coerenza
    init_db(target_path)
    conn = get_db_connection(target_path)
    
    with conn:
        cur = conn.cursor()
        # Pulizia preventiva in ordine corretto
        cur.execute("DELETE FROM simulation_history;")
        cur.execute("DELETE FROM h2h_matches;")
        cur.execute("DELETE FROM top_scorers;")
        cur.execute("DELETE FROM matches;")
        cur.execute("DELETE FROM standings;")
        cur.execute("DELETE FROM teams;")
        cur.execute("DELETE FROM leagues;")
        try:
            cur.execute("DELETE FROM sqlite_sequence;")
        except Exception:
            pass

        # 1. LEAGUES
        leagues_data = [
            (1, "Serie A", "Italia", "domestic", "https://assets.football.db/leagues/serie_a.png"),
            (2, "Premier League", "Inghilterra", "domestic", "https://assets.football.db/leagues/premier_league.png"),
            (3, "Ligue 1", "Francia", "domestic", "https://assets.football.db/leagues/ligue_1.png"),
            (4, "La Liga", "Spagna", "domestic", "https://assets.football.db/leagues/la_liga.png"),
            (5, "Campionato Portoghese", "Portogallo", "domestic", "https://assets.football.db/leagues/liga_portugal.png"),
            (6, "Campionato Belga", "Belgio", "domestic", "https://assets.football.db/leagues/pro_league.png"),
            (7, "Bundesliga", "Germania", "domestic", "https://assets.football.db/leagues/bundesliga.png"),
            (8, "Eredivisie", "Olanda", "domestic", "https://assets.football.db/leagues/eredivisie.png"),
            (9, "Süper Lig", "Turchia", "domestic", "https://assets.football.db/leagues/super_lig.png"),
            (10, "Champions League", "Europa", "cup", "https://assets.football.db/leagues/champions_league.png"),
            (11, "Europa League", "Europa", "cup", "https://assets.football.db/leagues/europa_league.png"),
            (12, "Conference League", "Europa", "cup", "https://assets.football.db/leagues/conference_league.png"),
        ]

        cur.executemany(
            "INSERT INTO leagues (id, name, country, type, logo) VALUES (?, ?, ?, ?, ?)",
            leagues_data
        )

        # 2. TEAMS PER LEAGUE (Valori non appiattiti: attacco 0.8-1.5, difesa 0.75-1.35, elo 1450-1900)
        # (league_id, name, logo, elo, attack, defense, home_adv, recent_form, xg_for, xg_against, matches_played, cards_factor, corners_factor)
        teams_data = [
            # SERIE A (league_id = 1)
            (1, "Inter", "https://assets.football.db/teams/inter.png", 1835.0, 1.34, 0.78, 1.15, "W-W-D-W-W", 2.15, 0.85, 3, 0.95, 1.25),
            (1, "Juventus", "https://assets.football.db/teams/juventus.png", 1775.0, 1.18, 0.80, 1.15, "W-D-W-W-D", 1.70, 0.90, 3, 1.05, 1.05),
            (1, "Milan", "https://assets.football.db/teams/milan.png", 1765.0, 1.22, 0.92, 1.15, "W-W-L-D-W", 1.85, 1.10, 3, 1.10, 1.15),
            (1, "Napoli", "https://assets.football.db/teams/napoli.png", 1785.0, 1.25, 0.82, 1.18, "W-W-W-D-W", 1.95, 0.95, 3, 1.00, 1.10),
            (1, "Atalanta", "https://assets.football.db/teams/atalanta.png", 1770.0, 1.30, 0.94, 1.16, "W-L-W-W-W", 2.05, 1.15, 3, 1.05, 1.30),
            (1, "Roma", "https://assets.football.db/teams/roma.png", 1720.0, 1.12, 0.96, 1.15, "D-W-L-W-D", 1.55, 1.15, 3, 1.20, 1.05),
            (1, "Lazio", "https://assets.football.db/teams/lazio.png", 1715.0, 1.14, 0.98, 1.15, "W-L-D-W-D", 1.60, 1.20, 3, 1.25, 1.00),
            (1, "Fiorentina", "https://assets.football.db/teams/fiorentina.png", 1690.0, 1.10, 1.00, 1.14, "D-D-W-L-W", 1.50, 1.25, 3, 1.10, 1.10),
            (1, "Bologna", "https://assets.football.db/teams/bologna.png", 1680.0, 1.05, 0.98, 1.14, "W-D-D-L-D", 1.40, 1.15, 3, 1.00, 1.00),
            (1, "Torino", "https://assets.football.db/teams/torino.png", 1640.0, 0.95, 1.02, 1.12, "L-D-W-D-L", 1.15, 1.25, 3, 1.15, 0.90),
            (1, "Genoa", "https://assets.football.db/teams/genoa.png", 1610.0, 0.92, 1.08, 1.14, "L-W-L-D-L", 1.10, 1.35, 3, 1.20, 0.90),
            (1, "Monza", "https://assets.football.db/teams/monza.png", 1580.0, 0.88, 1.15, 1.10, "L-L-D-L-D", 0.95, 1.45, 3, 1.05, 0.85),
            (1, "Udinese", "https://assets.football.db/teams/udinese.png", 1605.0, 0.94, 1.10, 1.12, "D-L-W-L-D", 1.15, 1.35, 3, 1.15, 0.95),
            (1, "Cagliari", "https://assets.football.db/teams/cagliari.png", 1570.0, 0.86, 1.20, 1.15, "L-D-L-W-L", 0.95, 1.50, 3, 1.20, 0.85),
            (1, "Parma", "https://assets.football.db/teams/parma.png", 1590.0, 0.98, 1.18, 1.12, "D-W-L-L-D", 1.20, 1.45, 3, 1.10, 0.95),
            (1, "Como", "https://assets.football.db/teams/como.png", 1585.0, 0.96, 1.16, 1.12, "L-D-D-W-L", 1.15, 1.40, 3, 1.05, 0.95),
            (1, "Hellas Verona", "https://assets.football.db/teams/verona.png", 1560.0, 0.85, 1.22, 1.12, "L-L-L-W-D", 0.90, 1.55, 3, 1.25, 0.85),
            (1, "Lecce", "https://assets.football.db/teams/lecce.png", 1550.0, 0.82, 1.24, 1.12, "L-D-L-L-D", 0.85, 1.60, 3, 1.20, 0.80),
            (1, "Empoli", "https://assets.football.db/teams/empoli.png", 1565.0, 0.84, 1.18, 1.12, "D-L-D-L-W", 0.90, 1.45, 3, 1.10, 0.85),
            (1, "Venezia", "https://assets.football.db/teams/venezia.png", 1540.0, 0.80, 1.28, 1.10, "L-L-D-L-L", 0.80, 1.65, 3, 1.15, 0.80),

            # PREMIER LEAGUE (league_id = 2)
            (2, "Manchester City", "https://assets.football.db/teams/mancity.png", 1895.0, 1.48, 0.74, 1.14, "W-W-W-W-D", 2.45, 0.75, 3, 0.85, 1.45),
            (2, "Arsenal", "https://assets.football.db/teams/arsenal.png", 1865.0, 1.40, 0.75, 1.15, "W-W-D-W-W", 2.30, 0.78, 3, 0.95, 1.35),
            (2, "Liverpool", "https://assets.football.db/teams/liverpool.png", 1860.0, 1.42, 0.78, 1.18, "W-W-W-L-W", 2.35, 0.85, 3, 0.90, 1.40),
            (2, "Chelsea", "https://assets.football.db/teams/chelsea.png", 1765.0, 1.25, 0.98, 1.14, "W-D-W-L-W", 1.90, 1.20, 3, 1.30, 1.15),
            (2, "Aston Villa", "https://assets.football.db/teams/astonvilla.png", 1755.0, 1.22, 0.96, 1.15, "W-L-W-W-D", 1.80, 1.15, 3, 1.10, 1.10),
            (2, "Tottenham", "https://assets.football.db/teams/tottenham.png", 1745.0, 1.26, 1.05, 1.14, "L-W-D-W-L", 1.95, 1.35, 3, 1.20, 1.25),
            (2, "Newcastle", "https://assets.football.db/teams/newcastle.png", 1750.0, 1.20, 0.95, 1.16, "W-D-L-W-W", 1.75, 1.10, 3, 1.15, 1.15),
            (2, "Manchester United", "https://assets.football.db/teams/manunited.png", 1730.0, 1.15, 1.04, 1.15, "L-W-D-L-W", 1.60, 1.30, 3, 1.20, 1.10),
            (2, "Brighton", "https://assets.football.db/teams/brighton.png", 1710.0, 1.16, 1.08, 1.12, "D-W-L-W-D", 1.65, 1.30, 3, 1.10, 1.10),
            (2, "West Ham", "https://assets.football.db/teams/westham.png", 1680.0, 1.08, 1.12, 1.13, "L-D-W-L-D", 1.40, 1.40, 3, 1.15, 1.00),
            (2, "Bournemouth", "https://assets.football.db/teams/bournemouth.png", 1665.0, 1.05, 1.10, 1.12, "W-L-D-D-W", 1.35, 1.35, 3, 1.20, 1.05),
            (2, "Fulham", "https://assets.football.db/teams/fulham.png", 1660.0, 1.02, 1.08, 1.12, "D-W-L-D-D", 1.30, 1.30, 3, 1.05, 0.95),
            (2, "Brentford", "https://assets.football.db/teams/brentford.png", 1650.0, 1.06, 1.15, 1.13, "L-W-L-D-W", 1.40, 1.45, 3, 1.10, 1.00),
            (2, "Crystal Palace", "https://assets.football.db/teams/crystalpalace.png", 1640.0, 0.98, 1.06, 1.12, "D-D-L-D-L", 1.20, 1.30, 3, 1.15, 0.95),
            (2, "Nottingham Forest", "https://assets.football.db/teams/nottingham.png", 1630.0, 0.96, 1.08, 1.13, "W-L-D-W-L", 1.20, 1.30, 3, 1.25, 0.90),
            (2, "Wolverhampton", "https://assets.football.db/teams/wolves.png", 1615.0, 0.92, 1.18, 1.12, "L-L-D-L-L", 1.10, 1.50, 3, 1.30, 0.90),
            (2, "Everton", "https://assets.football.db/teams/everton.png", 1610.0, 0.90, 1.12, 1.14, "L-D-L-D-W", 1.05, 1.35, 3, 1.25, 0.90),
            (2, "Leicester City", "https://assets.football.db/teams/leicester.png", 1590.0, 0.94, 1.22, 1.12, "L-D-L-L-D", 1.10, 1.55, 3, 1.10, 0.90),
            (2, "Ipswich Town", "https://assets.football.db/teams/ipswich.png", 1560.0, 0.88, 1.28, 1.12, "D-L-L-D-L", 1.00, 1.65, 3, 1.15, 0.85),
            (2, "Southampton", "https://assets.football.db/teams/southampton.png", 1550.0, 0.85, 1.30, 1.11, "L-L-L-L-D", 0.90, 1.70, 3, 1.20, 0.85),

            # LIGUE 1 (league_id = 3)
            (3, "Paris Saint-Germain", "https://assets.football.db/teams/psg.png", 1845.0, 1.45, 0.80, 1.15, "W-W-W-W-D", 2.40, 0.85, 3, 0.90, 1.30),
            (3, "Monaco", "https://assets.football.db/teams/monaco.png", 1750.0, 1.24, 0.94, 1.14, "W-W-D-W-L", 1.85, 1.15, 3, 1.10, 1.15),
            (3, "Lille", "https://assets.football.db/teams/lille.png", 1740.0, 1.18, 0.90, 1.15, "W-D-W-L-W", 1.70, 1.05, 3, 1.05, 1.10),
            (3, "Marseille", "https://assets.football.db/teams/marseille.png", 1745.0, 1.22, 0.95, 1.18, "W-W-L-W-D", 1.80, 1.15, 3, 1.30, 1.20),
            (3, "Lyon", "https://assets.football.db/teams/lyon.png", 1715.0, 1.15, 1.02, 1.15, "L-W-D-W-W", 1.65, 1.25, 3, 1.15, 1.05),
            (3, "Lens", "https://assets.football.db/teams/lens.png", 1710.0, 1.10, 0.92, 1.16, "D-W-D-W-L", 1.50, 1.05, 3, 1.10, 1.10),
            (3, "Nice", "https://assets.football.db/teams/nice.png", 1700.0, 1.08, 0.90, 1.14, "W-D-L-D-W", 1.45, 1.00, 3, 1.00, 1.00),
            (3, "Rennes", "https://assets.football.db/teams/rennes.png", 1680.0, 1.10, 1.04, 1.13, "L-D-W-L-D", 1.50, 1.30, 3, 1.15, 1.05),
            (3, "Brest", "https://assets.football.db/teams/brest.png", 1685.0, 1.06, 0.98, 1.14, "W-L-D-W-D", 1.40, 1.15, 3, 1.10, 1.00),
            (3, "Strasbourg", "https://assets.football.db/teams/strasbourg.png", 1630.0, 0.98, 1.12, 1.12, "D-W-L-D-L", 1.25, 1.40, 3, 1.20, 0.95),
            (3, "Toulouse", "https://assets.football.db/teams/toulouse.png", 1620.0, 0.95, 1.14, 1.12, "L-D-D-W-L", 1.20, 1.40, 3, 1.15, 0.90),
            (3, "Nantes", "https://assets.football.db/teams/nantes.png", 1600.0, 0.90, 1.16, 1.13, "L-D-L-D-D", 1.10, 1.45, 3, 1.10, 0.85),

            # LA LIGA (league_id = 4)
            (4, "Real Madrid", "https://assets.football.db/teams/realmadrid.png", 1895.0, 1.48, 0.76, 1.15, "W-W-W-D-W", 2.50, 0.80, 3, 0.90, 1.40),
            (4, "Barcelona", "https://assets.football.db/teams/barcelona.png", 1870.0, 1.46, 0.82, 1.15, "W-W-W-W-D", 2.45, 0.90, 3, 0.95, 1.35),
            (4, "Atletico Madrid", "https://assets.football.db/teams/atletico.png", 1795.0, 1.22, 0.80, 1.16, "W-D-W-W-D", 1.85, 0.90, 3, 1.25, 1.10),
            (4, "Athletic Bilbao", "https://assets.football.db/teams/bilbao.png", 1750.0, 1.18, 0.90, 1.17, "W-W-L-D-W", 1.70, 1.05, 3, 1.15, 1.20),
            (4, "Real Sociedad", "https://assets.football.db/teams/sociedad.png", 1735.0, 1.12, 0.92, 1.15, "D-W-D-L-W", 1.55, 1.05, 3, 1.10, 1.05),
            (4, "Villarreal", "https://assets.football.db/teams/villarreal.png", 1730.0, 1.20, 1.05, 1.14, "W-L-W-D-W", 1.80, 1.30, 3, 1.15, 1.10),
            (4, "Girona", "https://assets.football.db/teams/girona.png", 1720.0, 1.16, 1.08, 1.13, "L-W-D-W-L", 1.70, 1.35, 3, 1.05, 1.10),
            (4, "Real Betis", "https://assets.football.db/teams/betis.png", 1710.0, 1.12, 0.98, 1.16, "D-D-W-D-W", 1.50, 1.15, 3, 1.20, 1.05),
            (4, "Sevilla", "https://assets.football.db/teams/sevilla.png", 1680.0, 1.08, 1.06, 1.15, "L-D-W-L-D", 1.40, 1.30, 3, 1.35, 1.00),
            (4, "Valencia", "https://assets.football.db/teams/valencia.png", 1660.0, 1.02, 1.10, 1.14, "L-L-D-W-D", 1.25, 1.35, 3, 1.25, 0.95),
            (4, "Celta Vigo", "https://assets.football.db/teams/celta.png", 1650.0, 1.06, 1.18, 1.13, "W-L-D-L-W", 1.40, 1.45, 3, 1.15, 1.00),
            (4, "Mallorca", "https://assets.football.db/teams/mallorca.png", 1635.0, 0.90, 1.02, 1.14, "D-W-L-D-D", 1.10, 1.20, 3, 1.25, 0.85),

            # CAMPIONATO PORTOGHESE (league_id = 5)
            (5, "Sporting CP", "https://assets.football.db/teams/sporting.png", 1785.0, 1.36, 0.80, 1.16, "W-W-W-W-W", 2.30, 0.85, 3, 1.05, 1.25),
            (5, "Benfica", "https://assets.football.db/teams/benfica.png", 1775.0, 1.32, 0.82, 1.16, "W-W-D-W-W", 2.20, 0.90, 3, 1.00, 1.25),
            (5, "FC Porto", "https://assets.football.db/teams/porto.png", 1760.0, 1.28, 0.85, 1.17, "W-W-W-L-W", 2.10, 0.95, 3, 1.30, 1.20),
            (5, "SC Braga", "https://assets.football.db/teams/braga.png", 1695.0, 1.15, 0.98, 1.14, "W-D-W-D-L", 1.70, 1.20, 3, 1.15, 1.10),
            (5, "Vitoria Guimaraes", "https://assets.football.db/teams/guimaraes.png", 1650.0, 1.05, 1.02, 1.15, "D-W-L-W-D", 1.40, 1.25, 3, 1.20, 1.00),
            (5, "Famalicao", "https://assets.football.db/teams/famalicao.png", 1600.0, 0.94, 1.08, 1.12, "L-D-W-D-L", 1.20, 1.35, 3, 1.15, 0.90),
            (5, "Rio Ave", "https://assets.football.db/teams/rioave.png", 1580.0, 0.90, 1.15, 1.12, "D-L-D-L-W", 1.10, 1.45, 3, 1.10, 0.85),
            (5, "Gil Vicente", "https://assets.football.db/teams/gilvicente.png", 1570.0, 0.88, 1.18, 1.11, "L-L-D-W-L", 1.05, 1.50, 3, 1.10, 0.85),

            # CAMPIONATO BELGA (league_id = 6)
            (6, "Club Brugge", "https://assets.football.db/teams/clubbrugge.png", 1715.0, 1.25, 0.90, 1.15, "W-W-D-W-W", 1.95, 1.10, 3, 1.05, 1.20),
            (6, "Union Saint-Gilloise", "https://assets.football.db/teams/union_sg.png", 1700.0, 1.22, 0.92, 1.14, "W-D-W-W-L", 1.85, 1.15, 3, 1.10, 1.15),
            (6, "Anderlecht", "https://assets.football.db/teams/anderlecht.png", 1685.0, 1.18, 0.95, 1.15, "D-W-W-L-D", 1.75, 1.20, 3, 1.15, 1.10),
            (6, "KRC Genk", "https://assets.football.db/teams/genk.png", 1680.0, 1.20, 1.00, 1.14, "W-L-W-W-D", 1.80, 1.25, 3, 1.10, 1.15),
            (6, "KAA Gent", "https://assets.football.db/teams/gent.png", 1655.0, 1.12, 1.02, 1.14, "L-W-D-W-L", 1.60, 1.30, 3, 1.05, 1.05),
            (6, "Royal Antwerp", "https://assets.football.db/teams/antwerp.png", 1650.0, 1.10, 1.04, 1.15, "W-L-L-D-W", 1.55, 1.30, 3, 1.25, 1.05),
            (6, "Standard Liege", "https://assets.football.db/teams/standard.png", 1610.0, 0.95, 1.12, 1.15, "L-D-W-L-D", 1.25, 1.40, 3, 1.30, 0.95),
            (6, "Cercle Brugge", "https://assets.football.db/teams/cerclebrugge.png", 1620.0, 1.00, 1.15, 1.12, "D-L-L-W-D", 1.35, 1.45, 3, 1.15, 1.00),

            # BUNDESLIGA (league_id = 7)
            (7, "Bayern Munich", "https://assets.football.db/teams/bayern.png", 1880.0, 1.48, 0.80, 1.15, "W-W-W-W-D", 2.55, 0.88, 3, 0.85, 1.40),
            (7, "Bayer Leverkusen", "https://assets.football.db/teams/leverkusen.png", 1845.0, 1.42, 0.84, 1.15, "W-W-D-W-W", 2.35, 0.92, 3, 0.95, 1.35),
            (7, "Borussia Dortmund", "https://assets.football.db/teams/dortmund.png", 1790.0, 1.30, 0.95, 1.18, "W-D-W-L-W", 2.05, 1.20, 3, 1.10, 1.25),
            (7, "RB Leipzig", "https://assets.football.db/teams/rbleipzig.png", 1795.0, 1.32, 0.90, 1.15, "W-W-W-L-D", 2.10, 1.10, 3, 1.05, 1.20),
            (7, "VfB Stuttgart", "https://assets.football.db/teams/stuttgart.png", 1750.0, 1.24, 0.98, 1.16, "D-W-W-D-L", 1.90, 1.25, 3, 1.10, 1.15),
            (7, "Eintracht Frankfurt", "https://assets.football.db/teams/frankfurt.png", 1735.0, 1.22, 1.02, 1.16, "W-L-D-W-W", 1.85, 1.30, 3, 1.20, 1.15),
            (7, "SC Freiburg", "https://assets.football.db/teams/freiburg.png", 1695.0, 1.10, 1.00, 1.15, "W-D-L-W-D", 1.50, 1.25, 3, 1.05, 1.05),
            (7, "VfL Wolfsburg", "https://assets.football.db/teams/wolfsburg.png", 1670.0, 1.08, 1.08, 1.13, "L-W-L-D-D", 1.45, 1.35, 3, 1.15, 1.00),
            (7, "Borussia M'gladbach", "https://assets.football.db/teams/mgladbach.png", 1660.0, 1.12, 1.15, 1.14, "D-L-W-L-D", 1.55, 1.50, 3, 1.10, 1.05),
            (7, "Werder Bremen", "https://assets.football.db/teams/bremen.png", 1650.0, 1.05, 1.12, 1.13, "L-D-D-W-L", 1.40, 1.40, 3, 1.10, 1.00),

            # EREDIVISIE (league_id = 8)
            (8, "PSV Eindhoven", "https://assets.football.db/teams/psv.png", 1775.0, 1.38, 0.82, 1.15, "W-W-W-W-W", 2.45, 0.90, 3, 0.90, 1.30),
            (8, "Feyenoord", "https://assets.football.db/teams/feyenoord.png", 1750.0, 1.30, 0.88, 1.16, "W-W-D-W-D", 2.15, 1.05, 3, 1.00, 1.25),
            (8, "Ajax", "https://assets.football.db/teams/ajax.png", 1735.0, 1.26, 0.94, 1.15, "W-L-W-W-D", 2.05, 1.15, 3, 1.05, 1.20),
            (8, "AZ Alkmaar", "https://assets.football.db/teams/az.png", 1715.0, 1.20, 0.95, 1.14, "W-D-W-L-W", 1.85, 1.15, 3, 1.05, 1.15),
            (8, "FC Twente", "https://assets.football.db/teams/twente.png", 1710.0, 1.18, 0.92, 1.15, "D-W-D-W-W", 1.75, 1.10, 3, 1.00, 1.10),
            (8, "FC Utrecht", "https://assets.football.db/teams/utrecht.png", 1660.0, 1.08, 1.04, 1.14, "W-W-L-D-D", 1.50, 1.30, 3, 1.10, 1.00),
            (8, "Go Ahead Eagles", "https://assets.football.db/teams/goaheadeagles.png", 1615.0, 1.00, 1.12, 1.12, "L-D-W-L-D", 1.35, 1.45, 3, 1.10, 0.95),
            (8, "SC Heerenveen", "https://assets.football.db/teams/heerenveen.png", 1610.0, 0.98, 1.15, 1.12, "L-L-D-W-L", 1.30, 1.50, 3, 1.05, 0.95),

            # SÜPER LIG (league_id = 9)
            (9, "Galatasaray", "https://assets.football.db/teams/galatasaray.png", 1765.0, 1.35, 0.85, 1.20, "W-W-W-W-W", 2.30, 0.95, 3, 1.20, 1.25),
            (9, "Fenerbahce", "https://assets.football.db/teams/fenerbahce.png", 1760.0, 1.34, 0.84, 1.20, "W-W-D-W-W", 2.25, 0.95, 3, 1.25, 1.25),
            (9, "Besiktas", "https://assets.football.db/teams/besiktas.png", 1715.0, 1.20, 0.96, 1.18, "W-D-W-L-W", 1.85, 1.20, 3, 1.25, 1.15),
            (9, "Trabzonspor", "https://assets.football.db/teams/trabzonspor.png", 1675.0, 1.12, 1.02, 1.16, "D-W-D-L-D", 1.55, 1.30, 3, 1.20, 1.05),
            (9, "Istanbul Basaksehir", "https://assets.football.db/teams/basaksehir.png", 1650.0, 1.08, 1.04, 1.12, "L-W-D-W-L", 1.45, 1.30, 3, 1.10, 1.00),
            (9, "Kasimpasa", "https://assets.football.db/teams/kasimpasa.png", 1620.0, 1.04, 1.14, 1.12, "D-L-W-L-D", 1.40, 1.45, 3, 1.15, 0.95),
            (9, "Sivasspor", "https://assets.football.db/teams/sivasspor.png", 1600.0, 0.95, 1.12, 1.14, "L-D-L-W-L", 1.25, 1.40, 3, 1.20, 0.90),
            (9, "Antalyaspor", "https://assets.football.db/teams/antalyaspor.png", 1590.0, 0.92, 1.16, 1.14, "L-L-D-D-W", 1.20, 1.45, 3, 1.15, 0.90),

            # CHAMPIONS LEAGUE (league_id = 10) - Club europei partecipanti alla League Phase 26/27
            (10, "Real Madrid CL", "https://assets.football.db/teams/realmadrid.png", 1900.0, 1.50, 0.75, 1.15, "W-W-W-W-W", 2.55, 0.78, 2, 0.90, 1.40),
            (10, "Manchester City CL", "https://assets.football.db/teams/mancity.png", 1898.0, 1.49, 0.73, 1.14, "W-W-W-D-W", 2.50, 0.75, 2, 0.85, 1.45),
            (10, "Bayern Munich CL", "https://assets.football.db/teams/bayern.png", 1882.0, 1.48, 0.79, 1.15, "W-W-W-W-D", 2.50, 0.85, 2, 0.85, 1.40),
            (10, "Inter CL", "https://assets.football.db/teams/inter.png", 1840.0, 1.35, 0.77, 1.15, "W-W-D-W-W", 2.20, 0.80, 2, 0.95, 1.25),
            (10, "Paris Saint-Germain CL", "https://assets.football.db/teams/psg.png", 1848.0, 1.44, 0.80, 1.15, "W-W-W-D-W", 2.40, 0.85, 2, 0.90, 1.30),
            (10, "Arsenal CL", "https://assets.football.db/teams/arsenal.png", 1868.0, 1.41, 0.74, 1.15, "W-W-D-W-W", 2.35, 0.75, 2, 0.95, 1.35),
            (10, "Barcelona CL", "https://assets.football.db/teams/barcelona.png", 1872.0, 1.46, 0.81, 1.15, "W-W-W-W-D", 2.45, 0.88, 2, 0.95, 1.35),
            (10, "Bayer Leverkusen CL", "https://assets.football.db/teams/leverkusen.png", 1848.0, 1.42, 0.83, 1.15, "W-W-D-W-W", 2.35, 0.90, 2, 0.95, 1.35),

            # EUROPA LEAGUE (league_id = 11) - Club partecipanti League Phase EL 26/27
            (11, "AS Roma EL", "https://assets.football.db/teams/roma.png", 1725.0, 1.15, 0.95, 1.15, "W-D-W-L-W", 1.65, 1.10, 2, 1.15, 1.10),
            (11, "Manchester United EL", "https://assets.football.db/teams/manunited.png", 1735.0, 1.18, 1.02, 1.14, "W-L-W-D-W", 1.70, 1.25, 2, 1.20, 1.15),
            (11, "Tottenham EL", "https://assets.football.db/teams/tottenham.png", 1748.0, 1.28, 1.02, 1.14, "W-W-D-L-W", 1.95, 1.30, 2, 1.20, 1.25),
            (11, "FC Porto EL", "https://assets.football.db/teams/porto.png", 1762.0, 1.29, 0.84, 1.16, "W-W-W-L-W", 2.10, 0.90, 2, 1.25, 1.20),
            (11, "Lazio EL", "https://assets.football.db/teams/lazio.png", 1720.0, 1.16, 0.96, 1.15, "W-L-W-D-W", 1.65, 1.15, 2, 1.20, 1.05),
            (11, "Athletic Bilbao EL", "https://assets.football.db/teams/bilbao.png", 1752.0, 1.20, 0.89, 1.16, "W-W-L-W-D", 1.75, 1.00, 2, 1.15, 1.20),

            # CONFERENCE LEAGUE (league_id = 12) - Club partecipanti ECL 26/27
            (12, "Chelsea ECL", "https://assets.football.db/teams/chelsea.png", 1770.0, 1.30, 0.95, 1.14, "W-W-D-W-L", 2.05, 1.10, 2, 1.25, 1.20),
            (12, "Fiorentina ECL", "https://assets.football.db/teams/fiorentina.png", 1695.0, 1.15, 0.98, 1.15, "W-D-W-L-W", 1.65, 1.20, 2, 1.10, 1.15),
            (12, "Real Betis ECL", "https://assets.football.db/teams/betis.png", 1715.0, 1.16, 0.96, 1.16, "D-W-W-D-W", 1.60, 1.10, 2, 1.15, 1.10),
            (12, "Gent ECL", "https://assets.football.db/teams/gent.png", 1660.0, 1.14, 1.00, 1.14, "L-W-D-W-W", 1.65, 1.25, 2, 1.05, 1.05),
            (12, "Heidenheim ECL", "https://assets.football.db/teams/heidenheim.png", 1640.0, 1.05, 1.05, 1.13, "W-L-W-D-L", 1.45, 1.35, 2, 1.15, 1.00),
            (12, "FC Copenhagen ECL", "https://assets.football.db/teams/copenhagen.png", 1655.0, 1.10, 1.02, 1.15, "W-W-L-D-D", 1.55, 1.25, 2, 1.10, 1.05),
        ]

        cur.executemany("""
            INSERT INTO teams (league_id, name, logo, elo, attack, defense, home_advantage, recent_form, xg_for, xg_against, matches_played_stats, cards_factor, corners_factor)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, teams_data)

        # Mappatura rapida ID squadre per nome
        cur.execute("SELECT id, name, league_id FROM teams")
        team_map = {row["name"]: row["id"] for row in cur.fetchall()}

        # 3. MATCHES (Partite completate per generare classifica iniziale realistica + match da giocare)
        # (league_id, matchday, match_date, home_team, away_team, status, home_goals, away_goals, home_xg, away_xg)
        sample_matches = [
            # SERIE A
            (1, "Giornata 1", "2026-08-23", "Inter", "Torino", "completed", 2, 0, 2.20, 0.65),
            (1, "Giornata 1", "2026-08-23", "Juventus", "Como", "completed", 3, 0, 2.10, 0.45),
            (1, "Giornata 1", "2026-08-24", "Milan", "Lazio", "completed", 2, 1, 1.85, 1.30),
            (1, "Giornata 1", "2026-08-24", "Napoli", "Bologna", "completed", 3, 0, 2.30, 0.70),
            (1, "Giornata 1", "2026-08-25", "Atalanta", "Lecce", "completed", 4, 0, 2.85, 0.40),
            (1, "Giornata 2", "2026-08-30", "Inter", "Lecce", "completed", 2, 0, 2.40, 0.50),
            (1, "Giornata 2", "2026-08-30", "Hellas Verona", "Juventus", "completed", 0, 3, 0.55, 2.05),
            (1, "Giornata 2", "2026-08-31", "Napoli", "Parma", "completed", 2, 1, 1.90, 1.10),
            (1, "Giornata 2", "2026-08-31", "Lazio", "Milan", "completed", 2, 2, 1.50, 1.65),
            (1, "Giornata 3", "2026-09-13", "Juventus", "Roma", "completed", 0, 0, 0.95, 0.85),
            (1, "Giornata 3", "2026-09-14", "Inter", "Atalanta", "completed", 4, 0, 2.70, 0.80),
            # Prossimi match da simulare / giocare
            (1, "Giornata 4", "2026-09-20", "Milan", "Inter", "scheduled", None, None, None, None),
            (1, "Giornata 4", "2026-09-20", "Juventus", "Napoli", "scheduled", None, None, None, None),
            (1, "Giornata 4", "2026-09-21", "Roma", "Lazio", "scheduled", None, None, None, None),
            (1, "Giornata 4", "2026-09-21", "Fiorentina", "Atalanta", "scheduled", None, None, None, None),

            # PREMIER LEAGUE
            (2, "Matchday 1", "2026-08-16", "Chelsea", "Manchester City", "completed", 0, 2, 0.90, 2.10),
            (2, "Matchday 1", "2026-08-16", "Arsenal", "Wolverhampton", "completed", 2, 0, 2.30, 0.55),
            (2, "Matchday 1", "2026-08-17", "Ipswich Town", "Liverpool", "completed", 0, 2, 0.60, 2.45),
            (2, "Matchday 2", "2026-08-23", "Manchester City", "Ipswich Town", "completed", 4, 1, 3.20, 0.40),
            (2, "Matchday 2", "2026-08-24", "Aston Villa", "Arsenal", "completed", 0, 2, 1.10, 1.95),
            (2, "Matchday 2", "2026-08-24", "Liverpool", "Brentford", "completed", 2, 0, 2.40, 0.70),
            (2, "Matchday 3", "2026-08-31", "Manchester United", "Liverpool", "completed", 0, 3, 1.15, 2.65),
            (2, "Matchday 3", "2026-08-31", "West Ham", "Manchester City", "completed", 1, 3, 0.95, 2.70),
            # Prossimi match Premier
            (2, "Matchday 4", "2026-09-21", "Manchester City", "Arsenal", "scheduled", None, None, None, None),
            (2, "Matchday 4", "2026-09-21", "Liverpool", "Chelsea", "scheduled", None, None, None, None),
            (2, "Matchday 4", "2026-09-22", "Tottenham", "Aston Villa", "scheduled", None, None, None, None),

            # LA LIGA
            (4, "Jornada 1", "2026-08-17", "Valencia", "Barcelona", "completed", 1, 2, 1.10, 2.25),
            (4, "Jornada 1", "2026-08-18", "Mallorca", "Real Madrid", "completed", 1, 1, 0.85, 1.90),
            (4, "Jornada 2", "2026-08-24", "Real Madrid", "Real Valladolid" if "Real Valladolid" in team_map else "Celta Vigo", "completed", 3, 0, 2.65, 0.50),
            (4, "Jornada 2", "2026-08-25", "Barcelona", "Athletic Bilbao", "completed", 2, 1, 2.15, 1.05),
            (4, "Jornada 3", "2026-08-31", "Real Madrid", "Real Betis", "completed", 2, 0, 2.50, 0.70),
            # Prossimi match La Liga
            (4, "Jornada 4", "2026-09-20", "Atletico Madrid", "Real Madrid", "scheduled", None, None, None, None),
            (4, "Jornada 4", "2026-09-21", "Barcelona", "Sevilla", "scheduled", None, None, None, None),

            # BUNDESLIGA
            (7, "Spieltag 1", "2026-08-23", "Borussia M'gladbach", "Bayer Leverkusen", "completed", 2, 3, 1.45, 2.40),
            (7, "Spieltag 1", "2026-08-24", "Wolfsburg", "Bayern Munich", "completed", 2, 3, 1.20, 2.60),
            (7, "Spieltag 2", "2026-08-31", "Bayer Leverkusen", "RB Leipzig", "completed", 2, 3, 2.30, 2.10),
            (7, "Spieltag 2", "2026-08-31", "Bayern Munich", "SC Freiburg", "completed", 2, 0, 2.45, 0.60),
            # Prossimi match Bundesliga
            (7, "Spieltag 3", "2026-09-21", "Bayern Munich", "Bayer Leverkusen", "scheduled", None, None, None, None),
            (7, "Spieltag 3", "2026-09-21", "Borussia Dortmund", "RB Leipzig", "scheduled", None, None, None, None),

            # LIGUE 1
            (3, "Journée 1", "2026-08-16", "Le Havre" if "Le Havre" in team_map else "Nantes", "Paris Saint-Germain", "completed", 1, 4, 0.65, 2.80),
            (3, "Journée 2", "2026-08-23", "Paris Saint-Germain", "Montpellier" if "Montpellier" in team_map else "Toulouse", "completed", 6, 0, 3.40, 0.35),
            (3, "Journée 3", "2026-08-31", "Lille", "Paris Saint-Germain", "completed", 1, 3, 1.25, 2.35),
            # Prossimi match Ligue 1
            (3, "Journée 4", "2026-09-21", "Marseille", "Paris Saint-Germain", "scheduled", None, None, None, None),
            (3, "Journée 4", "2026-09-21", "Monaco", "Lyon", "scheduled", None, None, None, None),

            # CHAMPIONS LEAGUE
            (10, "League Phase - MD 1", "2026-09-16", "Manchester City CL", "Inter CL", "completed", 1, 0, 1.95, 1.10),
            (10, "League Phase - MD 1", "2026-09-16", "Real Madrid CL", "Bayern Munich CL", "completed", 2, 1, 2.10, 1.75),
            (10, "League Phase - MD 2", "2026-09-30", "Bayern Munich CL", "Manchester City CL", "scheduled", None, None, None, None),
            (10, "League Phase - MD 2", "2026-09-30", "Arsenal CL", "Paris Saint-Germain CL", "scheduled", None, None, None, None),
            (10, "League Phase - MD 2", "2026-10-01", "Barcelona CL", "Bayer Leverkusen CL", "scheduled", None, None, None, None),

            # EUROPA LEAGUE
            (11, "League Phase - MD 1", "2026-09-24", "AS Roma EL", "Athletic Bilbao EL", "scheduled", None, None, None, None),
            (11, "League Phase - MD 1", "2026-09-24", "Manchester United EL", "FC Porto EL", "scheduled", None, None, None, None),
            (11, "League Phase - MD 1", "2026-09-25", "Tottenham EL", "Lazio EL", "scheduled", None, None, None, None),

            # CONFERENCE LEAGUE
            (12, "League Phase - MD 1", "2026-10-02", "Chelsea ECL", "Gent ECL", "scheduled", None, None, None, None),
            (12, "League Phase - MD 1", "2026-10-02", "Fiorentina ECL", "Real Betis ECL", "scheduled", None, None, None, None),
            (12, "League Phase - MD 1", "2026-10-02", "FC Copenhagen ECL", "Heidenheim ECL", "scheduled", None, None, None, None),
        ]

        matches_insert = []
        for lid, mday, mdate, h_name, a_name, status, h_goals, a_goals, h_xg, a_xg in sample_matches:
            if h_name in team_map and a_name in team_map:
                matches_insert.append((
                    lid, mday, mdate, team_map[h_name], team_map[a_name],
                    status, h_goals, a_goals, h_xg, a_xg
                ))

        cur.executemany("""
            INSERT INTO matches (league_id, matchday, match_date, home_team_id, away_team_id, status, home_goals, away_goals, home_xg, away_xg)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, matches_insert)

        # 4. STANDINGS INIZIALI: Popoliamo la tabella con record iniziali per ciascuna squadra
        cur.execute("SELECT id, league_id FROM teams")
        all_teams = cur.fetchall()
        for t in all_teams:
            cur.execute("""
                INSERT OR IGNORE INTO standings (league_id, team_id, played, won, drawn, lost, goals_for, goals_against, goal_diff, points)
                VALUES (?, ?, 0, 0, 0, 0, 0, 0, 0, 0)
            """, (t["league_id"], t["id"]))

        # 5. TOP SCORERS REALISTICI 2026/2027
        # (league_id, team_name, player_name, goals, assists)
        scorers_data = [
            # Serie A
            (1, "Inter", "Lautaro Martínez", 5, 2),
            (1, "Inter", "Marcus Thuram", 4, 3),
            (1, "Juventus", "Dušan Vlahović", 4, 1),
            (1, "Napoli", "Khvicha Kvaratskhelia", 3, 3),
            (1, "Atalanta", "Mateo Retegui", 4, 1),
            (1, "Milan", "Rafael Leão", 3, 4),
            (1, "Milan", "Christian Pulisic", 3, 2),
            (1, "Roma", "Paulo Dybala", 2, 3),
            (1, "Lazio", "Mattia Zaccagni", 2, 2),
            (1, "Fiorentina", "Moise Kean", 3, 1),

            # Premier League
            (2, "Manchester City", "Erling Haaland", 7, 1),
            (2, "Liverpool", "Mohamed Salah", 4, 4),
            (2, "Arsenal", "Bukayo Saka", 3, 5),
            (2, "Chelsea", "Cole Palmer", 4, 3),
            (2, "Aston Villa", "Ollie Watkins", 3, 2),
            (2, "Tottenham", "Son Heung-min", 3, 2),
            (2, "Newcastle", "Alexander Isak", 3, 1),

            # La Liga
            (4, "Real Madrid", "Kylian Mbappé", 5, 2),
            (4, "Real Madrid", "Vinícius Júnior", 4, 4),
            (4, "Barcelona", "Robert Lewandowski", 5, 1),
            (4, "Barcelona", "Lamine Yamal", 3, 5),
            (4, "Barcelona", "Raphinha", 4, 3),
            (4, "Atletico Madrid", "Julián Álvarez", 3, 2),

            # Bundesliga
            (7, "Bayern Munich", "Harry Kane", 6, 3),
            (7, "Bayern Munich", "Jamal Musiala", 4, 2),
            (7, "Bayer Leverkusen", "Florian Wirtz", 4, 4),
            (7, "Bayer Leverkusen", "Victor Boniface", 4, 1),
            (7, "RB Leipzig", "Benjamin Šeško", 3, 1),
            (7, "VfB Stuttgart", "Deniz Undav", 3, 2),

            # Ligue 1
            (3, "Paris Saint-Germain", "Bradley Barcola", 5, 2),
            (3, "Paris Saint-Germain", "Ousmane Dembélé", 3, 4),
            (3, "Lille", "Jonathan David", 4, 1),
            (3, "Marseille", "Mason Greenwood", 4, 2),
            (3, "Monaco", "Folarin Balogun", 3, 1),

            # Campionato Portoghese
            (5, "Sporting CP", "Viktor Gyökeres", 8, 2),
            (5, "Benfica", "Ángel Di María", 3, 4),
            (5, "FC Porto", "Galeno", 4, 2),

            # Campionato Belga
            (6, "Club Brugge", "Andreas Skov Olsen", 5, 3),
            (6, "Union Saint-Gilloise", "Kevin Rodríguez", 4, 2),
            (6, "KRC Genk", "Tolu Arokodare", 4, 1),

            # Eredivisie
            (8, "PSV Eindhoven", "Luuk de Jong", 5, 2),
            (8, "Feyenoord", "Santiago Giménez", 4, 1),
            (8, "Ajax", "Brian Brobbey", 3, 2),

            # Süper Lig
            (9, "Galatasaray", "Victor Osimhen", 6, 2),
            (9, "Galatasaray", "Mauro Icardi", 4, 2),
            (9, "Fenerbahce", "Edin Džeko", 5, 2),
            (9, "Besiktas", "Ciro Immobile", 4, 1),

            # Champions League
            (10, "Real Madrid CL", "Kylian Mbappé CL", 3, 1),
            (10, "Manchester City CL", "Erling Haaland CL", 3, 0),
            (10, "Bayern Munich CL", "Harry Kane CL", 2, 1),
            (10, "Inter CL", "Lautaro Martínez CL", 2, 1),

            # Europa League
            (11, "Manchester United EL", "Bruno Fernandes EL", 2, 2),
            (11, "AS Roma EL", "Artem Dovbyk EL", 2, 1),
            (11, "FC Porto EL", "Samu Omorodion EL", 2, 0),

            # Conference League
            (12, "Chelsea ECL", "Christopher Nkunku ECL", 2, 1),
            (12, "Fiorentina ECL", "Moise Kean ECL", 2, 0),
        ]

        top_scorers_insert = []
        for lid, tname, pname, goals, assists in scorers_data:
            if tname in team_map:
                top_scorers_insert.append((lid, team_map[tname], pname, goals, assists))

        cur.executemany("""
            INSERT INTO top_scorers (league_id, team_id, player_name, goals, assists)
            VALUES (?, ?, ?, ?, ?)
        """, top_scorers_insert)

        # 6. HEAD-TO-HEAD (H2H) STORICO PER LE RIVALITÀ E PARTITE DI CARTELLO
        # (date, comp, team1, team2, hg, ag, outcome, tot_goals)
        h2h_rivalry_data = [
            # Inter vs Milan
            ("2026-04-22", "Serie A", "Milan", "Inter", 1, 2, "2", 3),
            ("2025-09-22", "Serie A", "Inter", "Milan", 1, 2, "2", 3),
            ("2025-05-16", "Champions League", "Inter", "Milan", 1, 0, "1", 1),
            ("2025-05-10", "Champions League", "Milan", "Inter", 0, 2, "2", 2),
            ("2024-09-16", "Serie A", "Inter", "Milan", 5, 1, "1", 6),

            # Inter vs Juventus
            ("2026-02-15", "Serie A", "Inter", "Juventus", 1, 0, "1", 1),
            ("2025-10-27", "Serie A", "Inter", "Juventus", 4, 4, "X", 8),
            ("2025-02-04", "Serie A", "Inter", "Juventus", 1, 0, "1", 1),
            ("2024-11-26", "Serie A", "Juventus", "Inter", 1, 1, "X", 2),
            ("2024-04-26", "Coppa Italia", "Inter", "Juventus", 1, 0, "1", 1),

            # Juventus vs Napoli
            ("2026-03-03", "Serie A", "Napoli", "Juventus", 2, 1, "1", 3),
            ("2025-09-21", "Serie A", "Juventus", "Napoli", 0, 0, "X", 0),
            ("2025-04-23", "Serie A", "Juventus", "Napoli", 0, 1, "2", 1),
            ("2024-12-08", "Serie A", "Juventus", "Napoli", 1, 0, "1", 1),
            ("2024-01-13", "Serie A", "Napoli", "Juventus", 5, 1, "1", 6),

            # Roma vs Lazio
            ("2026-04-06", "Serie A", "Roma", "Lazio", 1, 0, "1", 1),
            ("2026-01-10", "Serie A", "Lazio", "Roma", 1, 0, "1", 1),
            ("2025-11-12", "Serie A", "Lazio", "Roma", 0, 0, "X", 0),
            ("2025-03-19", "Serie A", "Lazio", "Roma", 1, 0, "1", 1),
            ("2024-11-06", "Serie A", "Roma", "Lazio", 0, 1, "2", 1),

            # Manchester City vs Arsenal
            ("2026-03-31", "Premier League", "Manchester City", "Arsenal", 0, 0, "X", 0),
            ("2025-09-22", "Premier League", "Manchester City", "Arsenal", 2, 2, "X", 4),
            ("2025-04-26", "Premier League", "Manchester City", "Arsenal", 4, 1, "1", 5),
            ("2024-10-08", "Premier League", "Arsenal", "Manchester City", 1, 0, "1", 1),
            ("2024-08-06", "FA Community Shield", "Arsenal", "Manchester City", 1, 1, "X", 2),

            # Liverpool vs Chelsea
            ("2026-02-25", "EFL Cup", "Chelsea", "Liverpool", 0, 1, "2", 1),
            ("2025-10-20", "Premier League", "Liverpool", "Chelsea", 2, 1, "1", 3),
            ("2025-01-31", "Premier League", "Liverpool", "Chelsea", 4, 1, "1", 5),
            ("2024-08-13", "Premier League", "Chelsea", "Liverpool", 1, 1, "X", 2),
            ("2024-04-04", "Premier League", "Chelsea", "Liverpool", 0, 0, "X", 0),

            # Real Madrid vs Barcelona
            ("2026-04-21", "La Liga", "Real Madrid", "Barcelona", 3, 2, "1", 5),
            ("2025-10-26", "La Liga", "Real Madrid", "Barcelona", 0, 4, "2", 4),
            ("2025-01-14", "Supercopa", "Real Madrid", "Barcelona", 4, 1, "1", 5),
            ("2024-10-28", "La Liga", "Barcelona", "Real Madrid", 1, 2, "2", 3),
            ("2024-04-05", "Copa del Rey", "Barcelona", "Real Madrid", 0, 4, "2", 4),

            # Atletico Madrid vs Real Madrid
            ("2026-02-04", "La Liga", "Real Madrid", "Atletico Madrid", 1, 1, "X", 2),
            ("2025-09-29", "La Liga", "Atletico Madrid", "Real Madrid", 1, 1, "X", 2),
            ("2025-01-18", "Copa del Rey", "Atletico Madrid", "Real Madrid", 4, 2, "1", 6),
            ("2025-01-10", "Supercopa", "Real Madrid", "Atletico Madrid", 5, 3, "1", 8),
            ("2024-09-24", "La Liga", "Atletico Madrid", "Real Madrid", 3, 1, "1", 4),

            # Bayern Munich vs Bayer Leverkusen
            ("2026-02-10", "Bundesliga", "Bayer Leverkusen", "Bayern Munich", 3, 0, "1", 3),
            ("2025-09-28", "Bundesliga", "Bayern Munich", "Bayer Leverkusen", 1, 1, "X", 2),
            ("2025-03-09", "DFB Pokal", "Bayern Munich", "Bayer Leverkusen", 0, 1, "2", 1),
            ("2024-12-03", "Bundesliga", "Bayern Munich", "Bayer Leverkusen", 2, 2, "X", 4),
            ("2024-09-15", "Bundesliga", "Bayern Munich", "Bayer Leverkusen", 2, 2, "X", 4),

            # Sporting CP vs Benfica
            ("2026-04-06", "Liga Portugal", "Sporting CP", "Benfica", 2, 1, "1", 3),
            ("2025-11-12", "Liga Portugal", "Benfica", "Sporting CP", 2, 1, "1", 3),
            ("2025-04-02", "Taca de Portugal", "Benfica", "Sporting CP", 2, 2, "X", 4),
            ("2025-02-29", "Taca de Portugal", "Sporting CP", "Benfica", 2, 1, "1", 3),
            ("2024-05-21", "Liga Portugal", "Sporting CP", "Benfica", 2, 2, "X", 4),

            # Manchester City CL vs Inter CL
            ("2026-09-18", "Champions League", "Manchester City CL", "Inter CL", 0, 0, "X", 0),
            ("2025-06-10", "Champions League", "Manchester City CL", "Inter CL", 1, 0, "1", 1),
            ("2024-08-01", "Amichevole Internazionale", "Manchester City CL", "Inter CL", 2, 1, "1", 3),
            ("2023-07-28", "Amichevole Internazionale", "Inter CL", "Manchester City CL", 1, 1, "X", 2),
            ("2022-08-15", "Club Friendly", "Manchester City CL", "Inter CL", 3, 0, "1", 3),

            # Real Madrid CL vs Bayern Munich CL
            ("2026-05-08", "Champions League", "Real Madrid CL", "Bayern Munich CL", 2, 1, "1", 3),
            ("2026-04-30", "Champions League", "Bayern Munich CL", "Real Madrid CL", 2, 2, "X", 4),
            ("2024-05-01", "Champions League", "Real Madrid CL", "Bayern Munich CL", 2, 2, "X", 4),
            ("2024-04-25", "Champions League", "Bayern Munich CL", "Real Madrid CL", 1, 2, "2", 3),
            ("2023-04-18", "Champions League", "Real Madrid CL", "Bayern Munich CL", 4, 2, "1", 6),
        ]

        h2h_inserts = []
        covered_pairs = set()

        for mdate, comp, h_name, a_name, hg, ag, outc, tot in h2h_rivalry_data:
            if h_name in team_map and a_name in team_map:
                h_id = team_map[h_name]
                a_id = team_map[a_name]
                h2h_inserts.append((mdate, comp, h_id, a_id, hg, ag, outc, tot))
                pair_key = tuple(sorted([h_id, a_id]))
                covered_pairs.add(pair_key)

        # Assicuriamo che ogni match in calendario abbia almeno 5 precedenti realistici
        for m in sample_matches:
            h_name = m[3]
            a_name = m[4]
            if h_name in team_map and a_name in team_map:
                h_id = team_map[h_name]
                a_id = team_map[a_name]
                pair_key = tuple(sorted([h_id, a_id]))
                if pair_key not in covered_pairs:
                    covered_pairs.add(pair_key)
                    # Generiamo 5 precedenti storici coerenti
                    historical_templates = [
                        ("2026-03-12", 2, 1, "1"),
                        ("2025-10-18", 1, 1, "X"),
                        ("2025-04-08", 0, 2, "2"),
                        ("2024-11-22", 1, 0, "1"),
                        ("2024-02-14", 2, 2, "X")
                    ]
                    for dt, hg, ag, outc in historical_templates:
                        h2h_inserts.append((dt, "Campionato", h_id, a_id, hg, ag, outc, hg + ag))

        cur.executemany("""
            INSERT INTO h2h_matches (match_date, competition, home_team_id, away_team_id, home_goals, away_goals, outcome, total_goals)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, h2h_inserts)

    conn.close()

    # 6. RICALCOLO DELLE CLASSIFICHE PER TUTTE LE 12 LEGHE
    for league_id in range(1, 13):
        recalculate_league_standings(league_id, target_path)

    print(f"[seed.py] Database '{target_path}' popolato con successo per tutte le 12 competizioni 2026/2027!")


if __name__ == "__main__":
    seed_database()
