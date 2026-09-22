/* Proposed TPS School Closures — map application.
   MapLibre GL JS (vendored) over CARTO's Positron / Dark Matter vector basemap.
   Data lives in ../data/*.geojson; this file only draws it. */
import * as maplibregl from '../vendor/maplibre-gl/maplibre-gl.mjs';   // v6 uses named exports

const STYLES = {
  light: 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json',
  dark:  'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json',
};
const BREAKS = [35000, 45000, 55000, 65000, 80000, 95000];
const FONT = ['Montserrat Medium', 'Open Sans Bold'];     // glyphs served with the CARTO styles
const HOME_PAD = { top: 36, right: 36, bottom: 36, left: 36 };

const $ = (id) => document.getElementById(id);
const money = (v) => '$' + Number(v).toLocaleString('en-US');
const token = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

// ---------------------------------------------------------------- theme
function isDark() {
  const t = document.documentElement.getAttribute('data-theme');
  if (t === 'dark') return true;
  if (t === 'light') return false;
  return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
}
function styleFor() {
  const q = new URLSearchParams(location.search);
  if (q.get('style') === 'blank') {           // offline test harness: no basemap, everything else live
    return {
      version: 8,
      glyphs: 'https://tiles.basemaps.cartocdn.com/fonts/{fontstack}/{range}.pbf',
      sources: {},
      layers: [{ id: 'bg', type: 'background', paint: { 'background-color': token('--paper-2') || '#eee' } }],
    };
  }
  return isDark() ? STYLES.dark : STYLES.light;
}

// ---------------------------------------------------------------- data
const [schools, tracts, zips] = await Promise.all(
  ['data/schools.geojson', 'data/tracts.geojson', 'data/zips.geojson'].map((u) => fetch(u).then((r) => r.json()))
);
const S = schools.features.map((f) => ({ ...f.properties, lon: f.geometry.coordinates[0], lat: f.geometry.coordinates[1] }));
const closures = S.filter((s) => s.status === 'closure').sort((a, b) => a.number - b.number);
const changes = S.filter((s) => s.status === 'change');
const opens = S.filter((s) => s.status === 'open');
const tractBy = Object.fromEntries(tracts.features.map((f) => [f.properties.geoid, f.properties]));
const zipBy = Object.fromEntries(zips.features.map((f) => [f.properties.zip, f.properties]));
// a marker that covers another school at the identical address names it on its card
for (const s of [...closures, ...changes]) s.colocated = opens.filter((o) => o.address === s.address).map((o) => o.name);

const bounds = S.reduce(
  (b, s) => [[Math.min(b[0][0], s.lon), Math.min(b[0][1], s.lat)], [Math.max(b[1][0], s.lon), Math.max(b[1][1], s.lat)]],
  [[180, 90], [-180, -90]]
);

// ---------------------------------------------------------------- map
const map = new maplibregl.Map({
  container: 'map',
  style: styleFor(),
  bounds,
  fitBoundsOptions: { padding: HOME_PAD },
  minZoom: 8,
  maxZoom: 17,
  attributionControl: { compact: true },
});
map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right');
map.addControl(new maplibregl.ScaleControl({ unit: 'imperial', maxWidth: 120 }), 'bottom-left');
window.__map = map;     // exposed for the test harness only
window.__data = { schools, tracts, zips };

const state = { unit: 'tract', income: true, chg: true, open: true, ziplab: true, sel: null };
const tip = new maplibregl.Popup({ closeButton: false, closeOnClick: false, className: 'tip', offset: 12, maxWidth: 'none' });
let card = null;
const phone = () => window.innerWidth < 600;
function newCard() {
  // phones: pin the card above the site and pan the site to the lower part of the map
  return new maplibregl.Popup({ closeButton: false, closeOnClick: false, className: 'pop', offset: 20, maxWidth: 'none',
    anchor: phone() ? 'bottom' : undefined });
}

function ramp() {
  const c = [0, 1, 2, 3, 4, 5, 6].map((i) => token('--c' + i));
  const expr = ['step', ['coalesce', ['get', 'median_hh_income'], -1], token('--nodata'), 0, c[0]];
  BREAKS.forEach((b, i) => expr.push(b, c[i + 1]));
  return expr;
}

function firstSymbolLayer() {
  const l = map.getStyle().layers.find((x) => x.type === 'symbol');
  return l ? l.id : undefined;
}

