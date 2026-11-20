// Card placement rule from the design: each card sits beside its point,
// linked by a thin line, and cards never overlap — they are shifted side by
// side around the point. Greedy search over rings of candidate positions,
// biggest items first, with stickiness so cards don't jump between frames.

const ANGLES = [0, 180, -30, 30, 150, 210, -60, 60, 120, 240, -90, 90];
const RINGS = 7;

function overlaps(a, b, gap) {
  return a.x < b.x + b.w + gap && a.x + a.w + gap > b.x && a.y < b.y + b.h + gap && a.y + a.h + gap > b.y;
}

function candidate(p, angleDeg, ring, w, h) {
  const a = angleDeg * Math.PI / 180;
  const d = 14 + ring * 26;
  const cx = p.x + Math.cos(a) * (d + w / 2);
  const cy = p.y + Math.sin(a) * (d + h / 2);
  return { x: Math.round(cx - w / 2), y: Math.round(cy - h / 2), w, h };
}

// items: [{ key, x, y, w, h }] in priority order; bounds: {x0,y0,x1,y1}
// prev: Map(key -> {angle, ring}) from the previous call (mutated).
export function placeCards(items, bounds, prev = new Map(), gap = 8) {
  const placed = [];
  const out = new Map();
  const points = items.map((i) => ({ x: i.x - 6, y: i.y - 6, w: 12, h: 12 }));
  for (const it of items) {
    const last = prev.get(it.key);
    const order = [];
    if (last) order.push([last.angle, last.ring]);
    for (let r = 0; r < RINGS; r++) for (const a of ANGLES) order.push([a, r]);
    let chosen = null;
    for (const [angle, ring] of order) {
      const c = candidate(it, angle, ring, it.w, it.h);
      if (c.x < bounds.x0 || c.y < bounds.y0 || c.x + c.w > bounds.x1 || c.y + c.h > bounds.y1) continue;
      if (placed.some((p) => overlaps(c, p, gap))) continue;
      if (points.some((p) => overlaps(c, p, 0))) continue; // never hide another city's dot
      chosen = { ...c, angle, ring };
      break;
    }
    if (!chosen) continue; // no room: the card is skipped rather than overlapping
    placed.push(chosen);
    prev.set(it.key, { angle: chosen.angle, ring: chosen.ring });
    out.set(it.key, chosen);
  }
  return out;
}

// End of the link line: the point of the card's border closest to the dot.
export function edgePoint(p, r) {
  return {
    x: Math.max(r.x, Math.min(p.x, r.x + r.w)),
    y: Math.max(r.y, Math.min(p.y, r.y + r.h)),
  };
}
