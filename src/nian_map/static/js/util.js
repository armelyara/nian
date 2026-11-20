// Shared helpers. DOM is built with textContent, never innerHTML with data.

export const EMBED_PREFIX = "https://www.youtube-nocookie.com/embed/";
const MONTHS = ["JAN", "FÉV", "MAR", "AVR", "MAI", "JUIN", "JUIL", "AOÛT", "SEP", "OCT", "NOV", "DÉC"];

export function fmtTs(ts) {
  const d = new Date(ts);
  if (Number.isNaN(d.getTime())) return String(ts ?? "");
  const p = (n) => String(n).padStart(2, "0");
  return `${d.getDate()} ${MONTHS[d.getMonth()]} ${d.getFullYear()} • ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
}

// Returns a normalized https URL or null (blocks javascript:, data:, http:).
export function httpsUrl(u) {
  if (typeof u !== "string" || !u) return null;
  try {
    const url = new URL(u);
    return url.protocol === "https:" ? url.href : null;
  } catch {
    return null;
  }
}

// iframe src is only ever a youtube-nocookie embed.
export function safeEmbed(u) {
  const url = httpsUrl(u);
  return url && url.startsWith(EMBED_PREFIX) ? url : null;
}

// Tiny element factory: h("div", { class: "x" }, "text", childNode)
export function h(tag, attrs = {}, ...children) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v == null || v === false) continue;
    if (k === "class") el.className = v;
    else if (k.startsWith("on") && typeof v === "function") el.addEventListener(k.slice(2), v);
    else el.setAttribute(k, v === true ? "" : String(v));
  }
  for (const c of children.flat()) {
    if (c == null || c === false) continue;
    el.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
  return el;
}

const SVG_NS = "http://www.w3.org/2000/svg";
export function svg(tag, attrs = {}) {
  const el = document.createElementNS(SVG_NS, tag);
  for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, String(v));
  return el;
}

let toastTimer = 0;
export function toast(msg) {
  const el = document.getElementById("toast");
  if (!el) return;
  el.textContent = msg;
  el.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove("show"), Math.max(4000, msg.length * 70));
}