function addLayers() {
  if (map.getSource('tracts')) return;         // already built for this style
  const halo = token('--halo'), ink = token('--ink');
  const before = firstSymbolLayer();           // street names paint above the shading

  map.addSource('tracts', { type: 'geojson', data: tracts, promoteId: 'geoid' });
  map.addSource('zips', { type: 'geojson', data: zips, promoteId: 'zip' });
  map.addSource('schools', { type: 'geojson', data: schools, promoteId: 'id' });

  for (const [id, src] of [['tract', 'tracts'], ['zip', 'zips']]) {
    const vis = state.unit === id ? 'visible' : 'none';
    map.addLayer({ id: id + '-fill', type: 'fill', source: src, layout: { visibility: vis },
      paint: { 'fill-color': ramp(), 'fill-opacity': state.income ? 0.74 : 0 } }, before);
    map.addLayer({ id: id + '-line', type: 'line', source: src, layout: { visibility: vis },
      filter: ['==', ['get', 'reliability'], 'ok'],
      paint: { 'line-color': halo, 'line-width': id === 'tract' ? 0.7 : 1 } }, before);
    map.addLayer({ id: id + '-line-flagged', type: 'line', source: src, layout: { visibility: vis },
      filter: ['!=', ['get', 'reliability'], 'ok'],
      paint: { 'line-color': halo, 'line-width': 1.3, 'line-dasharray': [3, 2.5] } }, before);
    map.addLayer({ id: id + '-sel', type: 'line', source: src, layout: { visibility: vis },
      filter: ['==', ['get', id === 'tract' ? 'geoid' : 'zip'], '__none__'],
      paint: { 'line-color': ink, 'line-width': 2.2 } }, before);
  }

  map.addLayer({ id: 'zip-label', type: 'symbol', source: 'zips',
    layout: { 'text-field': ['get', 'zip'], 'text-font': FONT, 'text-size': 11, 'symbol-placement': 'point',
      'text-allow-overlap': false, 'text-padding': 6, visibility: state.ziplab ? 'visible' : 'none' },
    paint: { 'text-color': ink, 'text-opacity': 0.62, 'text-halo-color': halo, 'text-halo-width': 1.4 } });

  map.addLayer({ id: 'open-dot', type: 'circle', source: 'schools', filter: ['==', ['get', 'status'], 'open'],
    layout: { visibility: state.open ? 'visible' : 'none' },
    paint: { 'circle-radius': ['interpolate', ['linear'], ['zoom'], 9, 5, 12, 7, 15, 9], 'circle-color': token('--site') } });
  map.addLayer({ id: 'chg-dot', type: 'circle', source: 'schools', filter: ['==', ['get', 'status'], 'change'],
    layout: { visibility: state.chg ? 'visible' : 'none' },
    paint: { 'circle-radius': ['interpolate', ['linear'], ['zoom'], 9, 6.5, 12, 8.6, 15, 11], 'circle-color': '#ffffff',
      'circle-stroke-color': ['case', ['boolean', ['feature-state', 'sel'], false], ink, token('--site')],
      'circle-stroke-width': ['case', ['boolean', ['feature-state', 'sel'], false], 4, 3.5] } });

  applySelection();
}
map.on('style.load', addLayers);

// numbered closure pins are DOM markers: no glyph dependency, exact styling, keyboard-reachable
for (const s of closures) {
  const el = document.createElement('button');
  el.className = 'pin'; el.type = 'button'; el.textContent = s.number;
  el.setAttribute('aria-label', `${s.name}, ${s.address}, proposed for closure`);
  el.addEventListener('click', (e) => { e.stopPropagation(); openCard(s); });
  el.addEventListener('mouseenter', () => { if (state.sel !== s) showTip([s.lon, s.lat], schoolTip(s)); });
  el.addEventListener('mouseleave', () => tip.remove());
  s.marker = new maplibregl.Marker({ element: el, anchor: 'center' }).setLngLat([s.lon, s.lat]).addTo(map);
  s.el = el;
}

