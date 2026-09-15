/**
 * Simulatore IA - Frontend Logic (app.js)
 * Gestisce l'interazione SPA, le chiamate API REST e l'integrazione
 * con il motore di simulazione Monte Carlo (50.000 iterazioni).
 */

const state = {
  leagues: [],
  currentLeagueId: null,
  currentTab: 'calendario',
  matches: [],
  matchdays: [],
  selectedMatchday: null,
  standings: [],
  topScorers: [],
  teams: [],
  teamsMap: {},
  currentSimulation: null,
  currentMarketCategory: 'all',
};

// Flag e colori rappresentativi per ciascuna lega
const leagueMeta = {
  "Serie A": { flag: "🇮🇹", color: "from-blue-600 to-cyan-500", icon: "shield" },
  "Premier League": { flag: "🏴󠁧󠁢󠁥󠁮󠁧󠁿", color: "from-purple-600 to-indigo-500", icon: "crown" },
  "Ligue 1": { flag: "🇫🇷", color: "from-blue-500 to-indigo-600", icon: "flame" },
  "La Liga": { flag: "🇪🇸", color: "from-amber-500 to-red-500", icon: "sun" },
  "Campionato Portoghese": { flag: "🇵🇹", color: "from-emerald-600 to-teal-500", icon: "compass" },
  "Campionato Belga": { flag: "🇧🇪", color: "from-red-600 to-yellow-500", icon: "swords" },
  "Bundesliga": { flag: "🇩🇪", color: "from-red-600 to-slate-900", icon: "zap" },
  "Eredivisie": { flag: "🇳🇱", color: "from-orange-500 to-amber-600", icon: "wind" },
  "Süper Lig": { flag: "🇹🇷", color: "from-red-500 to-rose-600", icon: "star" },
  "Champions League": { flag: "🇪🇺", color: "from-indigo-600 to-blue-400", icon: "trophy" },
  "Europa League": { flag: "🇪🇺", color: "from-amber-500 to-orange-600", icon: "award" },
  "Conference League": { flag: "🇪🇺", color: "from-emerald-500 to-cyan-500", icon: "shield-check" },
};

// Inizializzazione al caricamento
document.addEventListener('DOMContentLoaded', () => {
  initApp();
});

async function initApp() {
  try {
    const res = await fetch('/api/leagues');
    state.leagues = await res.json();
    renderLeaguesGrid();
    if (window.lucide) window.lucide.createIcons();
  } catch (err) {
    console.error("Errore nel caricamento delle leghe:", err);
  }
}

// ================= VISTA 1: DASHBOARD HOME =================

function renderLeaguesGrid() {
  const container = document.getElementById('leagues-grid');
  if (!container) return;

  container.innerHTML = state.leagues.map(l => {
    const meta = leagueMeta[l.name] || { flag: "⚽", color: "from-blue-600 to-cyan-500", icon: "shield" };
    return `
      <div onclick="navigateToLeague(${l.id})" class="glass-card p-5 cursor-pointer group hover:scale-[1.02] transition duration-200 flex flex-col justify-between">
        <div>
          <div class="flex items-center justify-between mb-4">
            <span class="text-2xl">${meta.flag}</span>
            <span class="text-[11px] uppercase tracking-wider font-bold px-2 py-0.5 rounded-full bg-white/5 border border-white/10 text-slate-300">
              ${l.type === 'cup' ? 'Coppa Europea' : 'Campionato'}
            </span>
          </div>
          <div class="flex items-center gap-3 mb-2">
            <div class="w-10 h-10 rounded-xl bg-gradient-to-tr ${meta.color} flex items-center justify-center text-white shadow-[0_0_12px_rgba(0,240,255,0.25)] flex-shrink-0">
              <i data-lucide="${meta.icon}" class="w-5 h-5"></i>
            </div>
            <div>
              <h3 class="text-lg font-bold text-white group-hover:text-[#00f0ff] transition font-['Outfit']">${l.name}</h3>
              <p class="text-xs text-slate-400">${l.country} • Stagione 26/27</p>
            </div>
          </div>
        </div>
        <div class="mt-4 pt-3 border-t border-white/5 flex items-center justify-between text-xs font-semibold text-[#00f0ff]">
          <span>Esplora & Pronostici</span>
          <i data-lucide="chevron-right" class="w-4 h-4 group-hover:translate-x-1 transition"></i>
        </div>
      </div>
    `;
  }).join('');

  if (window.lucide) window.lucide.createIcons();
}

