// Thin HTTP client for the Nian API v1.

function token() {
  try {
    return localStorage.getItem("nianToken") || "";
  } catch {
    return "";
  }
}

async function getJSON(url, { signal, headers = {} } = {}) {
  const r = await fetch(url, { signal, headers: { Accept: "application/json", ...headers } });
  const body = await r.json().catch(() => ({}));
  if (!r.ok) {
    const msg = typeof body.detail === "string" ? body.detail : `Error ${r.status}`;
    throw new Error(msg);
  }
  return body;
}

export const api = {
  meta: () => getJSON("/api/v1/meta"),
  places: () => getJSON("/api/v1/places"),
  feeds: (limit = 100) => getJSON(`/api/v1/feeds?limit=${limit}`),
  search(q, place, signal) {
    const t = token();
    const qs = new URLSearchParams({ q, place });
    return getJSON(`/api/v1/search?${qs}`, { signal, headers: t ? { "X-Nian-Token": t } : {} });
  },
  // EventSource reconnects by itself (server sends retry: 5000).
  stream(onItem) {
    const es = new EventSource("/api/v1/stream");
    es.onmessage = (ev) => {
      try {
        onItem(JSON.parse(ev.data));
      } catch { /* ignore malformed frames */ }
    };
    return es;
  },
};
