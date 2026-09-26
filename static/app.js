'use strict';

/* Орбита — интерфейс без внешних зависимостей. */
const paths = {
  database: '<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v7c0 1.7 3.6 3 8 3s8-1.3 8-3V5M4 12v7c0 1.7 3.6 3 8 3s8-1.3 8-3v-7"/>',
  network: '<circle cx="12" cy="12" r="3"/><circle cx="4" cy="5" r="2"/><circle cx="20" cy="5" r="2"/><circle cx="5" cy="20" r="2"/><circle cx="20" cy="19" r="2"/><path d="m6 7 4 3m4 0 4-3m-8 7-4 4m8-4 4 3"/>',
  users: '<circle cx="8" cy="8" r="3"/><path d="M2 20v-2a6 6 0 0 1 12 0v2M16 5a3 3 0 0 1 0 6m1 3a5 5 0 0 1 5 5v1"/>',
  flask: '<path d="M9 3h6M10 3v6L4 19a1.5 1.5 0 0 0 1.3 2h13.4a1.5 1.5 0 0 0 1.3-2L14 9V3M7 14h10"/><path d="M10 17h.01M14 18h.01"/>',
  book: '<path d="M12 5c-2-2-6-3-10-2v16c4-1 8 0 10 2m0-16c2-2 6-3 10-2v16c-4-1-8 0-10 2V5"/>',
  folder: '<path d="M3 7V4h6l2 3h10v13H3V7Z"/>',
  save: '<path d="M5 3h12l4 4v14H3V3h2ZM7 3v6h10V3M7 21v-8h10v8"/>',
  upload: '<path d="M12 16V3m-5 5 5-5 5 5M4 15v6h16v-6"/>',
  download: '<path d="M12 3v13m-5-5 5 5 5-5M4 15v6h16v-6"/>',
  arrow: '<path d="M4 12h16m-6-6 6 6-6 6"/>',
  chevron: '<path d="m9 5 7 7-7 7"/>',
  search: '<circle cx="10" cy="10" r="6.5"/><path d="m15 15 6 6"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  minus: '<path d="M5 12h14"/>',
  fit: '<path d="M8 3H3v5M16 3h5v5M3 16v5h5M21 16v5h-5"/><circle cx="12" cy="12" r="2.5"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7h.01"/>',
  check: '<path d="m5 12 4 4L20 5"/>',
  close: '<path d="m6 6 12 12M18 6 6 18"/>',
  orbit: '<ellipse cx="12" cy="12" rx="10" ry="5" transform="rotate(-35 12 12)"/><ellipse cx="12" cy="12" rx="10" ry="5" transform="rotate(35 12 12)"/><circle cx="12" cy="12" r="1.5"/>',
  timer: '<circle cx="12" cy="13" r="8"/><path d="M9 2h6M12 2v3M12 9v5l3 2"/>',
  link: '<path d="m9 15 6-6m-5-3 2-2a5 5 0 0 1 7 7l-2 2M14 18l-2 2a5 5 0 0 1-7-7l2-2"/>',
  shield: '<path d="m12 2 9 4v6c0 6-9 10-9 10S3 18 3 12V6l9-4Z"/><path d="m8 12 3 3 5-6"/>',
  trash: '<path d="M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7M14 10v7"/>',
  sort: '<path d="M8 4v16m-3-3 3 3 3-3M16 20V4m-3 3 3-3 3 3"/>',
  chart: '<path d="M3 3v18h18M7 15l5-6 4 3 5-7"/>',
  file: '<path d="M14 2H4v20h16V8l-6-6Zm0 0v6h6M8 12h8M8 16h6"/>',
  refresh: '<path d="M20 7A9 9 0 0 0 4 6l-2 4m0-6v6h6m-4 7a9 9 0 0 0 16 1l2-4m0 6v-6h-6"/>',
  eye: '<path d="M1 12s4-7 11-7 11 7 11 7-4 7-11 7S1 12 1 12Z"/><circle cx="12" cy="12" r="3"/>',
};
const icon = (name, cls = '') => `<svg class="icon ${cls}" viewBox="0 0 24 24" aria-hidden="true">${paths[name] || paths.info}</svg>`;
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const number = value => value == null || !Number.isFinite(Number(value)) ? '—' : new Intl.NumberFormat('ru-RU', {maximumFractionDigits:0}).format(Number(value));
const decimal = (value, digits = 2) => value == null || !Number.isFinite(Number(value)) ? '—' : Number(value).toLocaleString('ru-RU', {minimumFractionDigits:digits, maximumFractionDigits:digits});
const pct = value => value == null || !Number.isFinite(Number(value)) ? '—' : `${decimal(Number(value) * 100, 1)}%`;
const bounded = (n, lo, hi) => Math.max(lo, Math.min(hi, Number(n)));
const nodeId = value => String(typeof value === 'object' && value !== null ? value.id : value);
const workspace = document.querySelector('#workspace');
const state = {
  view:'graph', graph:null, analysis:null, experiments:null, demos:[], projects:[], demoId:null,
  options:{root:null, radius:1, threshold:.65, exclude_root:true, max_pairs:2000},
  experimentConfig:{clone_count:3, retention:.8, noise_levels:[0,.05,.15], repeats:3, seed:42, threshold:.65, root:null, exclude_root:true},
  selectedPair:null, selectedNode:null, selectedOrbit:null, nodeQuery:'', pairQuery:'', pairMode:'all',
  pairSort:'score', pairSortDir:-1, pairPage:0, pageSize:20, busy:null, projectId:null, projectName:'',
  vkUser:'', vkLimit:40, importName:'', error:null, graphRevision:0, experimentTab:'summary', modalReturn:null,
};
const graphView = {graph:null, positions:new Map(), tx:0, ty:0, zoom:1, drag:null, svg:null, height:700, layoutHeight:0};
const orbitPalette = ['#578b77','#a2b58a','#eab061','#83a9a0','#d38d6b','#aca1bd','#8dabc0','#c4c193','#729e91','#b09e7e'];
const methodNames = {neighbors:'Сходство соседей', symmetry:'Симметрии', combined:'Комбинация'};
const methodColors = {neighbors:'#84a297', symmetry:'#c1ad8d', combined:'#ed6b35'};
const viewNames = {data:'Данные', graph:'Граф', candidates:'Кандидаты', experiments:'Эксперименты'};
const NS = 'http://www.w3.org/2000/svg';