function navigateToHome() {
  document.getElementById('view-home').classList.remove('hidden');
  document.getElementById('view-league').classList.add('hidden');
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

// ================= VISTA 2: DETTAGLIO CAMPIONATO =================

async function navigateToLeague(leagueId) {
  state.currentLeagueId = leagueId;
  const league = state.leagues.find(l => l.id === leagueId);
  if (!league) return;

  // Aggiorna titolo e metadati
  document.getElementById('league-title').innerText = league.name;
  document.getElementById('league-country-badge').innerText = `${league.country} • ${league.type === 'cup' ? 'Fase a Gironi' : 'Girone Unico'}`;

  const meta = leagueMeta[league.name] || { flag: "⚽", color: "from-blue-600 to-cyan-500", icon: "shield" };
  const logoBox = document.getElementById('league-logo-container');
  logoBox.innerHTML = `<i data-lucide="${meta.icon}" class="w-9 h-9 text-[#00f0ff]"></i>`;

  // Mostra vista campionato e nascondi home
  document.getElementById('view-home').classList.add('hidden');
  document.getElementById('view-league').classList.remove('hidden');
  window.scrollTo({ top: 0, behavior: 'smooth' });

  // Carica i dati in parallelo
  await refreshCurrentLeague();
}

async function refreshCurrentLeague() {
  if (!state.currentLeagueId) return;
  const lid = state.currentLeagueId;

  try {
    const [matchesRes, standingsRes, scorersRes, teamsRes] = await Promise.all([
      fetch(`/api/matches?league_id=${lid}&limit=500`),
      fetch(`/api/leagues/${lid}/standings`),
      fetch(`/api/leagues/${lid}/top-scorers?limit=15`),
      fetch(`/api/leagues/${lid}/teams`)
    ]);

    state.matches = await matchesRes.json();
    state.standings = await standingsRes.json();
    state.topScorers = await scorersRes.json();
    state.teams = await teamsRes.json();

    const league = state.leagues.find(item => item.id === lid);
    const matchdayPrefix = getMatchdayPrefix(state.matches, league);
    state.matches = state.matches.map(match => ({
      ...match,
      matchday: normalizeMatchday(match.matchday, matchdayPrefix),
    }));

    // Mappa squadre per id
    state.teamsMap = {};
    state.teams.forEach(t => { state.teamsMap[t.id] = t; });

    // Mostra anche i turni futuri che non hanno ancora partite nel database.
    state.matchdays = buildExpectedMatchdays(league, state.teams, state.matches, matchdayPrefix);

    // Seleziona la prima giornata o la giornata corrente
    if (!state.selectedMatchday || !days.includes(state.selectedMatchday)) {
      // Preferisci una giornata che ha match 'scheduled' se esiste
      const scheduledMatch = state.matches.find(m => m.status === 'scheduled');
      state.selectedMatchday = scheduledMatch ? scheduledMatch.matchday : (days[0] || 'Giornata 1');
    }

    renderMatchdaysSlider();
    renderMatchesList();
    renderStandingsTable();
    renderTopScorers();
    renderXgTable();

    if (window.lucide) window.lucide.createIcons();
  } catch (err) {
    console.error("Errore durante il refresh del campionato:", err);
  }
}

function getMatchdayPrefix(matches, league) {
  const existing = matches.find(match => match.matchday && /\d+/.test(String(match.matchday)));
  const value = existing ? String(existing.matchday) : '';
  if (value.includes('Matchday')) return 'Matchday';
  if (value.includes('Jornada')) return 'Jornada';
  if (value.includes('Spieltag')) return 'Spieltag';
  if (value.includes('Journée')) return 'Journée';
  if (value.includes('Giornata')) return 'Giornata';
  return league?.type === 'cup' ? 'Matchday' : 'Giornata';
}

function normalizeMatchday(value, prefix) {
  const number = String(value || '').match(/\d+/)?.[0];
  return number ? `${prefix} ${number}` : String(value || `${prefix} 1`);
}

function buildExpectedMatchdays(league, teams, matches, prefix) {
  const existing = [...new Set(matches.map(match => match.matchday).filter(Boolean))];
  const teamCount = teams.length;
  let totalMatchdays = 0;

  if (league?.name === 'Champions League') {
    totalMatchdays = 8;
  } else if (teamCount === 20) {
    totalMatchdays = 38;
  } else if (teamCount === 18) {
    totalMatchdays = 34;
  }

  if (!totalMatchdays) {
    return existing.sort((first, second) => extractMatchdayNumber(first) - extractMatchdayNumber(second));
  }

  return Array.from({ length: totalMatchdays }, (_, index) => `${prefix} ${index + 1}`);
}

function extractMatchdayNumber(value) {
  return Number(String(value).match(/\d+/)?.[0] || 0);
}

function switchLeagueTab(tabKey) {
  state.currentTab = tabKey;
  ['calendario', 'classifica', 'marcatori', 'xg'].forEach(k => {
    const tabBtn = document.getElementById(`tab-${k}`);
    const content = document.getElementById(`tab-content-${k}`);
    if (k === tabKey) {
      tabBtn.classList.add('active');
      content.classList.remove('hidden');
    } else {
      tabBtn.classList.remove('active');
      content.classList.add('hidden');
    }
  });
  if (window.lucide) window.lucide.createIcons();
}

// --- RENDER 1: CALENDARIO & GIORNATE ---

function renderMatchdaysSlider() {
  const slider = document.getElementById('matchdays-slider');
  if (!slider) return;

  if (state.matchdays.length === 0) {
    slider.innerHTML = `<span class="text-xs text-slate-400">Nessuna giornata registrata.</span>`;
    return;
  }

  slider.innerHTML = state.matchdays.map((mday, idx) => {
    const isActive = mday === state.selectedMatchday;
    // Estrai numero per visualizzazione compatta
    const labelNum = extractMatchdayNumber(mday) || (idx + 1);
    const shortTitle = mday.includes('Giornata') ? 'G.' : (mday.includes('Matchday') ? 'MD' : 'T.');

    return `
      <button onclick="selectMatchday('${mday}')" class="matchday-btn ${isActive ? 'active' : ''}">
        <span class="sub">${shortTitle}</span>
        <span class="num">${labelNum}</span>
      </button>
    `;
  }).join('');
}

function selectMatchday(mday) {
  state.selectedMatchday = mday;
  renderMatchdaysSlider();
  renderMatchesList();
  if (window.lucide) window.lucide.createIcons();
}

function renderFormPills(formStr) {
  if (!formStr) return '';
  const parts = formStr.split('-').filter(p => p.trim());
  return parts.map(res => {
    const r = res.toUpperCase();
    const cls = r === 'W' ? 'w' : (r === 'D' ? 'd' : 'l');
    return `<span class="form-pill ${cls}">${r}</span>`;
  }).join('');
}

function renderMatchesList() {
  const container = document.getElementById('matches-list-container');
  if (!container) return;

  const currentMatches = state.matches.filter(m => m.matchday === state.selectedMatchday);

  if (currentMatches.length === 0) {
    container.innerHTML = `
      <div class="glass-card p-8 text-center text-slate-400 text-sm">
        Nessuna partita programmata per ${state.selectedMatchday}.
      </div>
    `;
    return;
  }

  container.innerHTML = currentMatches.map(m => {
    const homeTeam = state.teamsMap[m.home_team_id] || { name: m.home_team_name, recent_form: "D-D-D-D-D", elo: 1500 };
    const awayTeam = state.teamsMap[m.away_team_id] || { name: m.away_team_name, recent_form: "D-D-D-D-D", elo: 1500 };
    const isCompleted = m.status === 'completed';

    return `
      <div class="glass-card p-4 sm:p-5 flex flex-col md:flex-row items-center justify-between gap-4 border-[#00f0ff]/15 hover:border-[#00f0ff]/40">
        
        <!-- Squadra Casa -->
        <div class="flex items-center gap-3 w-full md:w-5/12 justify-start">
          <div class="w-11 h-11 rounded-xl bg-[#091533] border border-white/10 p-1 flex items-center justify-center flex-shrink-0 shadow-[0_0_8px_rgba(0,240,255,0.1)]">
            <i data-lucide="shield" class="w-6 h-6 text-[#00f0ff]"></i>
          </div>
          <div class="min-w-0">
            <div class="flex items-center gap-2">
              <span class="font-bold text-white text-base truncate">${homeTeam.name}</span>
              <span class="text-[10px] text-slate-400 font-mono">(${Math.round(homeTeam.elo)})</span>
            </div>
            <div class="flex items-center gap-1 mt-1">
              ${renderFormPills(homeTeam.recent_form)}
            </div>
          </div>
        </div>

        <!-- Centro: Risultato o Data -->
        <div class="flex flex-col items-center justify-center my-2 md:my-0 flex-shrink-0 min-w-[120px]">
          ${isCompleted ? `
            <div class="text-xl font-extrabold text-[#00f0ff] font-['Outfit'] tracking-wider bg-[#070d1e] px-4 py-1.5 rounded-xl border border-[#00f0ff]/30 shadow-[0_0_12px_rgba(0,240,255,0.2)]">
              ${m.home_goals} - ${m.away_goals}
            </div>
            <span class="text-[10px] uppercase font-bold text-emerald-400 mt-1">Finale Concluso</span>
          ` : `
            <div class="text-xs font-bold text-slate-300 bg-white/5 px-3 py-1 rounded-full border border-white/10">
              ${m.match_date}
            </div>
            <span class="text-[10px] uppercase tracking-wider text-[#38bdf8] font-bold mt-1">Da Giocare</span>
          `}
        </div>

        <!-- Squadra Ospite -->
        <div class="flex items-center gap-3 w-full md:w-5/12 justify-end text-right">
          <div class="min-w-0">
            <div class="flex items-center justify-end gap-2">
              <span class="text-[10px] text-slate-400 font-mono">(${Math.round(awayTeam.elo)})</span>
              <span class="font-bold text-white text-base truncate">${awayTeam.name}</span>
            </div>
            <div class="flex items-center justify-end gap-1 mt-1">
              ${renderFormPills(awayTeam.recent_form)}
            </div>
          </div>
          <div class="w-11 h-11 rounded-xl bg-[#091533] border border-white/10 p-1 flex items-center justify-center flex-shrink-0 shadow-[0_0_8px_rgba(0,240,255,0.1)]">
            <i data-lucide="shield" class="w-6 h-6 text-[#38bdf8]"></i>
          </div>
        </div>

        <!-- Action Button: Analisi -->
        <div class="w-full md:w-auto flex justify-end md:pl-2">
          <button onclick="openAnalysis(${m.id}, ${m.home_team_id}, ${m.away_team_id})" class="glow-btn w-full md:w-auto text-xs py-2 px-3.5">
            <i data-lucide="zap" class="w-3.5 h-3.5 fill-current"></i>
            <span>Analisi</span>
          </button>
        </div>

      </div>
    `;
  }).join('');
}

// --- RENDER 2: CLASSIFICA ---

function renderStandingsTable() {
  const tbody = document.getElementById('standings-table-body');
  if (!tbody) return;

  tbody.innerHTML = state.standings.map((s, idx) => {
    const pos = idx + 1;
    // Evidenzia zone europee o retrocessione
    let posBadgeColor = "text-slate-300";
    if (pos <= 4) posBadgeColor = "text-[#00f0ff] font-extrabold";
    else if (pos <= 6) posBadgeColor = "text-amber-400 font-bold";
    else if (pos >= state.standings.length - 2) posBadgeColor = "text-red-400 font-bold";

    return `
      <tr class="table-row border-b border-white/5">
        <td class="font-mono ${posBadgeColor}">${pos}</td>
        <td>
          <div class="flex items-center gap-2.5">
            <div class="w-7 h-7 rounded-lg bg-[#0c1836] border border-white/10 flex items-center justify-center flex-shrink-0">
              <i data-lucide="shield" class="w-4 h-4 text-[#00f0ff]"></i>
            </div>
            <span class="font-bold text-white">${s.team_name}</span>
          </div>
        </td>
        <td class="text-center">
          <div class="flex items-center justify-center gap-1">
            ${renderFormPills(s.recent_form)}
          </div>
        </td>
        <td class="text-center font-mono text-slate-300">${s.played}</td>
        <td class="text-center font-mono text-emerald-400">${s.won}</td>
        <td class="text-center font-mono text-amber-400">${s.drawn}</td>
        <td class="text-center font-mono text-rose-400">${s.lost}</td>
        <td class="text-center font-mono text-slate-300">${s.goals_for}</td>
        <td class="text-center font-mono text-slate-300">${s.goals_against}</td>
        <td class="text-center font-mono ${s.goal_diff > 0 ? 'text-emerald-400' : (s.goal_diff < 0 ? 'text-rose-400' : 'text-slate-400')}">
          ${s.goal_diff > 0 ? '+' : ''}${s.goal_diff}
        </td>
        <td class="text-right font-mono font-black text-lg text-[#00f0ff] pr-4">${s.points}</td>
      </tr>
    `;
  }).join('');
}

// --- RENDER 3: MARCATORI ---

function renderTopScorers() {
  const container = document.getElementById('scorers-list-container');
  if (!container) return;

  if (state.topScorers.length === 0) {
    container.innerHTML = `<div class="p-4 text-slate-400 text-sm">Nessun marcatore registrato.</div>`;
    return;
  }

  container.innerHTML = state.topScorers.map((sc, idx) => {
    return `
      <div class="bg-[#091533] border border-white/5 hover:border-[#00f0ff]/30 rounded-xl p-3.5 flex items-center justify-between transition">
        <div class="flex items-center gap-3">
          <span class="w-7 h-7 rounded-lg bg-white/5 flex items-center justify-center text-xs font-bold ${idx < 3 ? 'text-[#00f0ff] font-extrabold' : 'text-slate-400'}">
            ${idx + 1}
          </span>
          <div>
            <h4 class="font-bold text-white text-sm">${sc.player_name}</h4>
            <p class="text-xs text-slate-400">${sc.team_name}</p>
          </div>
        </div>
        <div class="flex items-center gap-4 text-right">
          <div>
            <div class="text-base font-extrabold text-[#00f0ff] font-['Outfit']">${sc.goals}</div>
            <div class="text-[10px] uppercase text-slate-400 font-semibold">Gol</div>
          </div>
          <div class="border-l border-white/10 pl-4">
            <div class="text-base font-bold text-slate-300 font-['Outfit']">${sc.assists}</div>
            <div class="text-[10px] uppercase text-slate-400 font-semibold">Assist</div>
          </div>
        </div>
      </div>
    `;
  }).join('');
}

// --- RENDER 4: DATI XG ---

function renderXgTable() {
  const container = document.getElementById('xg-table-container');
  if (!container) return;

  const sortedTeams = [...state.teams].sort((a, b) => (b.xg_for - b.xg_against) - (a.xg_for - a.xg_against));

  container.innerHTML = `
    <table class="custom-table">
      <thead>
        <tr>
          <th>Squadra</th>
          <th class="text-center">Rating Elo</th>
          <th class="text-center">Attacco</th>
          <th class="text-center">Difesa</th>
          <th class="text-center">xG Prodotti (Media)</th>
          <th class="text-center">xG Concessi (Media)</th>
          <th class="text-right">xG Delta</th>
        </tr>
      </thead>
      <tbody>
        ${sortedTeams.map(t => {
          const hasXg = t.xg_source && t.xg_source !== 'not_available';
          const delta = hasXg ? (t.xg_for - t.xg_against).toFixed(2) : null;
          return `
            <tr class="table-row border-b border-white/5">
              <td class="font-bold text-white">${t.name}</td>
              <td class="text-center font-mono text-[#00f0ff] font-bold">${Math.round(t.elo)}</td>
              <td class="text-center font-mono text-slate-300">${t.attack.toFixed(2)}</td>
              <td class="text-center font-mono text-slate-300">${t.defense.toFixed(2)}</td>
              <td class="text-center font-mono text-emerald-400 font-semibold">${hasXg ? Number(t.xg_for).toFixed(2) : 'N/D'}</td>
              <td class="text-center font-mono text-rose-400 font-semibold">${hasXg ? Number(t.xg_against).toFixed(2) : 'N/D'}</td>
              <td class="text-right font-mono font-bold ${delta !== null && delta > 0 ? 'text-[#00f0ff]' : 'text-slate-400'}">
                ${delta !== null ? `${delta > 0 ? '+' : ''}${delta}` : 'N/D'}
              </td>
            </tr>
          `;
        }).join('')}
      </tbody>
    </table>
  `;
}

function rangeMarketItems(market, labelPrefix = '') {
  return Object.entries(market)
    .filter(([key]) => key !== 'expected_mean')
    .map(([key, stat]) => ({
      label: `${labelPrefix}${key.replaceAll('_', '-')}`,
      stat,
    }));
}

// ================= MODALE SIMULAZIONE & ANALISI (50.000 RUNS) =================

async function openAnalysis(matchId, homeTeamId, awayTeamId) {
  const modal = document.getElementById('simulation-modal');
  modal.classList.add('open');

  const homeTeam = state.teamsMap[homeTeamId] || {};
  const awayTeam = state.teamsMap[awayTeamId] || {};
  renderAnalysisSetup(matchId, homeTeamId, awayTeamId, homeTeam, awayTeam);
  return;
}

function openManualAnalysis() {
  openAnalysis(null, null, null);
}

const quoteMarketGroups = [
  ['1x2_finale', '1X2 Finale', ['1', 'X', '2']],
  ['1x2_primo_tempo', '1X2 Primo Tempo', ['1', 'X', '2']],
  ['over_under_finale', 'Over/Under Finale', ['Over_0.5', 'Under_0.5', 'Over_1.5', 'Under_1.5', 'Over_2.5', 'Under_2.5', 'Over_3.5', 'Under_3.5', 'Over_4.5', 'Under_4.5']],
  ['over_under_primo_tempo', 'Over/Under Primo Tempo', ['Over_0.5', 'Under_0.5', 'Over_1.5', 'Under_1.5', 'Over_2.5', 'Under_2.5', 'Over_3.5', 'Under_3.5', 'Over_4.5', 'Under_4.5']],
  ['goal_nogoal_finale', 'Goal/No Goal Finale', ['Goal', 'No_Goal']],
  ['goal_nogoal_primo_tempo', 'Goal/No Goal Primo Tempo', ['Goal', 'No_Goal']],
  ['multigol_partita', 'Multigol Partita', ['0_1', '0_2', '0_3', '0_4', '0_5', '1_2', '1_3', '1_4', '1_5', '2_3', '2_4', '2_5', '2_6', '3_4', '3_5', '3_6']],
  ['multigol_casa', 'Multigol Casa', ['0_1', '0_2', '0_3', '0_4', '0_5', '1_2', '1_3', '1_4', '1_5', '2_3', '2_4', '2_5', '2_6', '3_4', '3_5', '3_6']],
  ['multigol_ospite', 'Multigol Ospite', ['0_1', '0_2', '0_3', '0_4', '0_5', '1_2', '1_3', '1_4', '1_5', '2_3', '2_4', '2_5', '2_6', '3_4', '3_5', '3_6']],
  ['cartellini', 'Cartellini', ['Over_3.5', 'Under_3.5', 'Over_4.5', 'Under_4.5', 'Over_5.5', 'Under_5.5']],
  ['calci_dangolo', 'Calci d\'angolo', ['Over_8.5', 'Under_8.5', 'Over_9.5', 'Under_9.5', 'Over_10.5', 'Under_10.5', 'Over_11.5', 'Under_11.5']],
  ['over_under_squadra_casa', 'Over/Under Casa', ['Over_0.5', 'Under_0.5', 'Over_1.5', 'Under_1.5', 'Over_2.5', 'Under_2.5', 'Over_3.5', 'Under_3.5']],
  ['over_under_squadra_ospite', 'Over/Under Ospite', ['Over_0.5', 'Under_0.5', 'Over_1.5', 'Under_1.5', 'Over_2.5', 'Under_2.5', 'Over_3.5', 'Under_3.5']],
];

function renderAnalysisSetup(matchId, homeId, awayId, home, away) {
  const panel = document.getElementById('analysis-setup-panel');
  if (!panel) return;
  const isManual = !homeId && !awayId && !matchId;
  const value = (team, field, fallback = '') => {
    if (team[field] === undefined || team[field] === null || team[field] === '') return fallback;
    return typeof team[field] === 'number' ? team[field].toFixed(2) : team[field];
  };
  const xgValue = (team, field) => Number.isFinite(Number(team[field])) ? Number(team[field]).toFixed(2) : '';
  const teamFields = (side, team, defaultName, defaultForm) => `
    <div class="bg-[#070d1e] rounded-xl p-3 border border-white/10">
      <strong class="text-white">${side === 'home' ? 'Team 1 (casa)' : 'Team 2 (ospite)'}</strong>
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-2 mt-2">
        <label class="text-[11px] text-slate-400 sm:col-span-2">Nome squadra<input id="analysis-${side}-name" type="text" value="${value(team, 'name', defaultName)}" class="w-full mt-1 rounded-lg bg-white/5 border border-white/10 px-2 py-1.5 text-white"></label>
        <label class="text-[11px] text-slate-400">Attacco<input id="analysis-${side}-attack" type="number" min="0.2" max="3" step="0.01" value="${value(team, 'attack', '1.00')}" class="w-full mt-1 rounded-lg bg-white/5 border border-white/10 px-2 py-1.5 text-white"></label>
        <label class="text-[11px] text-slate-400">Difesa<input id="analysis-${side}-defense" type="number" min="0.2" max="3" step="0.01" value="${value(team, 'defense', '1.00')}" class="w-full mt-1 rounded-lg bg-white/5 border border-white/10 px-2 py-1.5 text-white"></label>
        <label class="text-[11px] text-slate-400">Valore Elo<input id="analysis-${side}-elo" type="number" min="800" max="2400" step="1" value="${value(team, 'elo', '1500')}" class="w-full mt-1 rounded-lg bg-white/5 border border-white/10 px-2 py-1.5 text-white"></label>
        <label class="text-[11px] text-slate-400">Forma (W-D-L)<input id="analysis-${side}-form" type="text" value="${value(team, 'recent_form', defaultForm)}" placeholder="W-D-W-D-L" class="w-full mt-1 rounded-lg bg-white/5 border border-white/10 px-2 py-1.5 text-white"></label>
        <label class="text-[11px] text-slate-400">Fattore cartellini<input id="analysis-${side}-cards" type="number" min="0.2" max="2.5" step="0.01" value="${value(team, 'cards_factor', '1.00')}" class="w-full mt-1 rounded-lg bg-white/5 border border-white/10 px-2 py-1.5 text-white"></label>
        <label class="text-[11px] text-slate-400">Fattore corner<input id="analysis-${side}-corners" type="number" min="0.2" max="2.5" step="0.01" value="${value(team, 'corners_factor', '1.00')}" class="w-full mt-1 rounded-lg bg-white/5 border border-white/10 px-2 py-1.5 text-white"></label>
        <label class="text-[11px] text-slate-400">xG fatti<input id="analysis-${side}-xg-for" type="number" min="0" max="10" step="0.01" value="${xgValue(team, 'xg_for')}" placeholder="es. 1.55" class="w-full mt-1 rounded-lg bg-white/5 border border-white/10 px-2 py-1.5 text-white"></label>
        <label class="text-[11px] text-slate-400">xG subiti<input id="analysis-${side}-xg-against" type="number" min="0" max="10" step="0.01" value="${xgValue(team, 'xg_against')}" placeholder="es. 1.10" class="w-full mt-1 rounded-lg bg-white/5 border border-white/10 px-2 py-1.5 text-white"></label>
      </div>
    </div>`;
  panel.innerHTML = `
    <div class="flex items-start justify-between gap-4 mb-4">
      <div>
        <h3 class="text-lg font-bold text-white">${isManual ? 'Crea partita manuale' : 'Prepara analisi'}</h3>
        <p class="text-xs text-slate-400">Puoi modificare per questa simulazione Elo, xG fatti e xG subiti di entrambe le squadre. Le quote bookmaker sono facoltative.</p>
      </div>
      <button onclick="runPreparedAnalysis(${matchId || 'null'}, ${homeId || 'null'}, ${awayId || 'null'})" class="glow-btn text-xs py-2 px-4">Avvia analisi</button>
    </div>
    <div class="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-5 text-xs">
      ${teamFields('home', home, 'Team 1', 'D-D-D-D-D')}
      ${teamFields('away', away, 'Team 2', 'D-D-D-D-D')}
    </div>
    <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
      ${quoteMarketGroups.map(([category, title, keys]) => `<div class="bg-[#070d1e] rounded-xl p-3 border border-white/10"><h4 class="text-xs font-bold text-[#00f0ff] mb-2">${title}</h4><div class="grid grid-cols-2 gap-2">${keys.map(key => `<label class="text-[11px] text-slate-400">${key.replaceAll('_', '-')}<input data-odds-key="${category}:${key}" type="number" min="1.01" step="0.01" placeholder="Quota" class="w-full mt-1 rounded-lg bg-white/5 border border-white/10 px-2 py-1.5 text-white"></label>`).join('')}</div></div>`).join('')}
    </div>`;
}

async function runPreparedAnalysis(matchId, homeTeamId, awayTeamId) {
  const customOdds = {};
  document.querySelectorAll('[data-odds-key]').forEach(input => {
    if (input.value && Number(input.value) > 1) customOdds[input.dataset.oddsKey] = Number(input.value);
  });
  const numberOrNull = id => {
    const value = document.getElementById(id)?.value;
    return value === '' || value === undefined ? null : Number(value);
  };
  const textOrDefault = (id, fallback) => document.getElementById(id)?.value.trim() || fallback;
  const xgFields = [
    ['analysis-home-xg-for', 'xG fatti casa'],
    ['analysis-home-xg-against', 'xG subiti casa'],
    ['analysis-away-xg-for', 'xG fatti ospite'],
    ['analysis-away-xg-against', 'xG subiti ospite'],
  ];
  const missingXg = xgFields.filter(([id]) => numberOrNull(id) === null).map(([, label]) => label);
  if (missingXg.length > 0) {
    document.getElementById('assistant-explanation-text').innerText = `Per rendere l'analisi basata sugli xG devi compilare: ${missingXg.join(', ')}.`;
    return;
  }

  // Loading indicator temporaneo
  document.getElementById('modal-expected-score').innerText = "...";
  document.getElementById('modal-halftime-score').innerText = "Calcolo 50.000 simulazioni...";
  document.getElementById('assistant-explanation-text').innerText = "Simulazione Monte Carlo vettorializzata in corso...";
  document.getElementById('markets-full-grid').innerHTML = `
    <div class="col-span-2 p-12 text-center">
      <div class="animate-spin rounded-full h-10 w-10 border-b-2 border-[#00f0ff] mx-auto mb-3"></div>
      <span class="text-xs text-slate-400">Elaborazione 50.000 partite con modello Dixon-Coles...</span>
    </div>
  `;

  try {
    const res = await fetch('/api/simulate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        match_id: matchId,
        home_team_id: homeTeamId,
        away_team_id: awayTeamId,
        n_simulations: 50000,
        custom_odds: customOdds,
        require_xg: true,
        home_team: {
          name: textOrDefault('analysis-home-name', 'Team 1'),
          attack: numberOrNull('analysis-home-attack'),
          defense: numberOrNull('analysis-home-defense'),
          elo: numberOrNull('analysis-home-elo'),
          recent_form: textOrDefault('analysis-home-form', 'D-D-D-D-D'),
          cards_factor: numberOrNull('analysis-home-cards'),
          corners_factor: numberOrNull('analysis-home-corners'),
          xg_for: numberOrNull('analysis-home-xg-for'),
          xg_against: numberOrNull('analysis-home-xg-against'),
        },
        away_team: {
          name: textOrDefault('analysis-away-name', 'Team 2'),
          attack: numberOrNull('analysis-away-attack'),
          defense: numberOrNull('analysis-away-defense'),
          elo: numberOrNull('analysis-away-elo'),
          recent_form: textOrDefault('analysis-away-form', 'D-D-D-D-D'),
          cards_factor: numberOrNull('analysis-away-cards'),
          corners_factor: numberOrNull('analysis-away-corners'),
          xg_for: numberOrNull('analysis-away-xg-for'),
          xg_against: numberOrNull('analysis-away-xg-against'),
        },
      }),
    });
    if (!res.ok) throw new Error("Errore chiamata simulazione");
    const data = await res.json();
    state.currentSimulation = data;

    populateSimulationModal(data, homeTeamId, awayTeamId);
  } catch (err) {
    console.error("Errore simulazione:", err);
    document.getElementById('assistant-explanation-text').innerText = "Errore durante la simulazione: " + err.message;
  }
}

