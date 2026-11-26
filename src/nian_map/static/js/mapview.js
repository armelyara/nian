// Country and City — flat Mercator maps drawn with d3-geo, exactly in the
// design's style: dark sea, faint graticule, land #151A1C/#161B1D, white
// borders at 14 %, selected country outlined in accent.
/* global d3 */
import { countryCard, postCard } from "./cards.js";
import { countryAt, landIn, loadLand, world } from "./geo.js";
import { edgePoint, placeCards } from "./layout.js";
import { svg } from "./util.js";

const W = 1000, H = 720;
const C = {
  sea: "#0B0E0F", grid: "rgba(255,255,255,.06)", land: "#151A1C", cityLand: "#161B1D",
  border: "rgba(255,255,255,.14)", coast: "rgba(162,179,177,.34)", sel: "#1E2629", selEdge: "rgba(231,141,56,.6)",
  dot: "#E78D38", halo: "rgba(231,141,56,.18)", link: "rgba(231,141,56,.55)",
};

function niceStep(spanDeg) {
  const raw = spanDeg / 12;
  const steps = [0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10];
  return steps.find((s) => s >= raw) || 10;
}

export function createMapView({ stage, canvas, links, cardLayer, tip, onCity, onCountry }) {
  const dpr = Math.min(devicePixelRatio || 1, 2);
  canvas.width = W * dpr; canvas.height = H * dpr;
  canvas.style.width = `${W}px`; canvas.style.height = `${H}px`;
  const ctx = canvas.getContext("2d");
  ctx.scale(dpr, dpr);

  const projection = d3.geoMercator();
  const path = d3.geoPath(projection, ctx);
  let mode = null, country = null, cityName = null, items = [], zoom = 1, base = null;
  const memory = new Map();
  let measured = new Map(); // card key -> {w,h}

  function fit(feature, extent) {
    projection.scale(1).translate([0, 0]).fitExtent(extent, feature);
    base = { scale: projection.scale(), translate: projection.translate() };
    zoom = 1;
  }
  // Zoom by factor f keeping map point p (stage px) fixed under the finger/cursor.
  function zoomAt(p, f) {
    if (!base) return;
    const next = Math.max(0.5, Math.min(12, zoom * f));
    f = next / zoom; zoom = next;
    const [tx, ty] = projection.translate();
    projection.scale(projection.scale() * f).translate([p[0] - (p[0] - tx) * f, p[1] - (p[1] - ty) * f]);
    schedule();
  }
  function panBy(dx, dy) {
    const [tx, ty] = projection.translate();
    projection.translate([tx + dx, ty + dy]);
    schedule();
  }
  let pending = false;
  function schedule() {
    if (pending) return;
    pending = true;
    requestAnimationFrame(() => { pending = false; render(); });
  }

  function viewBounds() {
    const tl = projection.invert([0, 0]), br = projection.invert([W, H]);
    return [[tl[0], br[1]], [br[0], tl[1]]];
  }

  function drawGrid() {
    const b = viewBounds();
    const step = niceStep(Math.max(b[1][0] - b[0][0], b[1][1] - b[0][1]));
    ctx.beginPath();
    path(d3.geoGraticule().extent([[b[0][0] - step, b[0][1] - step], [b[1][0] + step, b[1][1] + step]]).step([step, step])());
    ctx.strokeStyle = C.grid; ctx.lineWidth = 1; ctx.stroke();
  }

  function drawBase() {
    ctx.fillStyle = C.sea; ctx.fillRect(0, 0, W, H);
    const g = world().mid;
    if (mode === "country") {
      drawGrid();
      ctx.beginPath(); path(g.all); ctx.fillStyle = C.land; ctx.fill();
      ctx.beginPath(); path(g.borders); ctx.strokeStyle = C.border; ctx.lineWidth = 0.8; ctx.stroke();
      ctx.beginPath(); path(country); ctx.fillStyle = C.sel; ctx.fill();
      ctx.strokeStyle = C.selEdge; ctx.lineWidth = 1.2; ctx.stroke();
    } else {
      // City view: fill land, draw the graticule ON TOP (so it stays visible
      // even when the whole viewport is inland), then stroke the coastline.
      const polys = landIn(viewBounds());
      const trace = () => { ctx.beginPath(); for (const p of polys) path(p); };
      if (polys.length) {
        trace(); ctx.fillStyle = C.cityLand; ctx.fill();
        drawGrid();
        trace(); ctx.strokeStyle = C.coast; ctx.lineWidth = 1; ctx.stroke();
      } else {
        drawGrid();
        ctx.beginPath(); path(g.all); ctx.fillStyle = C.cityLand; ctx.fill(); // 10 m land not loaded yet
      }
    }
  }

  // Cards stay inside the map and out from under the open side panel.
  function cardBounds() {
    let x1 = W;
    const panel = document.getElementById("panel");
    if (panel && !panel.classList.contains("closed")) {
      const s = stage.getBoundingClientRect(), p = panel.getBoundingClientRect();
      const scale = s.width / W || 1;
      x1 = Math.min(W, (p.left - s.left) / scale - 8);
    }
    return { x0: 0, y0: 0, x1: Math.max(x1, 400), y1: H };
  }

  // Cards are measured once (their height depends on the network format).
  function sizeOf(key, el) {
    if (!measured.has(key)) {
      el.style.visibility = "hidden"; el.style.left = "0px"; el.style.top = "0px";
      cardLayer.append(el);
      measured.set(key, { w: el.offsetWidth, h: el.offsetHeight });
      el.style.visibility = "";
    }
    return measured.get(key);
  }

  function render() {
    if (!mode) return;
    drawBase();
    links.replaceChildren();
    const els = new Map([...cardLayer.children].map((el) => [el.dataset.key, el]));
    const anchors = items.map((it) => {
      const [x, y] = projection([it.lon, it.lat]);
      const elKey = it.elKey || it.key; // DOM identity (changes when content changes)
      let el = els.get(elKey);
      if (!el) { el = it.build(); el.dataset.key = elKey; }
      const { w, h } = sizeOf(elKey, el);
      return { ...it, x, y, w, h, el };
    });
    const spots = placeCards(anchors, cardBounds(), memory);
    const keep = new Set();
    for (const a of anchors) {
      const inView = a.x > -20 && a.x < W + 20 && a.y > -20 && a.y < H + 20;
      const r = spots.get(a.key);
      if (inView && a.top) {
        ctx.fillStyle = C.halo; ctx.beginPath(); ctx.arc(a.x, a.y, 18, 0, Math.PI * 2); ctx.fill();
      }
      if (inView) {
        ctx.fillStyle = C.dot; ctx.beginPath(); ctx.arc(a.x, a.y, a.top ? 6 : mode === "city" ? 5 : 4, 0, Math.PI * 2); ctx.fill();
      }
      if (!r || !inView) continue;
      const e = edgePoint(a, r);
      links.append(svg("line", { x1: a.x, y1: a.y, x2: e.x, y2: e.y, stroke: C.link, "stroke-width": 1 }));
      if (!a.el.isConnected) cardLayer.append(a.el);
      a.el.style.left = `${r.x}px`; a.el.style.top = `${r.y}px`;
      keep.add(a.el.dataset.key);
    }
    for (const el of [...cardLayer.children]) if (!keep.has(el.dataset.key)) el.remove();
  }

  // ---- input: drag = pan, wheel / pinch = zoom, click = neighbour country,
  //      hover = country name ----
  const pointers = new Map();
  let drag = null, pinch = null;
  const local = (e) => {
    const r = canvas.getBoundingClientRect(), k = r.width / W;
    return [(e.clientX - r.left) / k, (e.clientY - r.top) / k];
  };
  const countryUnder = (p) => { const ll = projection.invert(p); return ll ? countryAt(ll[0], ll[1]) : null; };

  canvas.addEventListener("pointerdown", (e) => {
    canvas.setPointerCapture(e.pointerId);
    pointers.set(e.pointerId, local(e));
    if (pointers.size === 1) drag = { p: local(e), moved: 0 };
    if (pointers.size === 2) {
      const [a, b] = [...pointers.values()];
      pinch = { d: Math.hypot(a[0] - b[0], a[1] - b[1]) || 1 };
      drag = null;
    }
    tip.hidden = true;
  });
  canvas.addEventListener("pointermove", (e) => {
    const p = local(e);
    if (pointers.has(e.pointerId)) pointers.set(e.pointerId, p);
    if (pinch && pointers.size >= 2) {
      const [a, b] = [...pointers.values()];
      const d = Math.hypot(a[0] - b[0], a[1] - b[1]) || 1;
      zoomAt([(a[0] + b[0]) / 2, (a[1] + b[1]) / 2], d / pinch.d);
      pinch.d = d;
      return;
    }
    if (drag) {
      drag.moved += Math.hypot(p[0] - drag.p[0], p[1] - drag.p[1]);
      panBy(p[0] - drag.p[0], p[1] - drag.p[1]);
      drag.p = p;
      return;
    }
    if (e.pointerType === "mouse" && mode === "country") {
      const f = countryUnder(p);
      if (!f) { tip.hidden = true; return; }
      const r = tip.parentElement.getBoundingClientRect();
      tip.textContent = f.label;
      tip.hidden = false;
      tip.style.left = `${e.clientX - r.left + 14}px`; tip.style.top = `${e.clientY - r.top + 14}px`;
    }
  });
  const release = (e) => {
    pointers.delete(e.pointerId);
    if (pointers.size < 2) pinch = null;
    if (!drag) return;
    const click = drag.moved < 5;
    drag = null;
    if (click && e.type === "pointerup" && mode === "country") {
      const f = countryUnder(local(e));
      if (f && f !== country) onCountry(f);
    }
  };
  canvas.addEventListener("pointerup", release);
  canvas.addEventListener("pointercancel", release);
  canvas.addEventListener("pointerleave", () => { tip.hidden = true; });
  // Wheel anywhere over the map, cards included, zooming around the cursor.
  stage.addEventListener("wheel", (e) => {
    e.preventDefault();
    zoomAt(local(e), Math.exp(-e.deltaY * 0.0015));
  }, { passive: false });

  return {
    get mode() { return mode; },
    showCountry(feature, cities) {
      const changed = mode !== "country" || country !== feature;
      mode = "country"; country = feature; cityName = null;
      if (changed) { fit(feature, [[215, 60], [785, 660]]); memory.clear(); measured.clear(); cardLayer.replaceChildren(); }
      const top = cities[0];
      items = cities.map((c) => ({ key: c.city, elKey: `${c.city}:${c.n}:${c === top}`, lon: c.lon, lat: c.lat, top: c === top, build: () => countryCard(c, { top: c === top, onOpen: onCity }) }));
      render();
    },
    async showCity(name, center, feeds) {
      const changed = mode !== "city" || cityName !== name;
      mode = "city"; cityName = name; country = null;
      if (changed) {
        // frame the city and its publications, at least ±0.12° around it
        const lons = feeds.map((f) => f.lon).concat(center.lon - 0.12, center.lon + 0.12);
        const lats = feeds.map((f) => f.lat).concat(center.lat - 0.09, center.lat + 0.09);
        const box = { type: "MultiPoint", coordinates: [[Math.min(...lons), Math.min(...lats)], [Math.max(...lons), Math.max(...lats)]] };
        fit(box, [[230, 150], [770, 570]]);
        memory.clear(); measured.clear(); cardLayer.replaceChildren();
      }
      items = feeds.map((f) => ({ key: f.id, lon: f.lon, lat: f.lat, top: false, build: () => postCard(f) }));
      render();
      if (!world().land) { await loadLand(); if (mode === "city") render(); }
    },
    zoom(f) { zoomAt([W / 2, H / 2], f); },
    clear() { mode = null; tip.hidden = true; cardLayer.replaceChildren(); links.replaceChildren(); },
  };
}