function hydrateIcons(root = document) {
  root.querySelectorAll('[data-icon]').forEach(el => { el.innerHTML = icon(el.dataset.icon); });
}
function toast(message, kind = 'success') {
  const item = document.createElement('div'); item.className = `toast ${kind === 'error' ? 'error' : ''}`;
  item.innerHTML = `${icon(kind === 'error' ? 'info' : 'check')}<span></span><button aria-label="Закрыть уведомление">×</button>`;
  item.querySelector('span').textContent = message;
  item.querySelector('button').addEventListener('click', () => item.remove());
  const stack = document.querySelector('#toast-stack');
  while (stack.children.length >= 2) stack.firstElementChild.remove();
  stack.append(item);
  window.setTimeout(() => item.remove(), kind === 'error' ? 12000 : 6500);
}
function apiMessage(detail) {
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) return detail.map(e => `${(e.loc || []).filter(v => v !== 'body').join(' → ')}: ${e.msg || 'неверное значение'}`).join('; ');
  return 'Не удалось выполнить запрос. Проверьте данные и попробуйте ещё раз.';
}
async function api(path, {body, method = body ? 'POST' : 'GET', timeout = 90000, download = false} = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);
  try {
    const response = await fetch(path, {method, headers:body ? {'Content-Type':'application/json'} : {}, body:body ? JSON.stringify(body) : undefined, signal:controller.signal, cache:'no-store'});
    if (!response.ok) {
      let detail; try { detail = await response.json(); } catch (_) { }
      throw new Error(detail ? apiMessage(detail.detail) : `Сервер ответил с ошибкой ${response.status}.`);
    }
    return download ? {blob:await response.blob(), disposition:response.headers.get('Content-Disposition')} : await response.json();
  } catch (error) {
    if (error.name === 'AbortError') throw new Error('Время ожидания истекло. Уменьшите граф или число повторов и попробуйте снова.');
    if (error instanceof TypeError) throw new Error('Нет связи с локальным сервером. Проверьте, что Орбита запущена, и повторите запрос.');
    throw error;
  } finally { clearTimeout(timer); }
}
function updateBusy() {
  document.querySelector('#busy-strip').hidden = !state.busy;
  document.querySelector('#busy-label').textContent = state.busy || '';
  workspace.setAttribute('aria-busy', String(Boolean(state.busy)));
  document.querySelector('#save-project').disabled = Boolean(state.busy) || !state.graph;
  document.querySelectorAll('[data-lock]').forEach(el => { el.disabled = Boolean(state.busy) || el.dataset.unavailable === 'true'; });
}
async function task(label, fn) {
  if (state.busy) return;
  state.busy = label; updateBusy();
  try { await fn(); state.error = null; }
  catch (error) { state.error = error.message; toast(error.message, 'error'); }
  finally { state.busy = null; updateBusy(); }
}
const lock = (unavailable = false) => `data-lock data-unavailable="${unavailable}" ${state.busy || unavailable ? 'disabled' : ''}`;
const displayedGraph = () => state.analysis?.graph || state.graph;
const graphNodeMaps = new WeakMap();
function nodeMap() {
  const graph = displayedGraph();
  if (!graph) return new Map();
  if (!graphNodeMaps.has(graph)) graphNodeMaps.set(graph, new Map(graph.nodes.map(n => [String(n.id), n])));
  return graphNodeMaps.get(graph);
}
function labelFor(id) { return nodeMap().get(String(id))?.label || String(id); }
function orbitColor(id) { const i = Number(id); if (state.analysis?.orbits.some(o => o.id === i && o.size === 1)) return '#b2bdb0'; if (!Number.isFinite(i)) return '#9bb4a1'; return i >= 0 && i < orbitPalette.length ? orbitPalette[i] : `hsl(${((i * 137.508) % 360).toFixed(2)} 30% 59%)`; }
function isSynthetic() {
  const source = String(state.graph?.metadata?.source || '').toLowerCase();
  return Boolean(state.demoId) || /synthet|demo|модель|демонстр/.test(source);
}
function dataBanner() {
  if (!state.graph) return '';
  return `<div class="data-banner">${icon(isSynthetic() ? 'flask' : 'shield')}<span><strong>${esc(state.graph.name || 'Граф')}.</strong> ${esc(state.graph.metadata?.description || 'Локальный анализ связей.')}</span><button data-action="methodology">Как читать результат ${icon('arrow')}</button></div>`;
}
function warningsHTML(warnings) {
  const items = [...new Set((warnings || []).filter(Boolean).map(String))];
  return items.length ? `<details class="warning-details"><summary>Замечания к данным · ${items.length}</summary><ul>${items.map(w => `<li>${esc(w)}</li>`).join('')}</ul></details>` : '';
}
function heading(eyebrow, title, description, actions = '') {
  return `<div class="page-heading"><div><div class="eyebrow">${eyebrow}</div><h1>${title}</h1><p>${description}</p></div>${actions ? `<div class="heading-actions">${actions}</div>` : ''}</div>`;
}
function graphPill() { return state.graph ? `<span class="dataset-pill">${icon('database')}<span title="${esc(state.graph.name)}">${esc(state.graph.name || 'Без названия')}</span></span>` : ''; }
function emptyHTML(title, message, symbol = 'network', action = '') {
  return `<div class="empty-state"><div class="empty-illustration">${icon(symbol)}</div><h2>${title}</h2><p>${message}</p>${action}</div>`;
}
function render() {
  document.querySelectorAll('[data-view]').forEach(button => { const active = button.dataset.view === state.view; button.classList.toggle('active', active); if (active) button.setAttribute('aria-current', 'page'); else button.removeAttribute('aria-current'); });
  document.querySelector('#current-section').textContent = viewNames[state.view];
  document.title = `${viewNames[state.view]} · Орбита`;
  workspace.innerHTML = ({data:renderData, graph:renderGraphPage, candidates:renderCandidatesPage, experiments:renderExperimentsPage}[state.view])();
  hydrateIcons(workspace); updateBusy();
  if (state.view === 'graph') drawGraph();
  if (state.view === 'experiments' && state.experiments) drawExperimentChart();
  bindDropzone();
}
function setView(view, push = true) {
  if (!viewNames[view]) return;
  state.view = view; render();
  if (push) history.replaceState(null, '', `#${view}`);
}
function acceptGraph(graph, {demoId = null, projectId = null, projectName = ''} = {}) {
  state.graph = graph; state.analysis = null; state.experiments = null;
  state.demoId = demoId; state.projectId = projectId; state.projectName = projectName;
  state.selectedPair = null; state.selectedNode = null; state.selectedOrbit = null;
  state.nodeQuery = ''; state.pairQuery = ''; state.pairPage = 0; state.graphRevision++;
  const ids = new Set(graph.nodes.map(n => String(n.id)));
  const suggested = graph.metadata?.root == null ? null : String(graph.metadata.root);
  state.options.root = suggested && ids.has(suggested) ? suggested : null;
  state.options.radius = 1;
  graphView.graph = null;
}
function invalidateAnalysis() {
  state.analysis = null; state.experiments = null; state.selectedPair = null;
  state.selectedNode = null; state.selectedOrbit = null; state.pairPage = 0;
  graphView.graph = null;
}
async function analyzeCurrent() {
  if (!state.graph) return;
  const result = await api('/api/analyze', {body:{graph:state.graph, options:{...state.options}}, timeout:130000});
  state.analysis = result; state.selectedPair = null; state.selectedNode = null; state.selectedOrbit = null;
  state.pairPage = 0; graphView.graph = null; render();
}
async function loadDemo(id, goToGraph = true) {
  await task('Загружаем граф и вычисляем симметрии…', async () => {
    const graph = await api(`/api/demos/${encodeURIComponent(id)}`);
    acceptGraph(graph, {demoId:id});
    if (goToGraph) state.view = 'graph';
    render(); await analyzeCurrent();
    toast('Граф загружен. Анализ готов.');
  });
}
function statsHTML() {
  const s = state.analysis?.summary;
  const n = displayedGraph()?.nodes.length;
  const e = displayedGraph()?.edges.length;
  const cards = [
    ['network','Вершины',number(s?.node_count ?? n),`${number(s?.edge_count ?? e)} связей`,false],
    ['orbit','Орбиты',number(s?.orbit_count),s ? `${number(s.nontrivial_orbits)} нетривиальных` : 'Нужен анализ',false],
    ['users','Кандидаты',number(s?.candidate_count),s ? `порог ≥ ${decimal(state.options.threshold)}` : 'Пары аккаунтов',true],
    ['timer','Время анализа',s ? decimal(s.elapsed_ms, 0) : '—',s ? 'миллисекунд' : 'Локальное вычисление',false],
  ];
  return `<div class="stats-grid">${cards.map(([i,l,v,d,a]) => `<div class="stat-card ${a ? 'accent' : ''}"><span class="stat-label">${icon(i)}${l}</span><strong class="stat-number">${v}</strong><span class="stat-detail">${d}</span></div>`).join('')}</div>`;
}
function analysisControls() {
  const nodes = state.graph?.nodes || [];
  return `<section class="panel control-panel"><div class="panel-header"><h2>Параметры</h2></div><div class="panel-body">
    <div class="form-field"><label for="root-select">Центр окружения</label><select id="root-select" ${lock(!state.graph)}><option value="">Весь граф</option>${nodes.map(n => `<option value="${esc(n.id)}" ${String(n.id) === state.options.root ? 'selected' : ''}>${esc(n.label || n.id)}</option>`).join('')}</select><small>Аккаунт, чьё окружение анализируется.</small></div>
    <div class="form-field"><label for="radius-select">Радиус</label><select id="radius-select" ${lock(!state.graph || !state.options.root)}>${[1,2,3].map(r => `<option value="${r}" ${r === state.options.radius ? 'selected' : ''}>${r} ${r === 1 ? 'шаг' : 'шага'} от центра</option>`).join('')}</select></div>
    <div class="form-field"><label class="inline-label" for="threshold-range"><span>Порог сходства</span><span class="value-badge" id="threshold-display">${decimal(state.options.threshold)}</span></label><input id="threshold-range" type="range" min="0" max="1" step=".05" value="${state.options.threshold}" ${lock(!state.graph)}><div class="range-labels"><span>0,00</span><span>1,00</span></div></div>
    <label class="checkbox-field"><input id="exclude-root" type="checkbox" ${state.options.exclude_root ? 'checked' : ''} ${lock(!state.graph || !state.options.root)}><span>Не считать центр общим другом</span></label>
    <button class="button button-orange full-width" data-action="analyze" ${lock(!state.graph)}>${icon('orbit')}Анализировать</button>
  </div></section>`;
}
function renderGraphPage() {
  const canvas = `<section class="panel canvas-panel"><div class="canvas-top"><div class="canvas-title"><h2>Карта связей</h2><span>НЕОРИЕНТИРОВАННЫЙ ГРАФ</span></div><div class="canvas-search">${icon('search')}<input class="input" id="node-search" placeholder="Найти аккаунт…" aria-label="Поиск вершины по имени или ID" value="${esc(state.nodeQuery)}"></div></div><div class="graph-stage" id="graph-stage"><svg id="network" class="network-svg" viewBox="0 0 1000 700" role="img" aria-label="Интерактивная карта связей графа. Нажмите вершину, чтобы увидеть её окружение."></svg>${!state.analysis && state.graph ? '<div class="graph-stale">Параметры изменены. Запустите анализ, чтобы обновить результат.</div>' : ''}<div class="graph-controls"><button class="icon-button" data-action="zoom-in" aria-label="Приблизить" title="Приблизить">${icon('plus')}</button><span class="zoom-level" id="zoom-level">100%</span><button class="icon-button" data-action="zoom-out" aria-label="Отдалить" title="Отдалить">${icon('minus')}</button><button class="icon-button" data-action="fit-graph" aria-label="Показать весь граф" title="Показать весь граф">${icon('fit')}</button></div><span class="graph-guide">Перетащите вершину или поле.<br>Колесо мыши — масштаб.</span></div><div class="canvas-foot"><span class="legend-strong"><i class="legend-dot" style="background:#6e9985"></i>Цвет — нетривиальная орбита</span><span><i class="legend-dot" style="background:#ecaa69"></i>Выбранная пара</span><span>Серый — орбита из 1 вершины</span></div></section>`;
  return heading('Структура графа','Увидеть связи. Найти сходство.','Цвет вершины — её орбита: группа аккаунтов, взаимозаменяемых в этом графе. Выберите вершину, чтобы рассмотреть её окружение.', graphPill() + (state.analysis ? `<button class="button button-outline button-small" data-action="export-subgraph" aria-label="Скачать JSON выбранного подграфа" ${lock()}>${icon('download')}<span>JSON подграфа</span></button>` : '')) + dataBanner() + statsHTML() +
    (state.graph ? `<div class="graph-workbench">${analysisControls()}${canvas}${inspectorHTML()}</div>${warningsHTML(state.analysis?.warnings || state.graph.metadata?.warnings)}<div class="section-line"><h2>Похожие пары аккаунтов <span class="count-label">${number(state.analysis?.summary?.candidate_count)}</span></h2><button class="button button-text button-small" data-view="candidates">Все кандидаты ${icon('arrow')}</button></div><div id="candidate-table-region">${candidateTableHTML(true)}</div><p class="table-caption">Кандидаты — пары с наибольшим структурным сходством окружений.</p>` : `<section class="panel">${emptyHTML('Начните с графа', 'Откройте модельный пример или загрузите собственный список связей.', 'network', '<button class="button button-orange" data-view="data">Выбрать данные</button>')}</section>`);
}
function inspectorHTML() {
  let title = 'Орбиты графа', body;
  const nodes = nodeMap();
  if (state.selectedPair) {
    title = 'Проверка пары';
    const pair = state.selectedPair, a = nodes.get(String(pair.source)), b = nodes.get(String(pair.target));
    const neighbors = id => new Set((displayedGraph()?.edges || []).flatMap(e => String(e.source) === id ? [String(e.target)] : String(e.target) === id ? [String(e.source)] : []).filter(id => !(state.options.exclude_root && id === state.options.root)));
    const na = neighbors(String(pair.source)), nb = neighbors(String(pair.target));
    const aOnly = [...na].filter(id => !nb.has(id)); const bOnly = [...nb].filter(id => !na.has(id));
    body = `${nodeIdentity(a, pair.source, '#e59a5e')}<div class="pair-connector"></div>${nodeIdentity(b, pair.target, '#548f7c')}<div class="info-grid"><div class="info-cell"><span>Оценка сходства</span><strong>${decimal(pair.score)}</strong></div><div class="info-cell"><span>Индекс Жаккара</span><strong>${decimal(pair.jaccard)}</strong></div></div><span class="badge ${pair.same_orbit ? '' : 'badge-neutral'}">${pair.same_orbit ? `Орбита ${esc(pair.orbit_id ?? '—')}` : 'Разные орбиты'}</span>${pair.twin_type ? `<span class="badge badge-orange" style="margin-left:4px">${pair.twin_type === 'true' || pair.twin_type === 'true_twins' ? 'Истинные близнецы' : pair.twin_type === 'false' || pair.twin_type === 'false_twins' ? 'Ложные близнецы' : esc(pair.twin_type)}</span>` : ''}${neighborSection('Общие соседи', pair.common_neighbors || [], true)}${neighborSection(`Только у ${a?.label || pair.source}`, aOnly)}${neighborSection(`Только у ${b?.label || pair.target}`, bOnly)}${pair.reasons?.length ? `<ul class="reason-list">${pair.reasons.map(r => `<li>${esc(r)}</li>`).join('')}</ul>` : ''}${state.view !== 'graph' ? '<button class="button button-outline full-width" style="margin-top:17px" data-view="graph">Показать на графе</button>' : ''}`;
  } else if (state.selectedNode && nodes.has(String(state.selectedNode))) {
    title = 'Вершина графа'; const node = nodes.get(String(state.selectedNode));
    const adj = (displayedGraph()?.edges || []).flatMap(e => String(e.source) === String(node.id) ? [String(e.target)] : String(e.target) === String(node.id) ? [String(e.source)] : []);
    body = `${nodeIdentity(node, node.id, orbitColor(node.orbit))}<div class="info-grid"><div class="info-cell"><span>Связей</span><strong>${number(node.degree ?? adj.length)}</strong></div><div class="info-cell"><span>Орбита</span><strong>${state.analysis ? esc(node.orbit ?? '—') : '—'}</strong></div></div>${neighborSection('Соседи', adj)}<button class="button button-outline full-width" style="margin-top:18px" data-action="node-as-root" data-node="${esc(node.id)}" ${lock()}>Сделать центром</button><p class="orbit-note">ID: ${esc(node.id)}. Цвет вершины основан на структуре, а не на разметке.</p>`;
  } else if (state.analysis) {
    const orbits = [...state.analysis.orbits].sort((a,b) => b.size-a.size || a.id-b.id);
    const nontrivial = orbits.filter(o => o.size > 1);
    const singletons = orbits.length - nontrivial.length;
    body = `<p class="inspector-intro">Номер орбиты определяет структурную группу. Цвет помогает ориентироваться; одиночные орбиты показаны серым.</p><div class="orbit-list">${nontrivial.length ? nontrivial.map(o => `<button class="orbit-row ${state.selectedOrbit === o.id ? 'selected' : ''}" data-action="select-orbit" data-orbit="${o.id}"><i class="orbit-color" style="background:${orbitColor(o.id)}"></i><span class="orbit-name">Орбита ${o.id}</span><span class="orbit-count">${o.size} вершин</span></button>`).join('') : '<div class="inspector-empty">Нетривиальных орбит нет.</div>'}</div><p class="orbit-note">${number(singletons)} одноэлементных орбит.<br>Порядок группы: <span class="mono">${esc(state.analysis.summary.group_order)}</span>.<br><br>Выберите орбиту, вершину или пару в таблице для подробного просмотра.</p>`;
  } else { body = `<div class="inspector-empty">${icon('orbit')}<p>Орбиты появятся<br>после анализа графа.</p></div>`; }
  return `<aside class="panel inspector-panel" id="inspector"><div class="panel-header"><h2>${title}</h2>${state.selectedPair || state.selectedNode || state.selectedOrbit != null ? `<button class="icon-button" data-action="clear-selection" aria-label="Снять выделение">${icon('close')}</button>` : `<span class="panel-kicker">${state.analysis ? number(state.analysis.summary.orbit_count) : '—'}</span>`}</div><div class="panel-body">${body}</div></aside>`;
}
function nodeIdentity(node, id, color) {
  const label = String(node?.label || id);
  return `<div class="node-identity"><span class="node-avatar" style="background:${color}">${esc(label.slice(0,1).toLocaleUpperCase())}</span><div><strong>${esc(label)}</strong><small>${esc(id)}</small></div></div>`;
}
function neighborSection(title, ids, common = false) {
  return `<div class="neighbor-section"><h3>${esc(title)} · ${number(ids.length)}</h3><div class="neighbor-chips">${ids.length ? ids.map(id => `<button class="neighbor-chip ${common ? 'common' : ''}" data-action="select-node" data-node="${esc(id)}">${esc(labelFor(id))}</button>`).join('') : '<span class="small muted">Нет</span>'}</div></div>`;
}
function filteredPairs() {
  const query = state.pairQuery.trim().toLowerCase();
  return (state.analysis?.pairs || []).map((pair,index) => ({pair,index})).filter(({pair}) => {
    if (state.pairMode === 'orbit' && !pair.same_orbit) return false;
    if (state.pairMode === 'similar' && pair.same_orbit) return false;
    return !query || [pair.source,pair.target,labelFor(pair.source),labelFor(pair.target)].some(v => String(v).toLowerCase().includes(query));
  }).sort((a,b) => {
    let x,y;
    if (state.pairSort === 'pair') { x = `${labelFor(a.pair.source)} ${labelFor(a.pair.target)}`; y = `${labelFor(b.pair.source)} ${labelFor(b.pair.target)}`; return x.localeCompare(y,'ru') * state.pairSortDir; }
    if (state.pairSort === 'common_neighbors') { x=a.pair.common_neighbors.length; y=b.pair.common_neighbors.length; }
    else { x=Number(a.pair[state.pairSort]); y=Number(b.pair[state.pairSort]); }
    return (x-y)*state.pairSortDir || a.index-b.index;
  });
}
function candidateTableHTML(preview = false) {
  if (!state.analysis) return `<section class="panel">${emptyHTML('Пока без результатов', 'Запустите анализ выбранного графа. Здесь появятся структурно похожие пары и объяснения.', 'users', state.graph ? `<button class="button button-orange" data-action="analyze" ${lock()}>${icon('orbit')}Анализировать граф</button>` : '<button class="button button-orange" data-view="data">Выбрать данные</button>')}</section>`;
  const pairs = preview ? (state.analysis.pairs || []).map((pair,index) => ({pair,index})) : filteredPairs();
  if (!pairs.length) return `<section class="panel">${emptyHTML(state.pairQuery || state.pairMode !== 'all' ? 'Пары не найдены' : 'Кандидатов выше порога нет', state.pairQuery || state.pairMode !== 'all' ? 'Измените поисковый запрос или фильтр. Исходные результаты сохранены.' : 'Это тоже результат: выбранный граф не содержит пар с достаточными структурными признаками при текущем пороге.', 'users', !preview && (state.pairQuery || state.pairMode !== 'all') ? '<button class="button button-outline" data-action="reset-filters">Сбросить фильтры</button>' : '')}</section>`;
  const pageCount = Math.ceil(pairs.length / state.pageSize);
  state.pairPage = Math.max(0, Math.min(state.pairPage,pageCount-1));
  const visible = preview ? pairs.slice(0,4) : pairs.slice(state.pairPage*state.pageSize,(state.pairPage+1)*state.pageSize);
  const columns = [['pair','Пара аккаунтов'],['same_orbit','Симметрия'],['common_neighbors','Общие соседи'],['jaccard','Жаккар'],['score','Сходство']];
  return `<section class="panel"><div class="table-wrap"><table class="table"><caption class="sr-only">Структурно похожие пары аккаунтов</caption><thead><tr>${columns.map(([key,name]) => `<th scope="col" ${!preview ? `aria-sort="${state.pairSort === key ? state.pairSortDir > 0 ? 'ascending' : 'descending' : 'none'}"` : ''}>${preview ? name : `<button data-action="sort-pairs" data-sort="${key}">${name}${state.pairSort === key ? `<span aria-hidden="true">${state.pairSortDir > 0 ? '↑' : '↓'}</span>` : icon('sort')}</button>`}</th>`).join('')}<th scope="col"><span class="sr-only">Посмотреть пару</span></th></tr></thead><tbody>${visible.map(({pair,index}) => `<tr data-pair="${index}" tabindex="0" aria-label="${esc(labelFor(pair.source))} и ${esc(labelFor(pair.target))}, сходство ${decimal(pair.score)}" class="${state.selectedPair === pair ? 'selected' : ''}"><td><div class="pair-names"><span class="mini-avatar">${esc(labelFor(pair.source).slice(0,1))}</span><span class="pair-name" title="${esc(labelFor(pair.source))}">${esc(labelFor(pair.source))}</span>${icon('link')}<span class="pair-name" title="${esc(labelFor(pair.target))}">${esc(labelFor(pair.target))}</span></div></td><td><span class="badge ${pair.same_orbit ? 'badge-teal' : 'badge-neutral'}">${pair.same_orbit ? 'Одна орбита' : 'Разные орбиты'}</span></td><td class="td-number">${number(pair.common_neighbors?.length)}</td><td class="td-number">${decimal(pair.jaccard)}</td><td class="td-number"><span class="score-wrap"><strong style="font-weight:500;color:#b77642">${decimal(pair.score)}</strong><span class="score-bar"><i style="width:${bounded(pair.score*100,0,100)}%"></i></span></span></td><td>${icon('chevron')}</td></tr>`).join('')}</tbody></table></div><div class="table-foot"><span>${preview ? `Показаны ${visible.length} из ${number(state.analysis.summary.candidate_count)} кандидатов` : `Показаны ${state.pairPage*state.pageSize+1}–${Math.min((state.pairPage+1)*state.pageSize,pairs.length)} из ${number(pairs.length)} пар`}</span>${preview ? '<span>Нажмите пару для подробностей</span>' : `<div class="page-buttons"><button class="icon-button" data-action="prev-page" ${state.pairPage === 0 ? 'disabled' : ''} aria-label="Предыдущая страница"><span style="transform:rotate(180deg)">${icon('chevron')}</span></button><span>${state.pairPage+1} / ${pageCount}</span><button class="icon-button" data-action="next-page" ${state.pairPage >= pageCount-1 ? 'disabled' : ''} aria-label="Следующая страница">${icon('chevron')}</button></div>`}</div></section>`;
}
function renderCandidatesPage() {
  const exportButtons = `<button class="button button-outline button-small" data-action="export-csv" aria-label="Скачать кандидатов CSV" ${lock(!state.analysis)}>${icon('download')}<span>CSV</span></button><button class="button button-dark button-small" data-action="export-html" aria-label="Скачать отчёт HTML" ${lock(!state.analysis)}>${icon('file')}<span>Отчёт HTML</span></button>`;
  return heading('Кандидаты / пары для проверки','Похожие пары аккаунтов','Отсортированы по структурной оценке: сверху — самые похожие окружения. Нажмите строку, чтобы сравнить пары по друзьям.', exportButtons) + dataBanner() + `<div class="panel filter-bar"><div class="search-field">${icon('search')}<input class="input" id="pair-search" placeholder="Имя или ID аккаунта…" aria-label="Поиск пары по имени или ID" value="${esc(state.pairQuery)}"></div><div class="segmented" aria-label="Фильтр пар">${[['all','Все пары'],['orbit','Одна орбита'],['similar','Разные орбиты']].map(([id,name]) => `<button data-action="filter-pairs" data-filter="${id}" class="${state.pairMode === id ? 'active' : ''}" aria-pressed="${state.pairMode === id}">${name}</button>`).join('')}</div></div><div class="table-view-hint" style="margin:10px 3px 13px">Нажмите заголовок столбца, чтобы изменить сортировку. Нажмите строку, чтобы сравнить окружения.</div><div class="table-split"><div id="candidate-table-region">${candidateTableHTML()}</div>${inspectorHTML()}</div>${evaluationHTML()}${warningsHTML(state.analysis?.warnings)}<p class="table-caption">Порог: ${decimal(state.options.threshold)}. Экспорт CSV содержит все возвращённые пары, включая скрытые текущим фильтром. Разметка аккаунтов не участвует в вычислении сходства.</p>`;
}
function evaluationHTML() {
  const evaluation = state.analysis?.evaluation;
  if (!evaluation) return '';
  const metrics = ['precision','recall','f1'].filter(key => Object.hasOwn(evaluation,key));
  return `<div class="notice">${icon('info')}<div>${evaluation.note ? `<p>${esc(evaluation.note)}</p>` : ''}${metrics.length ? `<div class="metric-line" style="margin-top:8px">${metrics.map(key => `<span class="metric-pill">${key === 'f1' ? 'F1' : key === 'precision' ? 'Precision' : 'Recall'} <strong>${decimal(evaluation[key])}</strong></span>`).join('')}</div>` : ''}</div></div>`;
}