// ---------------------------------------------------------------- tooltips
function showTip(lngLat, html) { tip.setLngLat(lngLat).setHTML(html).addTo(map); }
function schoolTip(s) {
  return `<div class="t-name">${s.name}<div class="t-n">${s.address}${s.building ? '<br><i>' + s.building + '</i>' : ''}</div></div>`;
}
function areaTip(p, unit) {
  const head = unit === 'tract' ? `Tract ${p.tract} &middot; ${p.county} County` : `ZIP ${p.zip}`;
  if (p.median_hh_income == null)
    return `<div class="t-z">${head}</div><div class="t-v">No median</div><div class="t-n">ACS publishes none; population ${p.population.toLocaleString('en-US')}.</div>`;
  return `<div class="t-z">${head}</div><div class="t-v">${money(p.median_hh_income)}</div><div class="t-n">&plusmn;${money(p.moe)} &middot; pop. ${p.population.toLocaleString('en-US')}` +
    (p.poverty_pct != null ? `<br>${p.poverty_pct.toFixed(1)}% below poverty` : '') +
    (p.reliability === 'small' ? '<br>Small population &mdash; read with care.' : p.reliability === 'wide' ? '<br>Wide margin of error.' : '') + '</div>';
}

map.on('mousemove', (e) => {
  const dots = map.queryRenderedFeatures(e.point, { layers: ['chg-dot', 'open-dot'].filter((l) => map.getLayer(l)) });
  if (dots.length) {
    const s = S.find((x) => x.id === dots[0].properties.id);
    map.getCanvas().style.cursor = s.status === 'change' ? 'pointer' : 'help';
    if (state.sel !== s) showTip([s.lon, s.lat], schoolTip(s)); else tip.remove();
    return;
  }
  map.getCanvas().style.cursor = '';
  const fl = state.unit + '-fill';
  const areas = map.getLayer(fl) ? map.queryRenderedFeatures(e.point, { layers: [fl] }) : [];
  if (areas.length) showTip(e.lngLat, areaTip(areas[0].properties, state.unit));
  else tip.remove();
});
map.on('mouseout', () => tip.remove());

// ---------------------------------------------------------------- cards
function row(label, val) { return val ? `<dt>${label}</dt><dd>${val}</dd>` : ''; }
function cardHTML(s) {
  const z = zipBy[s.zip], t = tractBy[s.tract_geoid];
  const zinc = z && z.median_hh_income != null
    ? `<b>${money(z.median_hh_income)}</b> median household${z.reliability !== 'ok' ? '<br>wide margin of error' : ''}`
    : 'no published median';
  const tinc = t ? `<b>${money(t.median_hh_income)}</b> median household` +
    (t.poverty_pct != null ? `<br>${t.poverty_pct.toFixed(1)}% below poverty` : '') +
    (t.county === 'Osage' ? '<br>Osage County' : '') : '';
  const closing = s.status === 'closure';
  const head = closing ? `<span class="pop-n">${s.number}</span>` : `<span class="pop-n chg-badge">&#9633;</span>`;
  const kicker = closing
    ? `<span class="pop-lv">Proposed for closure &middot; ${s.level === 'Elementary' ? 'Elementary site' : 'Secondary site'}</span>`
    : `<span class="pop-lv alt">Stays open &middot; building change</span>`;
  return `<div class="pop-hd">${head}<div class="pop-t"><h3>${s.name}</h3>${kicker}</div>` +
    `<button class="pop-x" type="button" aria-label="Close">&times;</button></div><dl>` +
    row('Address', `${s.address}<br>Tulsa, OK ${s.zip}`) +
    row('ZIP ' + s.zip, zinc) + (t ? row('Tract ' + t.tract, tinc) : '') +
    row('Feeder', s.feeder) + row('Enrollment', s.enrollment) + row('Occupancy', s.occupancy) +
    row('Staffing', s.staffing) + row('Bond', s.bond) +
    (s.colocated && s.colocated.length ? row('Campus', 'Shared with <b>' + s.colocated.join(', ') + '</b>') : '') +
    row('Building', s.building) + '</dl>';
}

