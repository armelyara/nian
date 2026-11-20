// Right panel (collapsible, overlays the map) and footer.
import { netBreakdown, netCodes } from "./nets.js";
import { h } from "./util.js";

const $ = (id) => document.getElementById(id);

function cityRow(c, top, onOpen) {
  const row = h("a", { class: `prow${top ? " hi" : ""}`, href: "#" },
    h("span", { class: "nm" }, c.city),
    h("span", { class: "chips" }, netCodes(c.feeds).map((n) => h("span", { class: "chip" }, n))),
    h("span", { class: "cnt" }, c.n));
  row.addEventListener("click", (e) => { e.preventDefault(); onOpen(c); });
  return row;
}

const plural = (n, one, many) => `${n} ${n > 1 ? many : one}`;

export function renderCitiesPanel(title, cities, onOpen) {
  const total = cities.reduce((s, c) => s + c.n, 0);
  $("panelTitle").textContent = title;
  $("panelSub").textContent = `${plural(cities.length, "ville", "villes")} · ${plural(total, "publication", "publications")}`;
  $("panelRows").replaceChildren(...(cities.length
    ? cities.map((c, i) => cityRow(c, i === 0, onOpen))
    : [h("div", { class: "empty" }, "Aucune publication pour l'instant.")]));
  $("tabLabel").textContent = "VILLES";
}

export function renderNetworksPanel(title, subtitle, feeds) {
  $("panelTitle").textContent = title;
  $("panelSub").textContent = subtitle;
  const rows = netBreakdown(feeds).map((r) => h("div", { class: "prow" },
    h("span", { class: `code n-${r.code}` }, r.code),
    h("span", { class: "nm" }, r.name),
    h("span", { class: "kind" }, r.kind),
    h("span", { class: "cnt" }, r.n)));
  $("panelRows").replaceChildren(...(rows.length ? rows : [h("div", { class: "empty" }, "Aucune publication.")]));
  $("tabLabel").textContent = "RÉSEAUX";
}

export function setPanelOpen(open) {
  $("panel").classList.toggle("closed", !open);
  $("tab").hidden = open;
}

// Footer: category counts (design shows the four main themes) + TOTAL.
export function renderCategoryFooter(categories, feeds) {
  const by = {};
  feeds.forEach((f) => { by[f.category] = (by[f.category] || 0) + 1; });
  const items = Object.entries(categories).filter(([cat]) => cat !== "Autre").map(([cat, color]) => {
    const sw = h("span", { class: "sw" });
    sw.style.background = color;
    return h("span", { class: "cat" }, sw, `${cat} `, h("b", {}, by[cat] || 0));
  });
  $("footer").replaceChildren(...items, h("span", { class: "total" }, "TOTAL ", h("b", {}, feeds.length)));
}

export function renderLabelFooter(label, total) {
  $("footer").replaceChildren(h("span", { class: "lbl" }, label), h("span", { class: "total" }, "TOTAL ", h("b", {}, total)));
}