function renderData() {
  const graph = state.graph;
  const labeled = graph?.nodes.filter(n => n.truth && n.truth !== 'unknown').length || 0;
  const projectList = state.projects.length ? state.projects.map(p => `<div class="project-row">${icon('folder')}<div class="project-content"><strong>${esc(p.name)}</strong><small>${number(p.node_count)} вершин · ${number(p.edge_count)} связей · ${formatDate(p.updated_at)}</small></div><div class="project-actions"><button class="button button-outline" data-action="load-project" data-project="${esc(p.id)}" ${lock()}>Открыть</button><button class="icon-button danger-text" data-action="delete-project" data-project="${esc(p.id)}" aria-label="Удалить проект ${esc(p.name)}" ${lock()}>${icon('trash')}</button></div></div>`).join('') : '<p class="inline-empty">Сохранённых проектов пока нет. Загрузите граф, выполните анализ и нажмите «Сохранить».</p>';
  return heading('Данные / рабочее пространство','Загрузите граф связей','Файл CSV со столбцами source и target, JSON со списком вершин и рёбер — или сбор окружения VK по ID и токену.',graphPill()) +
  `<div class="data-grid"><div class="data-main"><section class="panel"><div class="panel-header"><h2>Граф</h2>${graph ? `<button class="button button-text button-small" data-action="export-json" ${lock()}>${icon('download')}JSON</button>` : ''}</div><div class="panel-body"><div class="dropzone" id="graph-dropzone">${icon('upload')}<strong>Перетащите файл сюда</strong><p>CSV / TSV со списком связей или JSON с вершинами и рёбрами.<br>До 2000 вершин, 100 000 связей и 20 МБ.</p><span class="button button-dark">Выбрать файл</span><input type="file" id="graph-file" accept=".csv,.tsv,.txt,.json,text/csv,text/tab-separated-values,text/plain,application/json" aria-label="Загрузить граф в формате CSV или JSON" ${lock()}></div><div class="format-note">CSV: столбцы <code>source</code> и <code>target</code>. JSON: массивы <code>nodes</code> и <code>edges</code>.<br>Файлы обрабатываются вашим локальным сервером.</div>${graph ? `<div class="dataset-summary"><div><strong>${esc(graph.name || 'Без названия')}</strong><p>${number(graph.nodes.length)} вершин · ${number(graph.edges.length)} связей · ${number(labeled)} размеченных вершин</p></div>${icon('network')}</div><div class="labels-area"><div><h3 style="font-size:11px;margin:0 0 5px">Разметка для оценки</h3><p>CSV: <span class="mono">id,truth,clone_of</span>.<br>Метки используются только для оценки качества.</p></div><label class="button button-outline button-small file-button">${icon('upload')}Загрузить метки<input type="file" id="labels-file" accept=".csv,.tsv,.txt,.json,text/csv,text/tab-separated-values,text/plain,application/json" aria-label="Загрузить разметку" ${lock()}></label></div>${warningsHTML(graph.metadata?.warnings)}<button class="button button-orange" data-action="analyze-open" ${lock()}>${icon('orbit')}Перейти к исследованию</button>` : '<p class="inline-empty">Набор данных ещё не выбран.</p>'}</div></section>
  <section class="panel" id="projects-section"><div class="panel-header"><h2>Сохранённые проекты</h2><button class="icon-button" data-action="refresh-projects" aria-label="Обновить проекты" ${lock()}>${icon('refresh')}</button></div><div class="panel-body" style="padding-top:3px;padding-bottom:3px">${projectList}</div></section></div>
  <div class="data-aside"><section class="panel"><div class="panel-header"><h2>Готовые примеры</h2><span class="badge badge-orange">Синтетика</span></div><div class="panel-body"><div class="demo-grid">${state.demos.length ? state.demos.map((d,i) => `<button class="demo-card ${state.demoId === d.id ? 'selected' : ''}" data-action="load-demo" data-demo="${esc(d.id)}" ${lock()}>${icon(['network','orbit','chart'][i%3])}<strong>${esc(d.name)}</strong><small>${esc(d.description)}</small></button>`).join('') : '<p class="inline-empty">Примеры недоступны. Проверьте подключение к серверу.</p>'}</div><p class="vk-caption">Изучите поведение алгоритма на структурах с заранее известными свойствами.</p></div></section>
  <details class="panel details-block"><summary class="panel-header">Окружение VK · по запросу</summary><div class="panel-body"><form id="vk-form" class="vk-form"><div class="form-field"><label for="vk-user">Числовой ID пользователя</label><input id="vk-user" class="input" value="${esc(state.vkUser)}" placeholder="Например, 123456" inputmode="numeric" pattern="[1-9][0-9]*" autocomplete="off" required ${lock()}></div><div class="form-field"><label for="vk-limit">Друзей, до</label><input id="vk-limit" class="input" type="number" min="1" max="80" value="${state.vkLimit}" required ${lock()}></div><button class="button button-outline full-width wide" type="submit" ${lock()}>${icon('download')}Получить граф</button></form><p class="vk-caption">Токен VK настроен на сервере (файл .env). Доступность списков друзей зависит от приватности профилей.</p><div class="privacy-line">${icon('shield')}Запрос к VK выполняется только по вашей команде.</div></div></details></div></div>`;
}
function formatDate(value) {
  if (!value) return '';
  const date = new Date(value); return Number.isNaN(date.valueOf()) ? esc(value) : date.toLocaleDateString('ru-RU',{day:'numeric',month:'short',year:'numeric'});
}
function experimentControls() {
  const c=state.experimentConfig;
  return `<section class="panel experiment-form"><div class="panel-header"><h2>Условия эксперимента</h2></div><div class="panel-body"><div class="form-field"><label for="exp-clones">Добавить клонов</label><input class="input" id="exp-clones" type="number" min="1" max="10" step="1" value="${c.clone_count}" ${lock(!state.graph)}><small>Источники выбираются случайно по заданному seed.</small></div><div class="two-fields"><div class="form-field"><label for="exp-repeats">Повторов</label><input class="input" id="exp-repeats" type="number" min="1" max="5" step="1" value="${c.repeats}" ${lock(!state.graph)}></div><div class="form-field"><label for="exp-seed">Seed</label><input class="input" id="exp-seed" type="number" min="0" max="2147483647" step="1" value="${c.seed}" ${lock(!state.graph)}></div></div><div class="form-field"><label class="inline-label" for="exp-retention">Сохранить связей <span class="value-badge" id="exp-retention-display">${pct(c.retention)}</span></label><input id="exp-retention" type="range" min="0" max="1" step=".05" value="${c.retention}" ${lock(!state.graph)}><small>Вероятность сохранения каждой связи исходной вершины у клона.</small></div><div class="form-field"><label for="exp-noise">Уровни шума</label><input class="input" id="exp-noise" value="${c.noise_levels.join('; ')}" placeholder="0; 0.05; 0.15" ${lock(!state.graph)}><small>Доли заменяемых связей от 0 до 1. Разделяйте точкой с запятой.</small></div><div class="form-field"><label for="exp-threshold">Порог обнаружения</label><input class="input" id="exp-threshold" type="number" min="0" max="1" step=".05" value="${c.threshold}" ${lock(!state.graph)}><small>Фиксируется до запуска для всех методов.</small></div><div class="divider"></div><button class="button button-orange full-width" data-action="run-experiments" ${lock(!state.graph)}>${icon('flask')}Запустить эксперимент</button><p class="run-note">Все методы получают одинаковый граф и одинаковый шум в каждом повторе. Seed делает генерацию воспроизводимой.</p></div></section>`;
}
function renderExperimentsPage() {
  const controls = `<button class="button button-outline button-small" data-action="export-experiments" aria-label="Скачать результаты эксперимента CSV" ${lock(!state.experiments)}>${icon('download')}<span>Результаты CSV</span></button>`;
  const result = state.experiments;
  const main = result ? `<section class="panel"><div class="panel-header"><div><h2>Устойчивость к изменению связей</h2><span class="subtitle">F1 по уровням шума · среднее по повторам</span></div><span class="badge badge-orange">Эксперимент</span></div><div class="chart-wrap"><svg id="experiment-chart" class="experiment-chart" viewBox="0 0 800 340" role="img" aria-label="График F1 для трёх методов при разных уровнях шума"></svg></div><div class="chart-legend">${Object.keys(methodNames).map(m => `<span><i style="background:${methodColors[m]}"></i>${methodNames[m]}</span>`).join('')}</div><div class="experiment-baseline">Синтетические клоны добавлены к выбранному графу; шум изменяет связи между остальными вершинами.</div></section><section class="panel"><div class="panel-header"><h2>Измеренные результаты</h2><div class="segmented"><button data-action="exp-tab" data-tab="summary" class="${state.experimentTab === 'summary' ? 'active' : ''}">Средние</button><button data-action="exp-tab" data-tab="all" class="${state.experimentTab === 'all' ? 'active' : ''}">Все повторы</button><button data-action="exp-tab" data-tab="control" class="${state.experimentTab === 'control' ? 'active' : ''}">Контроль</button></div></div>${experimentTableHTML()}</section>${warningsHTML(result.warnings)}${result.example_graph ? `<div class="notice">${icon('network')}<div><p>Откройте один из сгенерированных графов, чтобы исследовать его симметрии вручную.</p><button class="button button-outline button-small" style="margin-top:9px" data-action="open-experiment-graph" ${lock()}>Исследовать пример ${icon('arrow')}</button></div></div>` : ''}` : `<section class="panel">${emptyHTML('Проверить гипотезу на практике','Добавьте модельные клоны, постепенно изменяйте связи и сравните три подхода на одних и тех же данных.','flask',!state.graph ? '<button class="button button-orange" data-view="data">Сначала выбрать граф</button>' : '')}</section>`;
  return heading('Эксперименты / проверка метода','Насколько метод устойчив','Система добавляет в копию графа модельных двойников, портит часть связей и показывает, какое правило поиска справляется лучше.',controls) + dataBanner() + `<div class="experiment-layout">${experimentControls()}<div class="experiment-results">${main}</div></div><div class="method-explainer"><div class="method-card"><strong>01 · Сходство соседей (Жаккар)</strong><p>Индекс Жаккара сравнивает множества соседей. Базовый метод для поиска похожего окружения.</p></div><div class="method-card"><strong>02 · Симметрии</strong><p>Проверка принадлежности к одной орбите автоморфизмов. Описывает точную структурную взаимозаменяемость.</p></div><div class="method-card"><strong>03 · Комбинация</strong><p>Среднее орбитального признака и индекса Жаккара. Порог выше 0,5 требует общей орбиты.</p></div></div>`;
}
function experimentTableHTML() {
  const rows = state.experimentTab === 'summary' ? state.experiments.summary || [] : (state.experiments.rows || []).filter(r => state.experimentTab === 'control' ? r.control : !r.control);
  const full = state.experimentTab !== 'summary';
  if (!rows.length) return '<p class="inline-empty" style="padding:20px">Для этого раздела нет результатов.</p>';
  return `<div class="table-wrap"><table class="table"><caption class="sr-only">${state.experimentTab === 'control' ? 'Контрольные графы без добавленных клонов' : 'Метрики эксперимента'}</caption><thead><tr><th scope="col">Шум</th>${full ? '<th scope="col">Повтор</th>' : ''}<th scope="col">Метод</th><th scope="col">Precision</th><th scope="col">Recall</th><th scope="col">F1</th>${full ? '<th scope="col">TP / FP / FN</th><th scope="col">Время, мс</th>' : ''}</tr></thead><tbody>${rows.map(r => `<tr><td class="td-number">${pct(r.noise)}</td>${full ? `<td class="td-number">${number(r.repeat)}</td>` : ''}<td><span style="display:inline-flex;align-items:center;gap:7px"><i class="legend-dot" style="background:${methodColors[r.method] || '#8ba179'}"></i>${esc(methodNames[r.method] || r.method)}</span></td><td class="td-number">${decimal(r.precision,3)}</td><td class="td-number">${decimal(r.recall,3)}</td><td class="td-number" style="color:${r.method === 'combined' ? '#be793e' : '#64785b'}">${decimal(r.f1,3)}</td>${full ? `<td class="td-number">${number(r.tp)} / ${number(r.fp)} / ${number(r.fn)}</td><td class="td-number">${decimal(r.elapsed_ms,1)}</td>` : ''}</tr>`).join('')}</tbody></table></div><div class="table-foot"><span>${state.experimentTab === 'control' ? 'Контроль: графы без добавленных клонов, оценивается число ложных срабатываний.' : 'Precision — точность · Recall — полнота · F1 — их гармоническое среднее.'}</span></div><p class="table-caption" style="padding:0 15px 13px">«—» означает, что метрика не определена при нулевом знаменателе. Контрольные графы не входят в основные средние.</p>`;
}