function closeSimulationModal() {
  document.getElementById('simulation-modal').classList.remove('open');
}

function populateSimulationModal(data, homeTeamId, awayTeamId) {
  const meta = data.metadata;
  const markets = data.markets;
  const conv = data.market_convergence;

  // Header squadre con fallback dai metadati
  const src = meta.database_source || {};
  const hId = homeTeamId || src.home_team_id;
  const aId = awayTeamId || src.away_team_id;

  const homeTeam = (hId && state.teamsMap[hId]) || { 
    name: meta.home_team, 
    elo: src.home_team_elo || 1750, 
    attack: 1.2, 
    defense: 1.0,
    recent_form: "W-D-W" 
  };
  const awayTeam = (aId && state.teamsMap[aId]) || { 
    name: meta.away_team, 
    elo: src.away_team_elo || 1700, 
    defense: 0.95, 
    attack: 1.0,
    recent_form: "L-W-D" 
  };

  document.getElementById('modal-home-name').innerText = homeTeam.name;
  document.getElementById('modal-away-name').innerText = awayTeam.name;
  document.getElementById('modal-home-elo').innerText = Math.round(homeTeam.elo);
  document.getElementById('modal-away-elo').innerText = Math.round(awayTeam.elo);
  document.getElementById('modal-home-att').innerText = (homeTeam.attack !== undefined) ? Number(homeTeam.attack).toFixed(2) : "1.20";
  document.getElementById('modal-home-def').innerText = (homeTeam.defense !== undefined) ? Number(homeTeam.defense).toFixed(2) : "1.00";
  document.getElementById('modal-away-att').innerText = (awayTeam.attack !== undefined) ? Number(awayTeam.attack).toFixed(2) : "1.00";
  document.getElementById('modal-away-def').innerText = (awayTeam.defense !== undefined) ? Number(awayTeam.defense).toFixed(2) : "0.95";
  document.getElementById('modal-home-form').innerHTML = renderFormPills(homeTeam.recent_form || "W-D-W");
  document.getElementById('modal-away-form').innerHTML = renderFormPills(awayTeam.recent_form || "L-W-D");

  document.getElementById('modal-exec-time').innerText = meta.execution_time_ms;
  document.getElementById('modal-sim-badge').innerText = `50.000 iterazioni • ${meta.execution_time_ms} ms • λ: ${meta.expected_goals_home_lambda} vs μ: ${meta.expected_goals_away_mu}`;
  const xgInputs = meta.xg_inputs || {};
  const xgStatus = xgInputs.applied ? 'xG inseriti applicati' : 'xG non inseriti';
  const enteredXg = xgInputs.applied
    ? ` • Inseriti H ${xgInputs.home_xg_for ?? '-'}/${xgInputs.home_xg_against ?? '-'} A ${xgInputs.away_xg_for ?? '-'}/${xgInputs.away_xg_against ?? '-'}`
    : '';
  const organic = meta.organic_expected_goals_home !== undefined
    ? ` • Organico ${meta.organic_expected_goals_home}/${meta.organic_expected_goals_away}`
    : '';
  document.getElementById('modal-sim-badge').innerText += ` • ${xgStatus}${enteredXg}${organic}`;

  // 1X2 Probabilità e barre
  const p1 = markets["1x2_finale"]["1"];
  const px = markets["1x2_finale"]["X"];
  const p2 = markets["1x2_finale"]["2"];

  document.getElementById('prob-1-val').innerText = `${p1.percentage}%`;
  document.getElementById('prob-x-val').innerText = `${px.percentage}%`;
  document.getElementById('prob-2-val').innerText = `${p2.percentage}%`;

  document.getElementById('prob-1-count').innerText = `${p1.count.toLocaleString()} / 50.000`;
  document.getElementById('prob-x-count').innerText = `${px.count.toLocaleString()} / 50.000`;
  document.getElementById('prob-2-count').innerText = `${p2.count.toLocaleString()} / 50.000`;

  document.getElementById('bar-prob-1').style.width = `${p1.percentage}%`;
  document.getElementById('bar-prob-x').style.width = `${px.percentage}%`;
  document.getElementById('bar-prob-2').style.width = `${p2.percentage}%`;

  // Stima punteggio più probabile
  const lambda = meta.expected_goals_home_lambda;
  const mu = meta.expected_goals_away_mu;
  const ftHome = Math.round(lambda);
  const ftAway = Math.round(mu);
  const htHome = Math.round(lambda * 0.45);
  const htAway = Math.round(mu * 0.45);
  const shHome = ftHome - htHome;
  const shAway = ftAway - htAway;

  document.getElementById('modal-expected-score').innerText = `${ftHome} - ${ftAway}`;
  document.getElementById('modal-halftime-score').innerText = `(1T: ${htHome} - ${htAway} • 2T: ${shHome} - ${shAway})`;

  // Precedenti Diretti Head-to-Head (H2H)
  const h2hBadge = document.getElementById('h2h-summary-badge');
  const h2hList = document.getElementById('h2h-matches-list');
  if (data.h2h && data.h2h.matches && data.h2h.matches.length > 0) {
    const sum = data.h2h.summary || {};
    if (h2hBadge) {
      h2hBadge.innerText = `${sum.team_a_name || 'Casa'} ${sum.team_a_wins || 0}V • ${sum.draws || 0}P • ${sum.team_b_name || 'Ospite'} ${sum.team_b_wins || 0}V (Media gol: ${sum.avg_goals || '0.0'})`;
    }
    if (h2hList) {
      h2hList.innerHTML = data.h2h.matches.map(m => {
        let badgeStyle = 'bg-white/10 text-slate-300 border-white/10';
        if (m.outcome_1x2 === '1') badgeStyle = 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30';
        else if (m.outcome_1x2 === 'X') badgeStyle = 'bg-amber-500/20 text-amber-300 border border-amber-500/30';
        else if (m.outcome_1x2 === '2') badgeStyle = 'bg-rose-500/20 text-rose-300 border border-rose-500/30';

        return `
          <div class="bg-[#070d1e] border border-white/5 rounded-xl p-2.5 text-center flex flex-col justify-between hover:border-[#00f0ff]/20 transition">
            <div class="text-[10px] text-slate-400 font-medium truncate mb-1">${m.match_date || 'Recente'}</div>
            <div class="text-xs font-semibold text-white mb-1.5 leading-tight">
              <div class="truncate">${m.home_team_name}</div>
              <div class="text-[#00f0ff] font-bold font-mono text-sm my-0.5">${m.home_goals} - ${m.away_goals}</div>
              <div class="truncate">${m.away_team_name}</div>
            </div>
            <div class="flex items-center justify-center">
              <span class="text-[10px] font-bold px-2 py-0.5 rounded-full ${badgeStyle}">Segno ${m.outcome_1x2}</span>
            </div>
          </div>
        `;
      }).join('');
    }
  } else {
    if (h2hBadge) h2hBadge.innerText = "Nessun precedente trovato";
    if (h2hList) h2hList.innerHTML = `<div class="col-span-full text-center text-xs text-slate-400 py-3">Nessun precedente recente registrato tra queste due formazioni.</div>`;
  }

  // Value Betting Consigliato
  const vb = data.value_betting;
  if (vb && vb.best_value_bet) {
    const b = vb.best_value_bet;
    const evVal = Number(b.ev_pct);
    const evStr = `${evVal > 0 ? '+' : ''}${evVal.toFixed(1)}% EV`;
    document.getElementById('vb-badge-ev').innerText = evStr;
    document.getElementById('vb-market-name').innerText = b.market;
    document.getElementById('vb-odds').innerText = Number(b.odds).toFixed(2);
    document.getElementById('vb-prob-sim').innerText = `${Number(b.simulated_prob_pct).toFixed(1)}%`;
    document.getElementById('vb-prob-imp').innerText = `${Number(b.implied_prob_pct).toFixed(1)}%`;
  } else {
    document.getElementById('vb-badge-ev').innerText = "0.0% EV";
    document.getElementById('vb-market-name').innerText = "Nessun Value Bet rilevante";
    document.getElementById('vb-odds').innerText = "-";
    document.getElementById('vb-prob-sim').innerText = "-";
    document.getElementById('vb-prob-imp').innerText = "-";
  }

  // Sintesi Narrativa AI
  const narrativeEl = document.getElementById('assistant-narrative-text');
  if (narrativeEl) {
    narrativeEl.innerText = data.ai_narrative || "Analisi Monte Carlo completata con successo sulle 50.000 iterazioni.";
  }

  // Assistente Statistico (Convergenza & Sinergie)
  const bestSynergy = conv.best_synergy_market;
  document.getElementById('assistant-top-combo-name').innerText = bestSynergy ? `${bestSynergy.combo} (Lift ${bestSynergy.lift}x)` : "Analisi Completata";
  document.getElementById('assistant-explanation-text').innerText = conv.assistant_explanation;

  const topCombosContainer = document.getElementById('top-combos-pills');
  if (conv.top_combos) {
    topCombosContainer.innerHTML = conv.top_combos.map(c => `
      <span class="px-2.5 py-1 rounded-lg bg-white/5 border border-white/10 text-xs text-slate-200">
        <strong class="text-[#00f0ff]">${c.combo}</strong>: ${c.percentage}% (${c.count.toLocaleString()} su 50k) • Lift: <span class="text-amber-400 font-bold">${c.lift}x</span>
      </span>
    `).join('');
  }

  // Reset Bottone Salva nello Storico
  const saveBtnText = document.getElementById('btn-save-text');
  if (saveBtnText) saveBtnText.innerText = "Salva nello Storico";
  const saveBtn = document.getElementById('btn-save-simulation');
  if (saveBtn) {
    saveBtn.disabled = false;
    saveBtn.classList.remove('opacity-50', 'cursor-not-allowed');
  }

  // Griglia 15 Mercati
  renderMarketsGrid();
  if (window.lucide) window.lucide.createIcons();
}

