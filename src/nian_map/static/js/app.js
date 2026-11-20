// Composition root: data, routing (Monde → Pays → Ville) and UI events.
import { api } from "./api.js";
import { countryAt, countryById, loadWorld } from "./geo.js";
import { createMapView } from "./mapview.js";
import {
  renderCategoryFooter, renderCitiesPanel, renderLabelFooter, renderNetworksPanel, setPanelOpen,
} from "./panel.js";
import { addFeeds, addPlaces, filtered, groupByCity, setFilter, setSearch, store, subscribe } from "./store.js";
import { h, toast } from "./util.js";
import { createWorld } from "./world.js";

const $ = (id) => document.getElementById(id);
const app = $("app");
let route = { view: "world" };
let panelOpen = false;

// ---------- routing (hash, so the browser Back button works) ----------
function parseHash() {
  const [, view, arg] = decodeURIComponent(location.hash).match(/^#\/(monde|pays|ville)(?:\/(.+))?$/) || [];
  if (view === "pays" && arg && countryById(arg)) return { view: "country", country: countryById(arg) };
  if (view === "ville" && arg) return { view: "city", city: arg };
  return { view: "world" };
}
const go = {
  world: () => { location.hash = "#/monde"; },
  country: (f) => { location.hash = `#/pays/${encodeURIComponent(f.key)}`; },
  city: (name) => { location.hash = `#/ville/${encodeURIComponent(name)}`; },
};

function countryOfCity(c) {
  return countryAt(c.lon, c.lat);
}

function cityCenter(name, feeds) {
  const p = store.places.get(name);
  if (p) return p;
  const n = feeds.length || 1;
  return { lon: feeds.reduce((s, f) => s + f.lon, 0) / n, lat: feeds.reduce((s, f) => s + f.lat, 0) / n };
}

// ---------- crumbs ----------
function crumbs(parts) {
  const nav = $("crumbs");
  nav.replaceChildren();
  parts.forEach((p, i) => {
    if (i) nav.append(h("span", { class: "sep" }, "›"));
    if (p.href) nav.append(h("a", { href: p.href }, p.label));
    else nav.append(h("span", {}, p.label));
  });
}

// ---------- views ----------
let world, map;

function renderWorld(feeds) {
  const cities = groupByCity(feeds);
  world.refresh();
  crumbs(store.search
    ? [{ label: "MONDE", href: "#/monde" }, { label: `RECHERCHE « ${store.search.text.toUpperCase()} »` }]
    : [{ label: "MONDE" }]);
  renderCitiesPanel("MONDE", cities, openCityFromCard);
  renderCategoryFooter(store.categories, feeds);
}

function renderCountry(feeds) {
  const f = route.country;
  const cities = groupByCity(feeds).filter((c) => countryOfCity(c) === f);
  const scoped = cities.flatMap((c) => c.feeds);
  map.showCountry(f, cities);
  crumbs([{ label: "MONDE", href: "#/monde" }, { label: f.label.toUpperCase() }]);
  renderCitiesPanel(f.label, cities, (c) => go.city(c.city));
  renderCategoryFooter(store.categories, scoped);
}

function renderCity(feeds) {
  const name = route.city;
  let cityFeeds = feeds.filter((f) => f.city === name);
  const s = store.search;
  const center = cityCenter(name, cityFeeds);
  map.showCity(name, center, cityFeeds);
  const country = countryAt(center.lon, center.lat);
  crumbs([
    { label: "MONDE", href: "#/monde" },
    ...(country ? [{ label: country.label.toUpperCase(), href: `#/pays/${encodeURIComponent(country.key)}` }] : []),
    { label: name.toUpperCase() },
  ]);
  const title = s && s.topic ? `${name} · ${s.topic}` : name;
  renderNetworksPanel(title, s ? "Le même sujet, tous réseaux confondus" : "Toutes les publications, par réseau", cityFeeds);
  renderLabelFooter(s ? `RECHERCHE « ${s.topic || s.text} » · ${name}` : `PUBLICATIONS · ${name}`, cityFeeds.length);
}

let scheduled = false;
function render() {
  if (scheduled) return;
  scheduled = true;
  requestAnimationFrame(() => {
    scheduled = false;
    const feeds = filtered();
    app.className = `v-${route.view}`;
    const isWorld = route.view === "world";
    $("worldStage").hidden = !isWorld;
    $("mapStage").hidden = isWorld;
    if (isWorld) world.start(); else world.stop();
    if (route.view === "world") renderWorld(feeds);
    else if (route.view === "country") renderCountry(feeds);
    else renderCity(feeds);
    const active = !!store.search;
    $("searchbox").classList.toggle("active", active);
    $("clear").hidden = !active;
  });
}

function onRoute() {
  const next = parseHash();
  const viewChanged = next.view !== route.view;
  route = next;
  if (viewChanged) { panelOpen = route.view !== "world"; setPanelOpen(panelOpen); }
  render();
}

function openCityFromCard(c) {
  const f = countryOfCity(c);
  if (f) go.country(f); else go.city(c.city);
}

// ---------- stage scaling: keep the design's proportions on smaller screens ----------
function fitStages() {
  // The globe sizes itself (world.js); the 1000×720 map stage is scaled down to fit.
  const ms = Math.min(1, (innerHeight - 124 - 50) / 720, (innerWidth - 24) / 1000);
  $("mapStage").style.transform = `scale(${Math.max(0.35, ms)})`;
}

// ---------- search: "ville + sujet" ----------
function stripPlace(text, placeName) {
  const fold = (s) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
  const placeWords = new Set(fold(placeName).split(/[\s,'-]+/));
  return text.split(/\s+/).filter((w) => !placeWords.has(fold(w).replace(/[,']/g, ""))).join(" ").trim();
}

let searchCtl = null;
async function doSearch() {
  const text = $("search").value.trim();
  if (!text) return;
  searchCtl?.abort();
  searchCtl = new AbortController();
  $("searchbox").classList.add("busy");
  try {
    const r = await api.search(text, text, searchCtl.signal);
    if (r.place) addPlaces([r.place]);
    addFeeds(r.items);
    const city = r.place?.name || r.items[0]?.city;
    if (!r.items.length || !city) { toast("Aucun résultat."); return; }
    // Stay on the globe: only the matching cards remain, the globe turns to
    // the place; the user then clicks a card to go down to country / city.
    setSearch({ city, text, topic: stripPlace(text, city), ids: new Set(r.items.map((i) => i.id)) });
    const target = r.place || r.items[0];
    if (route.view !== "world") go.world();
    world.focusOn(target.lon, target.lat);
    render();
  } catch (e) {
    if (e.name !== "AbortError") toast(`Recherche : ${e.message}`);
  } finally {
    $("searchbox").classList.remove("busy");
  }
}

// ---------- boot ----------
async function boot() {
  if (typeof d3 === "undefined" || typeof topojson === "undefined") {
    toast("Bibliothèques cartographiques non chargées.");
    return;
  }
  try {
    await loadWorld();
  } catch {
    toast("Données géographiques indisponibles.");
    return;
  }

  world = createWorld({
    root: app, canvas: $("globe"), cardLayer: $("worldCards"), tip: $("tip"),
    getCities: () => groupByCity(filtered()),
    onCity: openCityFromCard,
    onCountry: go.country,
    cardBounds: () => { // between header and footer, never under the open panel
      const panel = $("panel");
      const x1 = panel.classList.contains("closed") ? app.clientWidth : panel.offsetLeft;
      return { x0: 8, y0: 80, x1: x1 - 8, y1: app.clientHeight - 52 };
    },
  });
  map = createMapView({
    stage: $("mapStage"), canvas: $("map"), links: $("mapLinks"), cardLayer: $("mapCards"), tip: $("tip"),
    onCity: (c) => go.city(c.city), onCountry: go.country,
  });

  // UI events
  $("search").addEventListener("keydown", (e) => { if (e.key === "Enter") doSearch(); });
  const clearSearch = () => { $("search").value = ""; setSearch(null); render(); };
  $("clear").addEventListener("click", (e) => { e.preventDefault(); clearSearch(); });
  // "MONDE" in the crumbs while a search is shown on the globe = back to everything.
  $("crumbs").addEventListener("click", (e) => {
    if (route.view === "world" && store.search && e.target.closest('a[href="#/monde"]')) { e.preventDefault(); clearSearch(); }
  });
  $("filtersbtn").addEventListener("click", () => {
    const f = $("filters");
    f.hidden = !f.hidden;
    $("filtersbtn").setAttribute("aria-expanded", String(!f.hidden));
  });
  $("catsel").addEventListener("change", (e) => setFilter("category", e.target.value));
  $("datesel").addEventListener("change", (e) => setFilter("before", e.target.value));
  $("zoomin").addEventListener("click", () => (route.view === "world" ? world.zoom(1.2) : map.zoom(1.25)));
  $("zoomout").addEventListener("click", () => (route.view === "world" ? world.zoom(1 / 1.2) : map.zoom(0.8)));
  $("fold").addEventListener("click", () => { panelOpen = false; setPanelOpen(false); });
  $("tab").addEventListener("click", () => { panelOpen = true; setPanelOpen(true); });
  $("panel").addEventListener("transitionend", () => render()); // re-place cards around the panel
  addEventListener("keydown", (e) => { if (e.key === "Escape") $("filters").hidden = true; });
  addEventListener("hashchange", onRoute);
  addEventListener("resize", fitStages);
  fitStages();

  subscribe(() => render());

  // Public API (Indice integration, v1 compatibility)
  window.NIAN = Object.freeze({ updateFeeds: addFeeds, openCity: go.city, getFeeds: () => [...store.feeds.values()] });
  window.updateFeeds = addFeeds;

  // Data
  api.meta().then((m) => {
    store.categories = m.categories;
    for (const cat of Object.keys(m.categories)) $("catsel").append(h("option", { value: cat }, cat));
    if (!m.search_enabled) $("search").placeholder = "Recherche désactivée (clé YouTube absente)";
    render();
  }).catch(() => toast("API indisponible."));
  api.places().then(addPlaces).catch(() => {});
  Promise.all([api.meta(), api.feeds(500)]).then(([m, d]) => {
    addFeeds(d.items);
    if (!d.items.length) {
      toast(m.search_enabled
        ? "Collecte en cours : les premières vidéos arrivent dans quelques secondes."
        : "Aucune publication : ajoute ta clé YouTube (NIAN_YOUTUBE_KEY) ou lance « nian --demo ».");
    }
  }).catch(() => {});
  api.stream(addFeeds);

  onRoute();
}

boot();