function svgElement(tag, attrs = {}, text = null) {
  const el = document.createElementNS(NS,tag);
  for (const [key,value] of Object.entries(attrs)) el.setAttribute(key,String(value));
  if (text != null) el.textContent = String(text);
  return el;
}
function drawExperimentChart() {
  const svg = document.querySelector('#experiment-chart'); if (!svg) return;
  const rows = state.experiments?.summary || [];
  const levels = [...new Set(rows.map(r => Number(r.noise)).filter(Number.isFinite))].sort((a,b) => a-b);
  const width=800, left=60, right=29, top=23, bottom=62, height=340;
  const x = n => levels.length <= 1 ? (left+width-right)/2 : left + (n-levels[0])/(levels.at(-1)-levels[0])*(width-left-right);
  const y = n => top+(1-n)*(height-top-bottom);
  for(let i=0;i<=4;i++) {
    const v=i/4;
    svg.append(svgElement('line',{x1:left,y1:y(v),x2:width-right,y2:y(v),stroke:'#e5ecdc','stroke-dasharray':i ? '4 5' : 'none'}));
    svg.append(svgElement('text',{x:left-14,y:y(v)+4,'text-anchor':'end',class:'chart-tick'},decimal(v,2)));
  }
  levels.forEach(level => svg.append(svgElement('text',{x:x(level),y:height-bottom+24,'text-anchor':'middle',class:'chart-tick'},pct(level))));
  svg.append(svgElement('text',{x:19,y:17,class:'chart-axis-label'},'F1'));
  svg.append(svgElement('text',{x:(width+left-right)/2,y:height-10,'text-anchor':'middle',class:'chart-axis-label'},'Доля изменённых связей'));
  for(const method of Object.keys(methodNames)) {
    const data=rows.filter(r => r.method===method).sort((a,b)=>a.noise-b.noise);
    let segment=[];
    const flush=() => { if(segment.length > 1) svg.append(svgElement('polyline',{points:segment.join(' '),fill:'none',stroke:methodColors[method],'stroke-width':method==='combined'?3:2,'stroke-linecap':'round','stroke-linejoin':'round'})); segment=[]; };
    for(const row of data) {
      if(row.f1 == null || !Number.isFinite(Number(row.f1))) {flush(); continue;}
      segment.push(`${x(Number(row.noise))},${y(bounded(row.f1,0,1))}`);
    }
    flush();
    for(const row of data) {
      if(row.f1 == null || !Number.isFinite(Number(row.f1))) continue;
      const point=svgElement('circle',{cx:x(Number(row.noise)),cy:y(bounded(row.f1,0,1)),r:method==='combined'?5:4,fill:methodColors[method],stroke:'#fffefa','stroke-width':2,tabindex:'0'});
      point.append(svgElement('title',{},`${methodNames[method]}: шум ${pct(row.noise)}, F1 ${decimal(row.f1,3)}`)); svg.append(point);
    }
  }
  if(!rows.some(r => r.f1 != null && Number.isFinite(Number(r.f1)))) svg.append(svgElement('text',{x:width/2,y:height/2,'text-anchor':'middle',class:'chart-axis-label'},'F1 не определена для этих результатов'));
}

