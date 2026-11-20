// World — orthographic globe drawn with d3-geo on a full-screen canvas, in the
// design's palette. The globe keeps the design's place and size (centred,
// 760 px stage) but the canvas covers the whole screen so zooming in never
// clips it.
//
// Behaviour requested after review:
//  - the globe ALWAYS rotates (clicks, hovers, filters, zoom never stop it);
//    only an active drag takes over, and the orbit resumes on release;
//  - zoom with the mouse wheel, with a two-finger pinch on touch screens,
//    or with the + / − buttons;
//  - hovering a country shows its name;
//  - only cities that have publications get a dot.
/* global d3 */
import { worldCard } from "./cards.js";
import { countryAt, world } from "./geo.js";
import { edgePoint, placeCards } from "./layout.js";

const STAGE = 760, BASE_R = 358;
const C = {
  sphere: "#0D1112", sphereEdge: "rgba(255,255,255,.16)", grid: "rgba(255,255,255,.05)",
  land: "#161B1D", border: "rgba(255,255,255,.14)", sel: "#1E2629", selEdge: "rgba(231,141,56,.6)",
  dot: "#E78D38", link: "rgba(231,141,56,.55)",
};
const SPEED = 4; // degrees per second
const ZOOM_MIN = 0.6, ZOOM_MAX = 4;
const MAX_CARDS = 8;