function applySelection() {
  const s = state.sel;
  if (map.getLayer('tract-sel')) map.setFilter('tract-sel', ['==', ['get', 'geoid'], s ? s.tract_geoid : '__none__']);
  if (map.getLayer('zip-sel')) map.setFilter('zip-sel', ['==', ['get', 'zip'], s ? s.zip : '__none__']);
  for (const c of changes) if (map.getSource('schools')) map.setFeatureState({ source: 'schools', id: c.id }, { sel: c === s });
}
function openCard(s) {
  if (state.sel && state.sel !== s) unmark(state.sel);
  state.sel = s;
  if (s.el) s.el.classList.add('on');
  if (s.li) s.li.classList.add('on');
  applySelection();
  tip.remove();
  if (card) card.remove();
  card = newCard();
  card.setLngLat([s.lon, s.lat]).setHTML(cardHTML(s)).addTo(map);
  card.getElement().querySelector('.pop-x').addEventListener('click', clearSel);
  if (phone()) {
    // card is viewport-wide and anchored above the site, so put the site low and centred
    map.easeTo({ center: [s.lon, s.lat], offset: [0, map.getContainer().clientHeight * 0.34], duration: 350 });
  }
}
function unmark(s) { if (s.el) s.el.classList.remove('on'); if (s.li) s.li.classList.remove('on'); }
function clearSel() { if (state.sel) unmark(state.sel); state.sel = null; if (card) card.remove(); applySelection(); }

map.on('click', (e) => {
  const dots = map.queryRenderedFeatures(e.point, { layers: ['chg-dot'].filter((l) => map.getLayer(l)) });
  if (dots.length) { openCard(S.find((x) => x.id === dots[0].properties.id)); return; }
  if (!e.originalEvent.target.closest('.pin')) clearSel();
});
addEventListener('keydown', (e) => { if (e.key === 'Escape') clearSel(); });

// ---------------------------------------------------------------- sidebar
function rollRow(s, badge) {
  const li = document.createElement('li');
  li.className = 'it'; li.tabIndex = 0;
  const z = zipBy[s.zip];
  li.innerHTML = badge +
    `<span class="nm">${s.name}<span class="ad">${s.status === 'change' ? s.building : s.address + ' &middot; ' + s.zip}</span></span>` +
    (s.status === 'closure' ? `<span class="in">${z && z.median_hh_income ? money(z.median_hh_income) : '&mdash;'}</span>` : '');
  const go = () => { map.flyTo({ center: [s.lon, s.lat], zoom: Math.max(map.getZoom(), 13.5), duration: 700 }); openCard(s); };
  li.addEventListener('click', go);
  li.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); go(); } });
  s.li = li;
  return li;
}
const roll = $('roll');
let hd = null;
for (const s of closures) {
  const h = s.level === 'Elementary' ? 'Elementary sites' : 'Secondary sites';
  if (h !== hd) { const li = document.createElement('li'); li.className = 'hd'; li.textContent = h; roll.appendChild(li); hd = h; }
  roll.appendChild(rollRow(s, `<span class="n">${s.number}</span>`));
}
for (const s of changes) $('chgroll').appendChild(rollRow(s, '<span class="n sq">&#9633;</span>'));

// ---------------------------------------------------------------- controls
function setVis(id, on) { if (map.getLayer(id)) map.setLayoutProperty(id, 'visibility', on ? 'visible' : 'none'); }
function setUnit() {
  state.unit = $('u-tract').checked ? 'tract' : 'zip';
  for (const u of ['tract', 'zip']) for (const k of ['-fill', '-line', '-line-flagged', '-sel']) setVis(u + k, state.unit === u);
  tip.remove();
}
$('u-tract').addEventListener('change', setUnit);
$('u-zip').addEventListener('change', setUnit);
$('t-inc').addEventListener('change', (e) => { state.income = e.target.checked;
  for (const u of ['tract', 'zip']) if (map.getLayer(u + '-fill')) map.setPaintProperty(u + '-fill', 'fill-opacity', state.income ? 0.74 : 0); });
$('t-chg').addEventListener('change', (e) => { state.chg = e.target.checked; setVis('chg-dot', state.chg);
  if (!state.chg && state.sel && state.sel.status === 'change') clearSel(); tip.remove(); });
$('t-open').addEventListener('change', (e) => { state.open = e.target.checked; setVis('open-dot', state.open); tip.remove(); });
$('t-zip').addEventListener('change', (e) => { state.ziplab = e.target.checked; setVis('zip-label', state.ziplab); });
$('zrst').addEventListener('click', () => { clearSel(); map.fitBounds(bounds, { padding: HOME_PAD, duration: 600 }); });

// theme changes swap the basemap; layers are rebuilt on style.load
function retheme() { if (map.getSource('tracts')) map.setStyle(styleFor()); }
if (window.matchMedia) window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', retheme);
new MutationObserver(retheme).observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