function preparePositions(graph) {
  if (graphView.graph === graph && Math.abs(graphView.layoutHeight - graphView.height) < 2) return;
  graphView.graph=graph; graphView.positions=new Map(); graphView.tx=0; graphView.ty=0; graphView.zoom=1;
  graphView.layoutHeight=graphView.height;
  const centerY=graphView.height/2-15, spanY=Math.max(350,graphView.height-210);
  const nodes=graph.nodes, finite=nodes.every(n => n.x != null && n.y != null && Number.isFinite(Number(n.x)) && Number.isFinite(Number(n.y)));
  if(finite && nodes.length > 1) {
    const xs=nodes.map(n=>Number(n.x)), ys=nodes.map(n=>Number(n.y));
    const minX=Math.min(...xs),maxX=Math.max(...xs),minY=Math.min(...ys),maxY=Math.max(...ys);
    const scaleX=740/Math.max(maxX-minX,.001),scaleY=spanY/Math.max(maxY-minY,.001);
    nodes.forEach(n => graphView.positions.set(String(n.id),{x:500+(Number(n.x)-(minX+maxX)/2)*scaleX,y:centerY+(Number(n.y)-(minY+maxY)/2)*scaleY}));
  } else {
    const sorted=[...nodes].sort((a,b) => (Number(b.degree)||0)-(Number(a.degree)||0) || String(a.id).localeCompare(String(b.id)));
    if(sorted.length === 1) graphView.positions.set(String(sorted[0].id),{x:500,y:centerY});
    else sorted.forEach((n,i) => { const angle=(Math.PI*2*i/Math.max(sorted.length,1))-Math.PI/2; graphView.positions.set(String(n.id),{x:500+Math.cos(angle)*365,y:centerY+Math.sin(angle)*spanY/2}); });
  }
}
function spreadOverlaps(positions, degree) {
  const ids=[...positions.keys()];
  const size=id=>{const d=degree.get(id)||0;return Math.min(27,10+Math.sqrt(d)*2.4)+4;};
  const cell=30, passes=10;
  for(let pass=0;pass<passes;pass++){
    const grid=new Map();
    for(const id of ids){
      const p=positions.get(id), key=`${Math.floor(p.x/cell)}:${Math.floor(p.y/cell)}`;
      (grid.get(key)||grid.set(key,[]).get(key)).push(id);
    }
    let moved=0;
    for(const [key,members] of grid){
      const [cx,cy]=key.split(':').map(Number);
      const cand=[];
      for(let ox=-1;ox<=1;ox++)for(let oy=-1;oy<=1;oy++){const n=grid.get(`${cx+ox}:${cy+oy}`);if(n)cand.push(...n);}
      for(const a of members){
        const ra=size(a),pa=positions.get(a);
        for(const b of cand){
          if(b<=a)continue;
          const pb=positions.get(b),rb=size(b),min=ra+rb;
          const dx=pb.x-pa.x,dy=pb.y-pa.y,d2=dx*dx+dy*dy;
          if(d2>0&&d2<min*min){
            const d=Math.sqrt(d2),push=(min-d)/2*0.9,ux=dx/d,uy=dy/d;
            pa.x-=ux*push;pa.y-=uy*push;pb.x+=ux*push;pb.y+=uy*push;moved++;
          }
        }
      }
    }
    if(!moved)break;
  }
}
function drawGraph() {
  const svg=document.querySelector('#network'); const graph=displayedGraph(); if(!svg || !graph) return;
  graphView.svg=svg; graphView.height=Math.max(620,1000*svg.clientHeight/Math.max(svg.clientWidth,1));
  svg.setAttribute('viewBox',`0 0 1000 ${graphView.height}`); preparePositions(graph);
  const viewport=svgElement('g',{id:'graph-viewport'}), edges=svgElement('g',{id:'graph-edges'}), nodesGroup=svgElement('g',{id:'graph-nodes'});
  const degree=new Map(graph.nodes.map(n=>[String(n.id),0]));
  graph.edges.forEach(e => {degree.set(String(e.source),(degree.get(String(e.source))||0)+1);degree.set(String(e.target),(degree.get(String(e.target))||0)+1);});
  for(const edge of graph.edges) {
    const a=graphView.positions.get(String(edge.source)),b=graphView.positions.get(String(edge.target)); if(!a||!b) continue;
    edges.append(svgElement('line',{class:'graph-edge',x1:a.x,y1:a.y,x2:b.x,y2:b.y,'data-source':String(edge.source),'data-target':String(edge.target)}));
  }
  const topNodes=new Set([...graph.nodes].sort((a,b)=>(degree.get(String(b.id))||0)-(degree.get(String(a.id))||0)).slice(0,12).map(n=>String(n.id)));
  if(graph.nodes.length>120) spreadOverlaps(graphView.positions, degree);
  for(const node of graph.nodes) {
    const id=String(node.id), p=graphView.positions.get(id), d=degree.get(id)||0;
    const big=graph.nodes.length>200, radius=big?Math.min(13,4+Math.sqrt(d)*1.3):Math.min(27,10+Math.sqrt(d)*2.4);
    const group=svgElement('g',{class:'graph-node',transform:`translate(${p.x},${p.y})`,'data-node':id,tabindex:'0',role:'button','aria-label':`${node.label || id}, ${d} связей`});
    group.append(svgElement('title',{},`${node.label || id} · ID ${id} · ${d} связей${state.analysis ? ` · орбита ${node.orbit}` : ''}`));
    group.append(svgElement('circle',{class:'node-ring',r:radius+7,display:'none'}));
    group.append(svgElement('circle',{class:'node-dot',r:radius,fill:orbitColor(node.orbit)}));
    const label=svgElement('text',{class:'node-label',y:radius+12,'font-size':big?'11':'15','data-default-visible':String(graph.nodes.length<=20 || topNodes.has(id) || state.analysis?.orbits.some(o=>o.id===node.orbit&&o.size>1))},node.label || id);
    group.append(label); nodesGroup.append(group);
  }
  viewport.append(edges,nodesGroup); svg.append(viewport); applyGraphTransform(); applyGraphHighlight();
  svg.addEventListener('pointerdown', graphPointerDown);
  svg.addEventListener('pointermove', graphPointerMove);
  svg.addEventListener('pointerup', graphPointerUp);
  svg.addEventListener('pointercancel', () => { graphView.drag=null;svg.classList.remove('dragging'); });
  svg.addEventListener('wheel', event => { event.preventDefault(); const point=screenToSVG(event.clientX,event.clientY); zoomGraph(Math.exp(-event.deltaY*.0017),point); },{passive:false});
  svg.addEventListener('keydown', event => {
    const node=event.target.closest('[data-node]');
    if(node && (event.key==='Enter'||event.key===' ')) { event.preventDefault(); selectNode(node.dataset.node); }
  });
}
function screenToSVG(x,y) {
  const svg=graphView.svg, point=svg.createSVGPoint(); point.x=x;point.y=y;
  const matrix=svg.getScreenCTM(); return matrix ? point.matrixTransform(matrix.inverse()) : point;
}
function graphPointerDown(event) {
  if(event.button !== 0) return;
  const group=event.target.closest('[data-node]'),p=screenToSVG(event.clientX,event.clientY);
  graphView.drag={id:group?.dataset.node || null,start:p,previous:p,moved:false,pointerId:event.pointerId};
  graphView.svg.setPointerCapture(event.pointerId); graphView.svg.classList.add('dragging');
}
function graphPointerMove(event) {
  const drag=graphView.drag; if(!drag || drag.pointerId !== event.pointerId) return;
  const p=screenToSVG(event.clientX,event.clientY),dx=p.x-drag.previous.x,dy=p.y-drag.previous.y;
  if(Math.hypot(p.x-drag.start.x,p.y-drag.start.y)>5) drag.moved=true;
  if(drag.id) {
    const pos=graphView.positions.get(drag.id); pos.x+=dx/graphView.zoom;pos.y+=dy/graphView.zoom;
    updateNodePosition(drag.id,pos);
  } else {graphView.tx+=dx;graphView.ty+=dy;applyGraphTransform();}
  drag.previous=p;
}
function graphPointerUp(event) {
  const drag=graphView.drag;if(!drag || drag.pointerId!==event.pointerId) return;
  graphView.drag=null;graphView.svg.classList.remove('dragging');
  if(graphView.svg.hasPointerCapture(event.pointerId)) graphView.svg.releasePointerCapture(event.pointerId);
  if(!drag.moved) { if(drag.id) selectNode(drag.id); else {state.selectedPair=null;state.selectedNode=null;state.selectedOrbit=null;refreshSelection();} }
}
function updateNodePosition(id,p) {
  graphView.svg.querySelectorAll('.graph-node').forEach(g => { if(g.dataset.node===id) g.setAttribute('transform',`translate(${p.x},${p.y})`); });
  graphView.svg.querySelectorAll('.graph-edge').forEach(edge => {
    if(edge.dataset.source===id) {edge.setAttribute('x1',p.x);edge.setAttribute('y1',p.y);}
    if(edge.dataset.target===id) {edge.setAttribute('x2',p.x);edge.setAttribute('y2',p.y);}
  });
}
function applyGraphTransform() {
  const viewport=document.querySelector('#graph-viewport');
  if(viewport) viewport.setAttribute('transform',`translate(${graphView.tx} ${graphView.ty}) scale(${graphView.zoom})`);
  const label=document.querySelector('#zoom-level');if(label) label.textContent=`${Math.round(graphView.zoom*100)}%`;
}
function zoomGraph(factor,anchor={x:500,y:graphView.height/2}) {
  const next=bounded(graphView.zoom*factor,.25,5),ratio=next/graphView.zoom;
  graphView.tx=anchor.x-(anchor.x-graphView.tx)*ratio;graphView.ty=anchor.y-(anchor.y-graphView.ty)*ratio;
  graphView.zoom=next;applyGraphTransform();
}
function fitGraph() {
  const ps=[...graphView.positions.values()];if(!ps.length)return;
  const minX=Math.min(...ps.map(p=>p.x)),maxX=Math.max(...ps.map(p=>p.x)),minY=Math.min(...ps.map(p=>p.y)),maxY=Math.max(...ps.map(p=>p.y));
  graphView.zoom=bounded(Math.min(800/Math.max(maxX-minX,1),(graphView.height-210)/Math.max(maxY-minY,1)),.25,1.4);
  graphView.tx=500-(minX+maxX)/2*graphView.zoom;graphView.ty=graphView.height/2-15-(minY+maxY)/2*graphView.zoom;applyGraphTransform();
}
function applyGraphHighlight() {
  const svg=document.querySelector('#network'),graph=displayedGraph();if(!svg||!graph)return;
  const map=nodeMap(),pair=state.selectedPair,query=state.nodeQuery.trim().toLowerCase();
  const selected=new Set(), common=new Set((pair?.common_neighbors || []).map(String)),around=new Set();
  if(pair){selected.add(String(pair.source));selected.add(String(pair.target));}
  if(state.selectedNode)selected.add(String(state.selectedNode));
  graph.edges.forEach(e => {if(selected.has(String(e.source)))around.add(String(e.target));if(selected.has(String(e.target)))around.add(String(e.source));});
  if(state.selectedOrbit!=null) graph.nodes.forEach(n=>{if(n.orbit===state.selectedOrbit)selected.add(String(n.id));});
  const searching=Boolean(query),selection=selected.size>0;
  let matches=0;
  svg.querySelectorAll('.graph-node').forEach(group => {
    const id=group.dataset.node,node=map.get(id),hit=searching && [id,node?.label || ''].some(v=>String(v).toLowerCase().includes(query));
    if(hit)matches++;
    let color=state.analysis ? orbitColor(node?.orbit) : '#90aa97';
    if(id===state.options.root)color='#355749';
    if(pair){if(id===String(pair.source))color='#ec9d5d';else if(id===String(pair.target))color='#4b8e7c';else if(common.has(id))color='#e4bb75';}
    const active=selected.has(id)||hit;
    const faded=searching ? !hit && !selected.has(id) : selection && !selected.has(id) && !around.has(id);
    group.setAttribute('opacity',faded?'.22':'1');
    group.querySelector('.node-dot').setAttribute('fill',color);
    group.querySelector('.node-ring').setAttribute('display',active?'inline':'none');
    const label=group.querySelector('.node-label');
    label.setAttribute('display',(active || common.has(id) || (label.dataset.defaultVisible==='true' && !faded))?'inline':'none');
    group.setAttribute('aria-pressed',String(selected.has(id)));
  });
  svg.querySelectorAll('.graph-edge').forEach(edge => {
    const a=edge.dataset.source,b=edge.dataset.target,active=selected.has(a)||selected.has(b);
    edge.style.strokeOpacity=selection ? active?'.8':'.10' : '.52';
    edge.style.stroke=pair&&((selected.has(a)&&common.has(b))||(selected.has(b)&&common.has(a)))?'#d8ac65':active?'#829e86':'#bacabb';
  });
  const input=document.querySelector('#node-search');if(input){input.setAttribute('aria-label',searching?`Поиск вершины. Найдено: ${matches}`:'Поиск вершины по имени или ID');input.title=searching?`Совпадений: ${matches}`:'';}
}
function refreshSelection() {
  const inspector=document.querySelector('#inspector');if(inspector)inspector.outerHTML=inspectorHTML();
  const region=document.querySelector('#candidate-table-region');if(region)region.innerHTML=candidateTableHTML(state.view==='graph');
  applyGraphHighlight(); updateBusy();
}
function selectNode(id) {state.selectedNode=String(id);state.selectedPair=null;state.selectedOrbit=null;refreshSelection();}
function selectPair(index) {const pair=state.analysis?.pairs[index];if(!pair)return;state.selectedPair=pair;state.selectedNode=null;state.selectedOrbit=null;refreshSelection();}

