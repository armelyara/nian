// Card builders for the three levels. DOM is built with textContent only.
import { ago, net, netCodes } from "./nets.js";
import { h, httpsUrl, safeEmbed } from "./util.js";

const SVG_NS = "http://www.w3.org/2000/svg";

function playIcon(size = 14) {
  const s = document.createElementNS(SVG_NS, "svg");
  s.setAttribute("width", size); s.setAttribute("height", size);
  s.setAttribute("viewBox", "0 0 14 14"); s.setAttribute("aria-hidden", "true");
  s.classList.add("play");
  const p = document.createElementNS(SVG_NS, "path");
  p.setAttribute("d", "M4 2.5v9l7-4.5z"); p.setAttribute("fill", "#C3CDCB");
  s.append(p);
  return s;
}

function img(src) {
  const url = httpsUrl(src);
  if (!url) return null;
  const el = h("img", { src: url, alt: "", loading: "lazy", referrerpolicy: "no-referrer" });
  el.addEventListener("error", () => el.remove());
  return el;
}

const chips = (codes) => h("span", { class: "chips" }, codes.map((c) => h("span", { class: "chip" }, c)));

// Monde — one card per city: "ABIDJAN · 14", latest topic, networks.
export function worldCard(c, { top, onOpen }) {
  const latest = c.feeds[c.feeds.length - 1];
  const el = h("a", { class: `wcard${top ? " top" : ""}`, href: "#", "aria-label": `${c.city}, ${c.n} publications` },
    h("span", { class: "thumb" }, img(latest?.thumb), playIcon()),
    h("span", { class: "body" },
      h("span", { class: "ttl" }, `${c.city.toUpperCase()} · ${c.n}`),
      h("span", { class: "topic" }, latest?.text || ""),
      chips(netCodes(c.feeds))));
  el.addEventListener("click", (e) => { e.preventDefault(); onOpen(c); });
  return el;
}

// Pays — one card per city, media on top with its main network.
export function countryCard(c, { top, onOpen }) {
  const latest = c.feeds[c.feeds.length - 1];
  const el = h("a", { class: `pcard${top ? " top" : ""}`, href: "#", "aria-label": `${c.city}, ${c.n} publications` },
    h("span", { class: "media" }, img(latest?.thumb), playIcon(16), h("span", { class: "net" }, net(latest?.source).code)),
    h("span", { class: "body" },
      h("span", { class: "ttl" }, `${c.city.toUpperCase()} · ${c.n}`),
      h("span", { class: "topic" }, latest?.text || "")));
  el.addEventListener("click", (e) => { e.preventDefault(); onOpen(c); });
  return el;
}

function badge(code) {
  return h("span", { class: `badge n-${code}` }, code);
}

function author(f) {
  return f.author || "—";
}

// Ville — one card per publication, in the format of its network.
export function postCard(f) {
  const n = net(f.source);
  const source = httpsUrl(f.url);
  const tag = source ? "a" : "article";
  const attrs = source ? { href: source, target: "_blank", rel: "noopener noreferrer" } : {};
  const embed = safeEmbed(f.embed);
  const video = httpsUrl(f.video);

  if (n.format === "photo") {
    return h(tag, { ...attrs, class: "post photo" },
      h("div", { class: "meta" }, badge(n.code), author(f), h("span", { class: "ago" }, ago(f.ts))),
      h("div", { class: "media" }, img(f.thumb) || "[PHOTO]"),
      h("p", {}, f.text || ""));
  }
  if (n.format === "tt" || n.format === "yt") {
    // Content shows directly (no "watch live" button): videos play muted inline.
    let media = null;
    if (embed) media = h("iframe", { src: embed, allow: "autoplay; encrypted-media", loading: "lazy", title: f.text || "vidéo" });
    else if (video) {
      media = h("video", { src: video, muted: true, autoplay: true, loop: true, playsinline: true, preload: "metadata" });
      media.muted = true;
    } else media = img(f.thumb);
    return h(tag, { ...attrs, class: `post ${n.format}` },
      h("div", { class: "media" }, media, media ? null : playIcon(18), badge(n.code)),
      h("div", { class: "foot" },
        h("p", {}, f.text || ""),
        h("span", {}, `${author(f)} · ${ago(f.ts)}`)));
  }
  return h(tag, { ...attrs, class: "post text" },
    h("div", { class: "meta" }, badge(n.code), author(f), h("span", { class: "ago" }, ago(f.ts))),
    h("p", {}, f.text || ""));
}
