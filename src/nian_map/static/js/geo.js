// World geometry (Natural Earth via world-atlas) and country lookup.
/* global topojson, d3 */

const regionNames = new Intl.DisplayNames(["fr"], { type: "region" });
const geo = { low: null, mid: null, land: null, iso: {}, byId: new Map() };
const lookupCache = new Map();

async function json(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${url}: ${r.status}`);
  return r.json();
}

function unpack(topo) {
  const countries = topojson.feature(topo, topo.objects.countries).features;
  const borders = topojson.mesh(topo, topo.objects.countries, (a, b) => a !== b);
  return { countries, borders, all: { type: "FeatureCollection", features: countries } };
}

export async function loadWorld() {
  const [low, mid, iso] = await Promise.all([
    json("/static/data/countries-110m.json"),
    json("/static/data/countries-50m.json"),
    json("/static/data/iso-numeric.json"),
  ]);
  geo.low = unpack(low); // fast to redraw: the rotating globe
  geo.mid = unpack(mid); // detailed: country view and lookups
  geo.iso = iso;
  for (const f of geo.mid.countries) {
    f.key = countryKey(f);
    f.label = countryName(f);
    f.bbox = d3.geoBounds(f);
    geo.byId.set(f.key, f);
  }
  return geo;
}

// High-resolution land, loaded only when a city is opened.
let landPromise = null;
export function loadLand() {
  landPromise ??= json("/static/data/land-10m.json").then((topo) => {
    const land = topojson.feature(topo, topo.objects.land);
    const polys = land.type === "MultiPolygon" ? land.coordinates
      : land.features ? land.features.flatMap((f) => f.geometry.type === "Polygon" ? [f.geometry.coordinates] : f.geometry.coordinates)
        : land.geometry.type === "Polygon" ? [land.geometry.coordinates] : land.geometry.coordinates;
    geo.land = polys.map((coordinates) => {
      const feature = { type: "Polygon", coordinates };
      return { feature, bbox: d3.geoBounds(feature) };
    // Degenerate slivers read as "whole sphere" by d3 (area ≈ 4π): drop them.
    }).filter((p) => d3.geoArea(p.feature) < 2 * Math.PI);
    return geo.land;
  });
  return landPromise;
}

export const world = () => geo;

function countryKey(f) {
  return geo.iso[String(+f.id)] || f.id || f.properties.name;
}

export function countryName(f) {
  const a2 = geo.iso[String(+f.id)];
  try {
    if (a2) return regionNames.of(a2);
  } catch { /* fall through */ }
  return f.properties?.name || "—";
}

export function countryById(key) {
  return geo.byId.get(key) || null;
}

// Country containing a point; coastal city centroids that fall in the sea
// snap to the nearest country within ~150 km.
export function countryAt(lon, lat) {
  const k = `${lon.toFixed(2)},${lat.toFixed(2)}`;
  if (lookupCache.has(k)) return lookupCache.get(k);
  let hit = null;
  for (const f of geo.mid.countries) {
    const [[w, s], [e, n]] = f.bbox;
    const inLon = w <= e ? lon >= w && lon <= e : lon >= w || lon <= e;
    if (lat < s || lat > n || !inLon) continue;
    if (d3.geoContains(f, [lon, lat])) { hit = f; break; }
  }
  if (!hit) {
    let best = 0.025; // radians ≈ 160 km
    for (const f of geo.mid.countries) {
      // distance to the country's bounding box (cheap, good enough to snap)
      const [[w, s], [e, n]] = f.bbox;
      const cl = [Math.max(w, Math.min(e, lon)), Math.max(s, Math.min(n, lat))];
      const dd = d3.geoDistance([lon, lat], cl);
      if (dd < best) { best = dd; hit = f; }
    }
  }
  lookupCache.set(k, hit);
  return hit;
}

// Land polygons intersecting a lon/lat box (keeps the city redraw cheap).
export function landIn([[w, s], [e, n]]) {
  // A bbox whose west > east crosses the antimeridian (e.g. Eurasia-Africa).
  const lonHit = (a, c) => (a <= c ? !(c < w || a > e) : !(180 < w || a > e) || !(c < w || -180 > e));
  return (geo.land || []).filter(({ bbox: [[a, b], [c, d]] }) => lonHit(a, c) && !(d < s || b > n)).map((p) => p.feature);
}