function openModal(title,body,{drawer=false,onOpen}={}) {
  state.modalReturn=document.activeElement;
  const root=document.querySelector('#modal-root');
  root.innerHTML=`<div class="modal-backdrop ${drawer?'drawer-backdrop':''}"><section class="modal ${drawer?'drawer':''}" role="dialog" aria-modal="true" aria-labelledby="modal-title"><div class="modal-header"><h2 id="modal-title">${esc(title)}</h2><button class="icon-button" data-action="close-modal" aria-label="Закрыть">${icon('close')}</button></div><div class="modal-body">${body}</div></section></div>`;
  document.body.style.overflow='hidden';
  root.querySelector('.modal-backdrop').addEventListener('click',e=>{if(e.target===e.currentTarget)closeModal();});
  root.querySelector('input,button,a,select')?.focus();
  if(onOpen)onOpen(root);
}
function closeModal() {document.querySelector('#modal-root').innerHTML='';document.body.style.overflow='';state.modalReturn?.focus?.();}
function methodology() {
  openModal('Как устроено исследование',`<div class="eyebrow">Методика / Орбита</div><div class="method-section"><h3>1. Что анализируется</h3><p>Аккаунты представлены вершинами простого неориентированного графа, связи — рёбрами. Можно исследовать весь загруженный граф или окружение выбранной вершины на расстоянии 1–3 шагов. Направления и типы связей в этой модели не различаются.</p></div><div class="method-section"><h3>2. Автоморфизмы и орбиты</h3><p>Автоморфизм — перестановка вершин, сохраняющая все рёбра. Две вершины находятся в одной орбите, если существует такая перестановка, переводящая одну в другую. Нетривиальные орбиты выделены цветом, одноэлементные — серым, центр — тёмным. Номер орбиты точно определяет группу, а размер вершины показывает число связей.</p><p>Центр локального окружения фиксируется при поиске симметрий. Орбиты относятся к выбранному подграфу, а не ко всей социальной сети.</p></div><div class="method-section"><h3>3. Откуда берётся оценка пары</h3><p>J — индекс Жаккара: доля общих соседей среди всех соседей пары. O — орбитальный признак: обе вершины лежат в одной точной орбите. По умолчанию центр исключается из сравниваемых окружений, чтобы одна общая связь с ним не создавала ложное сходство.</p><div class="formula-grid"><div class="formula-card"><div class="formula-left"><span class="formula-var">O</span><span class="formula-name">орбита</span></div><div class="formula-body">O = 1, если a и b в одной точной орбите и оба окружения непусты; иначе O = 0</div></div><div class="formula-card"><div class="formula-left"><span class="formula-var">J</span><span class="formula-name">Жаккар</span></div><div class="formula-body">J = <span class="formula-frac"><span class="num">|N(a) ∩ N(b)|</span><span class="den">|N(a) ∪ N(b)|</span></span></div><div class="formula-note">N(a) — соседи аккаунта a. При пустом объединении J = 0. Пустые окружения не считаются свидетельством сходства.</div></div><div class="formula-card"><div class="formula-left"><span class="formula-var">S</span><span class="formula-name">оценка</span></div><div class="formula-body">S = (O + J) / 2</div><div class="formula-note">Пара попадает в кандидаты при S ≥ порога и наличии структурного свидетельства. Центр не участвует в сравнении пар.</div></div></div><p><strong>Порог выше 0,5 требует общей орбиты.</strong> Частично скопированные окружения могут потерять точную симметрию. В таких случаях простой метод общих соседей может оказаться полезнее — это проверяется в экспериментах.</p></div><div class="method-section"><h3>4. Что показывают эксперименты</h3><p>К исходному графу добавляются модельные клоны с заданной долей скопированных связей. Затем удаляется заданная доля рёбер и добавляется столько же случайных связей, если доступны отсутствующие рёбра. Связи с фиксированным центром не меняются. На каждом полученном графе сравниваются индекс Жаккара, орбитальный признак и их комбинация.</p><ul><li>Precision — доля верно найденных пар среди отмеченных.</li><li>Recall — доля найденных модельных пар среди добавленных.</li><li>F1 — гармоническое среднее точности и полноты.</li><li>Контрольные графы без добавленных клонов показывают ложные срабатывания.</li></ul><p>«—» означает отсутствие определённого значения метрики. Порог фиксируется до запуска.</p></div><div class="method-section"><h3>5. Интерпретация и данные</h3><p>Результат Орбиты — пары с максимальным структурным сходством окружений.</p><p>Разметка не влияет на поиск и цвета. Файлы и проекты обрабатываются локально. Запросы к VK выполняются только после явного запуска; токены не сохраняются. Проект записывается на диск только по кнопке «Сохранить».</p></div>`,{drawer:true});
}
async function refreshProjects() {const data=await api('/api/projects');state.projects=data.projects||[];}
function showSaveProject() {
  if(!state.graph)return;
  openModal('Сохранить исследование',`<p>Граф, параметры и текущие результаты будут сохранены в папке проектов на этом компьютере.</p><form id="save-form"><div class="form-field"><label for="project-name">Название проекта</label><input class="input" id="project-name" required maxlength="120" value="${esc(state.projectName || state.graph.name || 'Новое исследование')}" autocomplete="off"></div><div class="modal-actions"><button class="button button-outline" type="button" data-action="close-modal">Отмена</button><button class="button button-orange" type="submit" ${lock()}>${icon('save')}Сохранить проект</button></div></form>`);
}
function showDeleteProject(id) {
  const project=state.projects.find(p=>p.id===id);if(!project)return;
  openModal('Удалить сохранённый проект?',`<p>Проект «${esc(project.name)}» будет удалён с этого компьютера. Открытый в рабочей области граф останется доступен.</p><div class="modal-actions"><button class="button button-outline" data-action="close-modal">Отмена</button><button class="button button-danger" data-action="confirm-delete-project" data-project="${esc(id)}" ${lock()}>Удалить проект</button></div>`);
}
async function exportFile(kind) {
  const payload = kind==='subgraph'?{graph:state.analysis?.graph}:kind==='json'?{graph:state.graph}:kind==='experiments'?{experiments:state.experiments}:kind==='html'?{analysis:state.analysis,experiments:state.experiments}:{analysis:state.analysis};
  if(kind==='subgraph'&&!state.analysis || kind==='json'&&!state.graph || kind==='experiments'&&!state.experiments || ['csv','html'].includes(kind)&&!state.analysis)return;
  await task('Подготавливаем файл…',async()=>{
    const {blob,disposition}=await api(`/api/export/${kind==='subgraph'?'json':kind}`,{body:payload,download:true});
    const fallback={subgraph:'orbita-subgraph.json',json:'orbita-graph.json',csv:'orbita-candidates.csv',html:'orbita-report.html',experiments:'orbita-experiments.csv'}[kind];
    const match=disposition?.match(/filename\*?=(?:UTF-8'')?["']?([^"';]+)["']?/i);
    let filename=fallback;try{if(match&&kind!=='subgraph')filename=decodeURIComponent(match[1]);}catch(_){}
    const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=filename;a.hidden=true;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),30000);toast('Файл подготовлен к скачиванию.');
  });
}
async function importFile(file,isLabels=false) {
  if(!file)return;
  if(state.busy){toast('Дождитесь завершения текущей операции.','error');return;}
  if(file.size > 20*1024*1024){toast('Файл слишком большой. Максимальный размер — 20 МБ.','error');return;}
  if(!/\.(csv|json|tsv|txt)$/i.test(file.name)){toast('Поддерживаются файлы CSV, TSV, TXT и JSON.','error');return;}
  await task(isLabels?'Загружаем разметку…':'Импортируем граф…',async()=>{
    const content=await file.text();
    const result=await api(isLabels?'/api/labels':'/api/import',{body:isLabels?{graph:state.graph,content,filename:file.name}:{content,filename:file.name,name:file.name.replace(/\.[^.]+$/,'')}});
    if(isLabels){state.graph=result;invalidateAnalysis();render();toast('Разметка загружена. Повторите анализ для оценки результата.');}
    else{acceptGraph(result);state.view='graph';render();await analyzeCurrent();toast('Граф загружен и проанализирован.');}
  });
}
function bindDropzone() {
  const zone=document.querySelector('#graph-dropzone');if(!zone)return;
  ['dragenter','dragover'].forEach(type=>zone.addEventListener(type,e=>{e.preventDefault();zone.classList.add('drag-over');}));
  ['dragleave','drop'].forEach(type=>zone.addEventListener(type,e=>{e.preventDefault();zone.classList.remove('drag-over');}));
  zone.addEventListener('drop',e=>{const files=e.dataTransfer?.files;if(files?.length>1)toast('Выберите один файл графа.','error');else importFile(files?.[0]);});
}