function filterMarketCategory(catKey) {
  state.currentMarketCategory = catKey;
  document.querySelectorAll('.market-filter-btn').forEach(btn => {
    btn.classList.remove('active', 'bg-[#00f0ff]/20', 'text-[#00f0ff]', 'border-[#00f0ff]/30');
    btn.classList.add('bg-white/5', 'text-slate-300', 'border-white/10');
  });
  event.target.classList.add('active', 'bg-[#00f0ff]/20', 'text-[#00f0ff]', 'border-[#00f0ff]/30');
  event.target.classList.remove('bg-white/5', 'text-slate-300', 'border-white/10');

  renderMarketsGrid();
}

function renderMarketsGrid() {
  const container = document.getElementById('markets-full-grid');
  if (!container || !state.currentSimulation) return;

  const m = state.currentSimulation.markets;
  const cat = state.currentMarketCategory;

  const cards = [];

  // Helper per blocco mercato
  function createMarketCard(title, icon, items) {
    return `
      <div class="bg-[#0b1638] border border-white/10 hover:border-[#00f0ff]/30 rounded-xl p-4 transition">
        <div class="flex items-center gap-2 mb-3">
          <i data-lucide="${icon}" class="w-4 h-4 text-[#00f0ff]"></i>
          <h5 class="text-sm font-bold text-white font-['Outfit']">${title}</h5>
        </div>
        <div class="space-y-2">
          ${items.map(it => `
            <div>
              <div class="flex items-center justify-between text-xs mb-1">
                <span class="text-slate-300">${it.label}</span>
                <span class="font-mono">
                  <strong class="text-white">${it.stat.percentage}%</strong>
                  <span class="text-slate-400 text-[10px]">(${it.stat.count.toLocaleString()})</span>
                </span>
              </div>
              <div class="progress-bar-container">
                <div class="progress-bar-fill" style="width: ${it.stat.percentage}%"></div>
              </div>
            </div>
          `).join('')}
        </div>
      </div>
    `;
  }

  // 1. 1X2 Finale
  if (cat === 'all' || cat === '1x2_ou') {
    cards.push(createMarketCard("1X2 Finale", "check-circle-2", [
      { label: "1 (Casa)", stat: m["1x2_finale"]["1"] },
      { label: "X (Pareggio)", stat: m["1x2_finale"]["X"] },
      { label: "2 (Ospite)", stat: m["1x2_finale"]["2"] },
    ]));

    // 2. 1X2 Primo Tempo
    cards.push(createMarketCard("1X2 Primo Tempo (1T)", "clock", [
      { label: "1T: 1", stat: m["1x2_primo_tempo"]["1"] },
      { label: "1T: X", stat: m["1x2_primo_tempo"]["X"] },
      { label: "1T: 2", stat: m["1x2_primo_tempo"]["2"] },
    ]));

    // 3. Over / Under Finale
    cards.push(createMarketCard("Over / Under Finale", "arrow-up-down", rangeMarketItems(m["over_under_finale"])));

    // 4. Over / Under Primo Tempo
    cards.push(createMarketCard("Over / Under Primo Tempo", "hourglass", rangeMarketItems(m["over_under_primo_tempo"], "1T: ")));
  }

  // 5. Goal / No Goal & 6. Goal / No Goal 1T
  if (cat === 'all' || cat === 'goal_mg') {
    cards.push(createMarketCard("Goal / No Goal Finale", "target", [
      { label: "Goal (Entrambe segnano)", stat: m["goal_nogoal_finale"]["Goal"] },
      { label: "No Goal", stat: m["goal_nogoal_finale"]["No_Goal"] },
    ]));

    cards.push(createMarketCard("Goal / No Goal Primo Tempo", "sparkle", [
      { label: "1T Goal", stat: m["goal_nogoal_primo_tempo"]["Goal"] },
      { label: "1T No Goal", stat: m["goal_nogoal_primo_tempo"]["No_Goal"] },
    ]));

    // 9. Multigol Partita
    cards.push(createMarketCard("Multigol Partita", "hash", rangeMarketItems(m["multigol_partita"], "Multigol ")));

    // 10. Multigol Casa & 11. Multigol Ospite
    cards.push(createMarketCard("Multigol Casa", "home", rangeMarketItems(m["multigol_casa"], "Casa ")));
    cards.push(createMarketCard("Multigol Ospite", "plane", rangeMarketItems(m["multigol_ospite"], "Ospite ")));
  }

  // 7. Cartellini & 8. Corner
  if (cat === 'all' || cat === 'cards_corners') {
    cards.push(createMarketCard(`Cartellini (Media attesa: ${m["cartellini"].expected_mean})`, "file-text", [
      { label: "Fascia 0-3 Cartellini", stat: m["cartellini"]["fascia_0_3"] },
      { label: "Fascia 4-5 Cartellini", stat: m["cartellini"]["fascia_4_5"] },
      { label: "Fascia 6+ Cartellini", stat: m["cartellini"]["fascia_6_plus"] },
      { label: "Over 4.5 Cartellini", stat: m["cartellini"]["Over_4.5"] },
      { label: "Under 4.5 Cartellini", stat: m["cartellini"]["Under_4.5"] },
    ]));

    cards.push(createMarketCard(`Calci d'Angolo (Media attesa: ${m["calci_dangolo"].expected_mean})`, "flag", [
      { label: "Fascia 0-8 Corner", stat: m["calci_dangolo"]["fascia_0_8"] },
      { label: "Fascia 9-11 Corner", stat: m["calci_dangolo"]["fascia_9_11"] },
      { label: "Fascia 12+ Corner", stat: m["calci_dangolo"]["fascia_12_plus"] },
      { label: "Over 9.5 Corner", stat: m["calci_dangolo"]["Over_9.5"] },
      { label: "Under 9.5 Corner", stat: m["calci_dangolo"]["Under_9.5"] },
    ]));
  }

  // 12. Multigol Combo & 13. Multigol Tempi & 14/15 Over Squadre
  if (cat === 'all' || cat === 'combos') {
    cards.push(createMarketCard("Multigol Casa + Ospite (Combo)", "shuffle", [
      { label: "Casa 1-2 + Ospite 0-1", stat: m["multigol_casa_combo_ospite"]["Casa_1_2_e_Ospite_0_1"] },
      { label: "Casa 1-2 + Ospite 1-2", stat: m["multigol_casa_combo_ospite"]["Casa_1_2_e_Ospite_1_2"] },
      { label: "Casa 1-3 + Ospite 0-1", stat: m["multigol_casa_combo_ospite"]["Casa_1_3_e_Ospite_0_1"] },
      { label: "Casa 2-3 + Ospite 0-1", stat: m["multigol_casa_combo_ospite"]["Casa_2_3_e_Ospite_0_1"] },
    ]));

    cards.push(createMarketCard("Multigol 1° Tempo + 2° Tempo (Combo)", "timer", [
      { label: "1T 0-1 + 2T 1-2", stat: m["multigol_primo_tempo_combo_secondo_tempo"]["1T_0_1_e_2T_1_2"] },
      { label: "1T 1-2 + 2T 1-2", stat: m["multigol_primo_tempo_combo_secondo_tempo"]["1T_1_2_e_2T_1_2"] },
      { label: "1T 0-1 + 2T 1-3", stat: m["multigol_primo_tempo_combo_secondo_tempo"]["1T_0_1_e_2T_1_3"] },
      { label: "1T 1-2 + 2T 0-1", stat: m["multigol_primo_tempo_combo_secondo_tempo"]["1T_1_2_e_2T_0_1"] },
    ]));

    cards.push(createMarketCard("Over / Under Squadra Casa", "home", rangeMarketItems(m["over_under_squadra_casa"], "Casa ")));

    cards.push(createMarketCard("Over / Under Squadra Ospite", "plane", rangeMarketItems(m["over_under_squadra_ospite"], "Ospite ")));
  }

  container.innerHTML = cards.join('');
  if (window.lucide) window.lucide.createIcons();
}