export function createWorld({ root, canvas, cardLayer, tip, getCities, onCity, onCountry, cardBounds }) {
  const ctx = canvas.getContext("2d");
  const projection = d3.geoOrthographic().rotate([-12, -16]).clipAngle(90).precision(0.6);
  const path = d3.geoPath(projection, ctx);
  const graticule = d3.geoGraticule10();
  const sphere = { type: "Sphere" };

  let W = 0, H = 0, fit = 1, zoom = 1;
  let running = false, raf = 0, last = 0, dirty = true;
  let hoverCountry = null, mouse = null;
  let cities = [];
  const pointers = new Map(); // active touches / mouse buttons
  let drag = null, pinch = null, focus = null;
  const cardEls = new Map();
  const memory = new Map();

  // ---- geometry: keep the design's position (stage at top 90, centred) ----
  function resize() {
    const dpr = Math.min(devicePixelRatio || 1, 2);
    W = root.clientWidth; H = root.clientHeight;
    canvas.width = W * dpr; canvas.height = H * dpr;
    canvas.style.width = `${W}px`; canvas.style.height = `${H}px`;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    fit = Math.max(0.35, Math.min(1, (H - 90 - 50) / STAGE, (W - 24) / STAGE));
    projection.translate([W / 2, 90 + (STAGE / 2) * fit]);
    applyZoom();
  }
  function applyZoom() {
    projection.scale(BASE_R * fit * zoom);
    dirty = true;
  }
  function zoomBy(f) {
    zoom = Math.max(ZOOM_MIN, Math.min(ZOOM_MAX, zoom * f));
    applyZoom();
  }

  const center = () => { const r = projection.rotate(); return [-r[0], -r[1]]; };
  const visible = (lon, lat) => d3.geoDistance([lon, lat], center()) < Math.PI / 2 - 0.08;
  const local = (e) => { const r = canvas.getBoundingClientRect(); return [e.clientX - r.left, e.clientY - r.top]; };
  function countryUnder(p) {
    const ll = projection.invert(p);
    return ll && d3.geoDistance(ll, center()) < Math.PI / 2 ? countryAt(ll[0], ll[1]) : null;
  }

  function draw() {
    const g = world().low;
    ctx.clearRect(0, 0, W, H);
    const [cx, cy] = projection.translate(), R = projection.scale();
    const halo = ctx.createRadialGradient(cx, cy, R * 0.96, cx, cy, R * 1.06);
    halo.addColorStop(0, "rgba(116,165,204,0.07)"); halo.addColorStop(1, "rgba(116,165,204,0)");
    ctx.fillStyle = halo; ctx.beginPath(); ctx.arc(cx, cy, R * 1.06, 0, Math.PI * 2); ctx.fill();

    ctx.beginPath(); path(sphere); ctx.fillStyle = C.sphere; ctx.fill();
    ctx.beginPath(); path(graticule); ctx.strokeStyle = C.grid; ctx.lineWidth = 1; ctx.stroke();
    ctx.beginPath(); path(g.all); ctx.fillStyle = C.land; ctx.fill();
    ctx.beginPath(); path(g.borders); ctx.strokeStyle = C.border; ctx.lineWidth = 0.8; ctx.stroke();
    if (hoverCountry) {
      ctx.beginPath(); path(hoverCountry); ctx.fillStyle = C.sel; ctx.fill();
      ctx.strokeStyle = C.selEdge; ctx.lineWidth = 1.2; ctx.stroke();
    }
    ctx.beginPath(); path(sphere); ctx.strokeStyle = C.sphereEdge; ctx.lineWidth = 1; ctx.stroke();

    // Only cities with publications are drawn; the 8 busiest get a card.
    const front = cities.filter((c) => visible(c.lon, c.lat));
    const items = front.slice(0, MAX_CARDS).map((c) => {
      const [x, y] = projection([c.lon, c.lat]);
      return { key: c.city, x, y, w: 172, h: 60, c };
    });
    const spots = placeCards(items, cardBounds(), memory);

    const shown = new Set();
    ctx.strokeStyle = C.link; ctx.lineWidth = 1;
    for (const it of items) {
      const r = spots.get(it.key);
      if (!r) continue;
      const e = edgePoint(it, r);
      ctx.beginPath(); ctx.moveTo(it.x, it.y); ctx.lineTo(e.x, e.y); ctx.stroke();
      shown.add(it.key);
      let el = cardEls.get(it.key);
      if (!el || el._n !== it.c.n) {
        el?.remove();
        el = worldCard(it.c, { top: it.c === cities[0], onOpen: onCity });
        el._n = it.c.n;
        cardLayer.append(el);
        cardEls.set(it.key, el);
      }
      el.style.left = `${r.x}px`; el.style.top = `${r.y}px`;
    }
    for (const [k, el] of cardEls) if (!shown.has(k)) { el.remove(); cardEls.delete(k); }

    for (const c of front) {
      const [x, y] = projection([c.lon, c.lat]);
      if (c === cities[0]) {
        ctx.fillStyle = "rgba(231,141,56,.18)"; ctx.beginPath(); ctx.arc(x, y, 16, 0, Math.PI * 2); ctx.fill();
      }
      ctx.fillStyle = C.dot; ctx.beginPath(); ctx.arc(x, y, c === cities[0] ? 5 : 4, 0, Math.PI * 2); ctx.fill();
    }
  }

  function updateTip() {
    // Country name under the mouse (re-evaluated while the globe turns).
    if (!mouse || drag || pinch) { hoverCountry = null; tip.hidden = true; return; }
    hoverCountry = countryUnder(mouse.p);
    canvas.style.cursor = hoverCountry ? "pointer" : "";
    if (!hoverCountry) { tip.hidden = true; return; }
    tip.textContent = hoverCountry.label;
    tip.hidden = false;
    tip.style.left = `${mouse.x + 14}px`; tip.style.top = `${mouse.y + 14}px`;
  }

  function frame(t) {
    raf = requestAnimationFrame(frame);
    const dt = last ? Math.min(t - last, 64) : 16;
    last = t;
    if (focus && !drag) { // ease towards a searched place, then keep orbiting
      const k = Math.min(1, (t - focus.t0) / 900), e = k * (2 - k);
      const lam = focus.from[0] + (focus.to[0] - focus.from[0]) * e;
      const phi = focus.from[1] + (focus.to[1] - focus.from[1]) * e;
      projection.rotate([lam, phi, 0]);
      if (k >= 1) focus = null;
      dirty = true;
    } else if (!drag) { // the orbit never pauses, except while the user holds the globe
      const r = projection.rotate();
      projection.rotate([r[0] + SPEED * dt / 1000, r[1], r[2]]);
      dirty = true;
    }
    if (dirty) { dirty = false; updateTip(); draw(); }
  }

  // ---- pointer input: 1 pointer = rotate, 2 pointers = pinch zoom ----
  canvas.addEventListener("pointerdown", (e) => {
    canvas.setPointerCapture(e.pointerId);
    pointers.set(e.pointerId, local(e));
    if (pointers.size === 1) {
      drag = { p: local(e), r: projection.rotate(), moved: 0 };
      canvas.classList.add("dragging");
    } else if (pointers.size === 2) {
      const [a, b] = [...pointers.values()];
      pinch = { d: Math.hypot(a[0] - b[0], a[1] - b[1]) || 1, zoom };
      drag = null; // a pinch is not a click
    }
  });
  canvas.addEventListener("pointermove", (e) => {
    const p = local(e);
    if (e.pointerType === "mouse") {
      const r = root.getBoundingClientRect();
      mouse = { p, x: e.clientX - r.left, y: e.clientY - r.top };
    }
    if (pointers.has(e.pointerId)) pointers.set(e.pointerId, p);
    if (pinch && pointers.size >= 2) {
      const [a, b] = [...pointers.values()];
      zoom = Math.max(ZOOM_MIN, Math.min(ZOOM_MAX, pinch.zoom * Math.hypot(a[0] - b[0], a[1] - b[1]) / pinch.d));
      applyZoom();
      return;
    }
    if (drag) {
      const k = 0.25 / (fit * zoom);
      const dx = p[0] - drag.p[0], dy = p[1] - drag.p[1];
      drag.moved = Math.max(drag.moved, Math.hypot(dx, dy));
      projection.rotate([drag.r[0] + dx * k, Math.max(-80, Math.min(80, drag.r[1] - dy * k)), 0]);
    }
    dirty = true;
  });
  const release = (e) => {
    pointers.delete(e.pointerId);
    if (pointers.size < 2) pinch = null;
    if (!drag) return;
    const click = drag.moved < 5;
    drag = null;
    canvas.classList.remove("dragging");
    if (click && e.type === "pointerup") {
      const f = countryUnder(local(e));
      if (f) onCountry(f);
    }
  };
  canvas.addEventListener("pointerup", release);
  canvas.addEventListener("pointercancel", release);
  canvas.addEventListener("pointerleave", () => { mouse = null; tip.hidden = true; hoverCountry = null; dirty = true; });
  // Wheel anywhere over the globe area, cards included.
  canvas.parentElement.addEventListener("wheel", (e) => {
    e.preventDefault();
    zoomBy(Math.exp(-e.deltaY * 0.0015));
  }, { passive: false });

  addEventListener("resize", resize);
  resize();

  return {
    refresh() { cities = getCities(); dirty = true; },
    start() { if (running) return; running = true; last = 0; cities = getCities(); resize(); raf = requestAnimationFrame(frame); },
    stop() { running = false; cancelAnimationFrame(raf); tip.hidden = true; },
    zoom: zoomBy,
    focusOn(lon, lat) {
      const [l0, p0] = projection.rotate();
      let to = -lon;
      while (to - l0 > 180) to -= 360; // shortest way round
      while (to - l0 < -180) to += 360;
      focus = { from: [l0, p0], to: [to, Math.max(-60, Math.min(60, -lat))], t0: performance.now() };
    },
  };
}