document.addEventListener('click',async event => {
  const button=event.target.closest('button,a[data-action]');
  if(button?.disabled)return;
  const view=button?.dataset.view;if(view){setView(view);return;}
  const action=button?.dataset.action;
  if(action){
    if(action==='close-modal'){closeModal();return;}
    if(action==='methodology'){methodology();return;}
    if(action==='save-project'){showSaveProject();return;}
    if(action==='open-projects'){setView('data');document.querySelector('#projects-section')?.scrollIntoView({behavior:'smooth',block:'start'});return;}
    if(action==='load-demo'){await loadDemo(button.dataset.demo);return;}
    if(action==='analyze'||action==='analyze-open'){
      if(action==='analyze-open')setView('graph');
      await task('Вычисляем автоморфизмы и сравниваем окружения…',async()=>{await analyzeCurrent();toast('Анализ завершён.');});return;
    }
    if(action==='zoom-in'){zoomGraph(1.25);return;}
    if(action==='zoom-out'){zoomGraph(.8);return;}
    if(action==='fit-graph'){fitGraph();return;}
    if(action==='clear-selection'){state.selectedPair=null;state.selectedNode=null;state.selectedOrbit=null;refreshSelection();return;}
    if(action==='select-node'){selectNode(button.dataset.node);return;}
    if(action==='select-orbit'){const id=Number(button.dataset.orbit);state.selectedOrbit=state.selectedOrbit===id?null:id;state.selectedPair=null;state.selectedNode=null;refreshSelection();return;}
    if(action==='node-as-root'){state.options.root=button.dataset.node;invalidateAnalysis();render();await task('Анализируем окружение выбранной вершины…',analyzeCurrent);return;}
    if(action==='sort-pairs'){const key=button.dataset.sort;state.pairSortDir=state.pairSort===key?-state.pairSortDir:key==='pair'?1:-1;state.pairSort=key;state.pairPage=0;refreshSelection();return;}
    if(action==='filter-pairs'){state.pairMode=button.dataset.filter;state.pairPage=0;render();return;}
    if(action==='reset-filters'){state.pairMode='all';state.pairQuery='';state.pairPage=0;render();return;}
    if(action==='prev-page'||action==='next-page'){state.pairPage+=action==='next-page'?1:-1;refreshSelection();return;}
    if(action.startsWith('export-')){await exportFile(action.slice(7));return;}
    if(action==='refresh-projects'){await task('Обновляем список проектов…',async()=>{await refreshProjects();render();});return;}
    if(action==='load-project'){
      await task('Открываем проект…',async()=>{
        const p=await api(`/api/projects/${encodeURIComponent(button.dataset.project)}`);
        acceptGraph(p.graph,{projectId:button.dataset.project,projectName:p.name});
        for(const key of ['root','radius','threshold','exclude_root','max_pairs'])if(p.options?.[key]!==undefined)state.options[key]=p.options[key];
        state.analysis=p.analysis||null;state.experiments=p.experiments||null;
        if(p.experiments?.config)for(const key of Object.keys(state.experimentConfig))if(p.experiments.config[key]!==undefined)state.experimentConfig[key]=p.experiments.config[key];
        state.view='graph';render();toast(`Проект «${p.name}» открыт.`);
      });return;
    }
    if(action==='delete-project'){showDeleteProject(button.dataset.project);return;}
    if(action==='confirm-delete-project'){
      const id=button.dataset.project;
      await task('Удаляем сохранённый проект…',async()=>{await api(`/api/projects/${encodeURIComponent(id)}`,{method:'DELETE'});if(state.projectId===id){state.projectId=null;state.projectName='';}await refreshProjects();closeModal();render();toast('Сохранённый проект удалён.');});return;
    }
    if(action==='run-experiments'){
      if(!state.graph)return;
      if(!readExperimentControls())return;
      const config={...state.experimentConfig,root:state.options.root,exclude_root:state.options.exclude_root};
      await task('Проводим эксперимент: генерация, шум, три метода…',async()=>{
        state.experiments=null;render();
        state.experiments=await api('/api/experiments',{body:{graph:displayedGraph(),config},timeout:140000});
        state.experimentConfig={...config};state.experimentTab='summary';render();toast('Эксперимент завершён. Результаты готовы.');
      });return;
    }
    if(action==='exp-tab'){state.experimentTab=button.dataset.tab;render();return;}
    if(action==='open-experiment-graph'){
      const graph=state.experiments?.example_graph;if(!graph)return;
      acceptGraph(graph,{demoId:'experiment'});state.view='graph';render();
      await task('Анализируем модельный пример…',analyzeCurrent);return;
    }
  }
  const row=event.target.closest('tr[data-pair]');if(row)selectPair(Number(row.dataset.pair));
});
document.addEventListener('keydown',event=>{
  const row=event.target.closest('tr[data-pair]');if(row&&(event.key==='Enter'||event.key===' ')){event.preventDefault();selectPair(Number(row.dataset.pair));}
  const modal=document.querySelector('.modal');if(!modal)return;
  if(event.key==='Escape'){event.preventDefault();closeModal();}
  if(event.key==='Tab'){
    const focusable=[...modal.querySelectorAll('button:not(:disabled),input:not(:disabled),select:not(:disabled),a[href],summary,[tabindex="0"]')];
    const first=focusable[0],last=focusable.at(-1);
    if(event.shiftKey&&document.activeElement===first){event.preventDefault();last?.focus();}
    else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first?.focus();}
  }
});
document.addEventListener('input',event=>{
  const el=event.target;
  if(el.id==='node-search'){state.nodeQuery=el.value;applyGraphHighlight();}
  if(el.id==='pair-search'){state.pairQuery=el.value;state.pairPage=0;const region=document.querySelector('#candidate-table-region');if(region)region.innerHTML=candidateTableHTML();}
  if(el.id==='threshold-range')document.querySelector('#threshold-display').textContent=decimal(el.value);
  if(el.id==='exp-retention')document.querySelector('#exp-retention-display').textContent=pct(el.value);
  if(el.id==='vk-user')state.vkUser=el.value;
  if(el.id==='vk-limit')state.vkLimit=Number(el.value);
});
document.addEventListener('change',async event=>{
  const el=event.target;
  if(el.id==='graph-file'){await importFile(el.files?.[0]);el.value='';return;}
  if(el.id==='labels-file'){await importFile(el.files?.[0],true);el.value='';return;}
  const analysisFields={'root-select':'root','radius-select':'radius','threshold-range':'threshold','exclude-root':'exclude_root'};
  if(analysisFields[el.id]){
    const key=analysisFields[el.id];state.options[key]=key==='root'?el.value||null:key==='exclude_root'?el.checked:Number(el.value);
    invalidateAnalysis();render();return;
  }
  if(['exp-clones','exp-repeats','exp-seed','exp-retention','exp-noise','exp-threshold'].includes(el.id)){
    if(readExperimentControls(false)){state.experiments=null;render();}
  }
});
document.addEventListener('submit',async event=>{
  if(event.target.id==='vk-form'){
    event.preventDefault();if(state.busy)return;
    const userId=document.querySelector('#vk-user').value.trim();const maxFriends=Number(document.querySelector('#vk-limit').value);
    if(!userId){toast('Укажите числовой ID пользователя VK.','error');return;}
    if(!/^[1-9][0-9]*$/.test(userId)){toast('VK: укажите положительный числовой ID пользователя.','error');return;}
    if(!Number.isInteger(maxFriends)||maxFriends<1||maxFriends>80){toast('Лимит друзей должен быть целым числом от 1 до 80.','error');return;}
    await task('Получаем доступные связи VK. Это может занять до 2 минут…',async()=>{
      const graph=await api('/api/vk',{body:{user_id:userId,max_friends:maxFriends},timeout:170000});
      acceptGraph(graph);state.view='graph';render();await analyzeCurrent();toast('Граф VK загружен.');
    });return;
  }
  if(event.target.id==='save-form'){
    event.preventDefault();const name=document.querySelector('#project-name').value.trim();if(!name){toast('Введите название проекта.','error');return;}
    await task('Сохраняем проект локально…',async()=>{
      const result=await api('/api/projects',{body:{name,graph:state.graph,options:{...state.options},analysis:state.analysis,experiments:state.experiments}});
      state.projectId=result.id;state.projectName=result.name||name;await refreshProjects();closeModal();render();toast('Проект сохранён на этом компьютере.');
    });
  }
});
function readExperimentControls(showErrors=true) {
  const fields=['exp-clones','exp-repeats','exp-seed','exp-retention','exp-noise','exp-threshold'];
  if(!fields.every(id=>document.getElementById(id)))return true;
  const values=Object.fromEntries(fields.map(id=>[id,document.getElementById(id).value]));
  const clone_count=Number(values['exp-clones']),repeats=Number(values['exp-repeats']),seed=Number(values['exp-seed']),retention=Number(values['exp-retention']),threshold=Number(values['exp-threshold']);
  const noise=values['exp-noise'].trim();
  const noise_levels=noise.split(/[;\s]+/).filter(Boolean).map(v=>Number(v.replace(',','.')));
  let error='';
  if(!Number.isInteger(clone_count)||clone_count<1||clone_count>10)error='Число клонов должно быть от 1 до 10.';
  else if(!Number.isInteger(repeats)||repeats<1||repeats>5)error='Число повторов должно быть от 1 до 5.';
  else if(!Number.isInteger(seed)||seed<0||seed>4294967295)error='Seed должен быть целым числом от 0 до 4294967295.';
  else if(!Number.isFinite(retention)||retention<0||retention>1)error='Доля сохранения связей должна быть от 0 до 1.';
  else if(!Number.isFinite(threshold)||threshold<0||threshold>1)error='Порог должен быть от 0 до 1.';
  else if(!noise_levels.length||noise_levels.length>6||noise_levels.some(n=>!Number.isFinite(n)||n<0||n>1))error='Укажите от 1 до 6 уровней шума от 0 до 1, разделённых точкой с запятой.';
  if(error){if(showErrors)toast(error,'error');return false;}
  state.experimentConfig={...state.experimentConfig,clone_count,repeats,seed,retention,threshold,noise_levels:[...new Set(noise_levels)]};return true;
}
window.addEventListener('hashchange',()=>{const view=location.hash.slice(1);if(viewNames[view])setView(view,false);});
let graphResizeTimer;
window.addEventListener('resize',()=>{
  clearTimeout(graphResizeTimer);
  graphResizeTimer=setTimeout(()=>{
    const svg=document.querySelector('#network');
    if(state.view==='graph'&&svg&&displayedGraph()){
      graphView.drag=null;
      svg.replaceWith(svg.cloneNode(false));
      drawGraph();
    }
  },160);
});
async function bootstrap() {
  hydrateIcons();
  const hash=location.hash.slice(1);if(viewNames[hash])state.view=hash;
  state.busy='Загружаем рабочее пространство…';updateBusy();
  const responses=await Promise.allSettled([api('/api/health',{timeout:15000}),api('/api/demos',{timeout:15000}),api('/api/projects',{timeout:15000})]);
  const [health,demos,projects]=responses;
  if(health.status==='fulfilled')document.querySelector('#app-version').textContent=health.value.version||'1.0';
  else{const connection=document.querySelector('#connection');connection.classList.add('offline');connection.innerHTML='<i></i>Сервер недоступен';}
  if(demos.status==='fulfilled')state.demos=demos.value.demos||[];else toast(demos.reason.message,'error');
  if(projects.status==='fulfilled')state.projects=projects.value.projects||[];else toast(projects.reason.message,'error');
  try {
    const demo=state.demos.find(d=>d.id==='social')||state.demos[0];
    if(demo){const graph=await api(`/api/demos/${encodeURIComponent(demo.id)}`);acceptGraph(graph,{demoId:demo.id});render();state.busy='Вычисляем симметрии модельного графа…';updateBusy();await analyzeCurrent();}
    else render();
  }catch(error){toast(error.message,'error');render();}
  finally{state.busy=null;updateBusy();}
}
bootstrap();