// ================= GESTIONE STORICO SIMULAZIONI (SIMULATION HISTORY) =================

async function saveCurrentSimulation() {
  if (!state.currentSimulation) return;
  const sim = state.currentSimulation;
  const meta = sim.metadata || {};
  const dbSrc = meta.database_source || {};
  const conv = sim.market_convergence || {};
  const bestSynergy = conv.best_synergy_market || {};
  const vb = sim.value_betting || {};
  const bestVb = vb.best_value_bet || {};

  const payload = {
    match_id: dbSrc.match_id || null,
    home_team_name: meta.home_team || "Squadra Casa",
    away_team_name: meta.away_team || "Squadra Ospite",
    home_elo: dbSrc.home_team_elo || 1500,
    away_elo: dbSrc.away_team_elo || 1500,
    simulations_count: 50000,
    execution_time_ms: meta.execution_time_ms || 40,
    best_convergence_market: bestSynergy.combo || "N/A",
    best_convergence_lift: bestSynergy.lift || 1.0,
    best_convergence_prob: bestSynergy.percentage || 0.0,
    best_value_bet_market: bestVb.market || "N/A",
    best_value_bet_odds: bestVb.odds || 1.0,
    best_value_bet_ev: bestVb.ev_pct || 0.0,
    assistant_narrative: sim.ai_narrative || "",
    full_results_json: JSON.stringify(sim)
  };

  const btnText = document.getElementById('btn-save-text');
  const btn = document.getElementById('btn-save-simulation');
  if (btnText) btnText.innerText = "Salvataggio...";
  if (btn) btn.disabled = true;

  try {
    const res = await fetch('/api/history', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (!res.ok) throw new Error("Errore nel salvataggio");
    if (btnText) btnText.innerText = "✅ Salvato nello Storico!";
  } catch (e) {
    console.error("Errore salvataggio:", e);
    if (btnText) btnText.innerText = "❌ Errore";
    if (btn) btn.disabled = false;
  }
}

async function openHistoryModal() {
  const modal = document.getElementById('history-modal');
  modal.classList.add('open');
  const listContainer = document.getElementById('history-list-container');
  const countLabel = document.getElementById('history-count-label');

  listContainer.innerHTML = `
    <div class="p-8 text-center text-slate-400">
      <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-[#00f0ff] mx-auto mb-2"></div>
      Caricamento storico da SQLite...
    </div>
  `;

  try {
    const res = await fetch('/api/history?limit=50');
    const items = await res.json();

    if (countLabel) {
      countLabel.innerText = `${items.length} ${items.length === 1 ? 'analisi salvata' : 'analisi salvate'}`;
    }

    if (!items || items.length === 0) {
      listContainer.innerHTML = `
        <div class="p-8 text-center text-slate-400">
          <i data-lucide="archive" class="w-10 h-10 mx-auto mb-2 text-slate-500"></i>
          Nessuna simulazione ancora salvata nello storico.<br>
          <span class="text-xs text-slate-500">Esegui una simulazione e clicca su "Salva nello Storico".</span>
        </div>
      `;
      if (window.lucide) window.lucide.createIcons();
      return;
    }

    listContainer.innerHTML = items.map(it => {
      const dt = it.created_at ? new Date(it.created_at).toLocaleString('it-IT', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' }) : 'Recente';
      const evText = it.best_value_bet_ev !== null && it.best_value_bet_ev !== undefined ? `${it.best_value_bet_ev > 0 ? '+' : ''}${Number(it.best_value_bet_ev).toFixed(1)}% EV` : '';

      return `
        <div class="bg-[#070d1e] border border-white/10 hover:border-[#00f0ff]/30 rounded-xl p-4 transition flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
          <div class="flex-grow">
            <div class="flex items-center gap-2 mb-1">
              <span class="text-xs font-mono text-[#00f0ff]">${dt}</span>
              <span class="text-xs text-slate-400">•</span>
              <span class="text-xs text-slate-400">${Number(it.simulations_count).toLocaleString()} run (${it.execution_time_ms} ms)</span>
            </div>
            <h4 class="text-base font-bold text-white font-['Outfit'] flex items-center gap-2">
              <span>${it.home_team_name}</span>
              <span class="text-xs text-slate-400">vs</span>
              <span>${it.away_team_name}</span>
            </h4>
            <div class="flex flex-wrap items-center gap-2 mt-2 text-xs">
              ${it.best_convergence_market ? `
                <span class="px-2 py-0.5 rounded-md bg-[#0284c7]/20 border border-[#00f0ff]/20 text-[#00f0ff]">
                  🎯 <strong>${it.best_convergence_market}</strong> (${it.best_convergence_prob}%)
                </span>
              ` : ''}
              ${it.best_value_bet_market ? `
                <span class="px-2 py-0.5 rounded-md bg-emerald-500/20 border border-emerald-500/30 text-emerald-300 font-mono">
                  💎 ${it.best_value_bet_market} @ ${Number(it.best_value_bet_odds).toFixed(2)} (${evText})
                </span>
              ` : ''}
            </div>
          </div>
          <div class="flex items-center gap-2 self-end sm:self-center flex-shrink-0">
            <button onclick="loadHistoryItem(${it.id})" class="px-3 py-1.5 rounded-lg bg-[#00f0ff]/15 hover:bg-[#00f0ff]/30 text-[#00f0ff] border border-[#00f0ff]/30 text-xs font-bold flex items-center gap-1.5 transition">
              <i data-lucide="eye" class="w-3.5 h-3.5"></i>
              <span>Visualizza</span>
            </button>
            <button onclick="deleteHistoryItem(${it.id}, event)" class="p-1.5 rounded-lg bg-white/5 hover:bg-rose-500/20 text-slate-400 hover:text-rose-400 border border-white/10 hover:border-rose-500/30 text-xs transition" title="Elimina dallo storico">
              <i data-lucide="trash-2" class="w-4 h-4"></i>
            </button>
          </div>
        </div>
      `;
    }).join('');

    if (window.lucide) window.lucide.createIcons();
  } catch (err) {
    console.error("Errore caricamento storico:", err);
    listContainer.innerHTML = `<div class="p-4 text-center text-rose-400 text-xs">Errore nel caricamento: ${err.message}</div>`;
  }
}

function closeHistoryModal() {
  document.getElementById('history-modal').classList.remove('open');
}

async function loadHistoryItem(historyId) {
  try {
    const res = await fetch(`/api/history/${historyId}`);
    if (!res.ok) throw new Error("Errore nel recupero della simulazione");
    const item = await res.json();
    
    let parsedData = null;
    if (item.full_results_json) {
      try {
        parsedData = JSON.parse(item.full_results_json);
      } catch (e) {
        console.warn("Snapshot JSON non valido, fallback:", e);
      }
    }

    if (parsedData && parsedData.markets) {
      closeHistoryModal();
      state.currentSimulation = parsedData;
      const src = parsedData.metadata?.database_source || {};
      populateSimulationModal(parsedData, src.home_team_id, src.away_team_id);
      document.getElementById('simulation-modal').classList.add('open');
      window.scrollTo({ top: 0, behavior: 'smooth' });
    } else {
      alert("Dati completi non disponibili per questa simulazione archiviata.");
    }
  } catch (err) {
    alert("Errore nel caricamento dell'analisi: " + err.message);
  }
}

async function deleteHistoryItem(historyId, ev) {
  if (ev) ev.stopPropagation();
  if (!confirm("Sei sicuro di voler eliminare questa simulazione dallo storico?")) return;

  try {
    const res = await fetch(`/api/history/${historyId}`, { method: 'DELETE' });
    if (!res.ok) throw new Error("Errore durante l'eliminazione");
    await openHistoryModal();
  } catch (err) {
    alert("Errore nell'eliminazione: " + err.message);
  }
}

