// Single client-side state container with change notification and a
// memoized filtered view (recomputed only when data or filters change,
// not on every animation frame as in v1).

const MAX_FEEDS = 500;

export const store = {
  feeds: new Map(), // id -> item, insertion-ordered
  places: new Map(), // name -> { lat, lon }
  categories: {}, // name -> color
  filters: { category: "all", city: "all", before: "" },
};

const listeners = new Set();
let filteredCache = null;

export function subscribe(fn) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

function emit(kind) {
  filteredCache = null;
  listeners.forEach((fn) => fn(kind));
}

function isValidItem(it) {
  return it && typeof it.id === "string" && it.id.length <= 64 &&
    Number.isFinite(it.lat) && Math.abs(it.lat) <= 90 &&
    Number.isFinite(it.lon) && Math.abs(it.lon) <= 180;
}

export function addFeeds(items) {
  let changed = false;
  for (const it of [].concat(items || [])) {
    if (!isValidItem(it) || store.feeds.has(it.id)) continue;
    store.feeds.set(it.id, it);
    changed = true;
  }
  while (store.feeds.size > MAX_FEEDS) store.feeds.delete(store.feeds.keys().next().value);
  if (changed) emit("feeds");
}

export function addPlaces(list) {
  let changed = false;
  for (const p of [].concat(list || [])) {
    if (!p || typeof p.name !== "string" || !Number.isFinite(p.lat) || !Number.isFinite(p.lon)) continue;
    if (!store.places.has(p.name)) {
      store.places.set(p.name, { lat: p.lat, lon: p.lon });
      changed = true;
    }
  }
  if (changed) emit("places");
}

export function setFilter(key, value) {
  store.filters[key] = value;
  emit("filters");
}

const tsOf = (f) => Date.parse(f.ts) || 0;

export function filtered() {
  if (filteredCache) return filteredCache;
  const { category, city, before } = store.filters;
  const tmax = before ? Date.parse(before) : null;
  const only = store.search ? store.search.ids : null; // active search narrows everything
  filteredCache = [...store.feeds.values()]
    .filter((f) => (!only || only.has(f.id)) &&
      (category === "all" || f.category === category) &&
      (city === "all" || f.city === city) &&
      (!tmax || tsOf(f) <= tmax))
    .sort((a, b) => tsOf(a) - tsOf(b));
  return filteredCache;
}

export function feedsForCity(city) {
  return filtered().filter((f) => f.city === city);
}

// ---- aggregation by city (the unit shown on the globe and country maps) ----
export function groupByCity(feeds) {
  const by = new Map();
  for (const f of feeds) {
    let c = by.get(f.city);
    if (!c) { c = { city: f.city, feeds: [], n: 0, sx: 0, sy: 0 }; by.set(f.city, c); }
    c.feeds.push(f); c.n += 1; c.sx += f.lon; c.sy += f.lat;
  }
  for (const c of by.values()) {
    const p = store.places.get(c.city);
    c.lon = p ? p.lon : c.sx / c.n;
    c.lat = p ? p.lat : c.sy / c.n;
  }
  return [...by.values()].sort((a, b) => b.n - a.n);
}

// Active search ("ville + sujet"), or null.
store.search = null;
export function setSearch(s) {
  store.search = s;
  filteredCache = null;
  listeners.forEach((fn) => fn("search"));
}
