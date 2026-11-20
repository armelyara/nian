// Social networks: short code, label and the kind of content each one shows.
const NETS = {
  X: { code: "X", name: "X", kind: "posts", format: "text" },
  Twitter: { code: "X", name: "X", kind: "posts", format: "text" },
  Instagram: { code: "IG", name: "Instagram", kind: "photos", format: "photo" },
  TikTok: { code: "TT", name: "TikTok", kind: "vidéos", format: "tt" },
  Facebook: { code: "FB", name: "Facebook", kind: "posts", format: "text" },
  YouTube: { code: "YT", name: "YouTube", kind: "vidéos", format: "yt" },
};
const ORDER = ["X", "TT", "IG", "FB", "YT"];

export function net(source) {
  return NETS[source] || { code: "WEB", name: source || "Web", kind: "posts", format: "text" };
}

// Unique network codes of a list of feeds, in a stable display order.
export function netCodes(feeds) {
  const set = new Set(feeds.map((f) => net(f.source).code));
  return [...set].sort((a, b) => (ORDER.indexOf(a) + 99) % 99 - (ORDER.indexOf(b) + 99) % 99);
}

// Per-network counts for the city panel, most frequent first.
export function netBreakdown(feeds) {
  const by = new Map();
  for (const f of feeds) {
    const n = net(f.source);
    const row = by.get(n.code) || { ...n, n: 0 };
    row.n += 1;
    by.set(n.code, row);
  }
  return [...by.values()].sort((a, b) => b.n - a.n);
}

export function ago(ts) {
  const t = Date.parse(ts);
  if (!t) return "";
  const s = Math.max(0, (Date.now() - t) / 1000);
  if (s < 3600) return `${Math.max(1, Math.round(s / 60))} min`;
  if (s < 86400) return `${Math.round(s / 3600)} h`;
  return `${Math.round(s / 86400)} j`;
}
