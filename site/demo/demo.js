// Demo: derive a Food Web style listing from a producer's website, and notice when it changes.
// A browser port of scripts/demo/url_to_listing.py. Facts only: nothing is copied from the site
// beyond short pointers. Pages are fetched through a public CORS proxy because browsers cannot read
// other sites directly; snapshots live in this browser's localStorage and never leave it.
(function () {
  "use strict";

  const PROXIES = [
    (u) => "https://api.allorigins.win/raw?url=" + encodeURIComponent(u),
    (u) => "https://corsproxy.io/?" + encodeURIComponent(u),
  ];
  const MAX_PAGES = 3;          // home + 2 linked pages (the Python tool reads 5)
  const DELAY_MS = 1000;
  const STORE = "cofw-demo-snapshots-v1";
  const FIELDS = [
    ["name", "Name"], ["phone", "Phone"], ["email", "Email"], ["address", "Address"],
    ["hours_text", "Hours"], ["facebook", "Facebook"], ["instagram", "Instagram"],
    ["sales_channels", "Sells via"], ["product_groups", "Products"],
  ];

  const PRODUCT_GROUPS = [
    ["veggies", /veggie|vegetable|\bproduce\b|greens|lettuce|tomato|squash|potato|beet|carrot|\bpeppers?\b|kale|broccoli|asparagus|chile|onion|pumpkin|cucumber|spinach|microgreen|sprouts/],
    ["fruit", /fruit|\bfigs?\b|apple|apricot|peach|cherr|berr|melon|plum|\bpears?\b|grape/],
    ["beef-meat", /beef|meat|pork|lamb|bison|sausage|jerky|goat meat|hides?/],
    ["poultry-eggs", /poultry|\beggs?\b|chicken|turkey|duck|quail/],
    ["dairy", /dairy|milk|cheese|yogurt|ice cream|(?<!peach )(?<!apple )(?<!nut )(?<!almond )(?<!cocoa )butter|kefir|chevre/],
    ["honey", /honey|\bbees?\b|apiary|beeswax/],
    ["flowers", /(?<!wild)flower|lavender|bouquet|zinnia/],
    ["garlic-herbs", /spice|garlic|herb/],
    ["mushrooms", /mushroom/],
    ["baked-goods", /bread|baked|bakery|pastr|sourdough|cookie|pie\b/],
    ["seeds-plants", /\bseeds?\b|seedling|plant starts?|\bstarts\b|nursery|houseplant/],
    ["drinks", /wine|cider|brew|\bbeer|\bhops?\b|kombucha|juice|coffee|\bteas?\b|soft drinks?|beverage|verjus/],
  ];

  const CHANNEL_RULES = [
    ["farm_stand", "high", /farm[\s-]?stand|farmstand|farm[\s-]?store|farm[\s-]?shop|on[\s-]farm (?:store|stand|sales|shop)|roadside stand/i],
    ["u_pick", "high", /\bu[\s-]?pick\b|\byou[\s-]?pick\b|pick[\s-]your[\s-]own|\bPYO\b/i],
    ["csa", "high", /\bCSA\b|community[\s-]supported agriculture|farm share|harvest share|(?:veggie|vegetable|flower|meat|egg) share/i],
    ["online", "high", /online (?:store|shop|ordering|orders?)|order online|shop online|add to cart|web ?store|buy online/i],
    ["pickup", "high", /(?:order|curbside|farm|csa|share|local) pick[\s-]?up|pick[\s-]?up (?:location|day|site|time|window)s?/i],
    ["delivery", "high", /(?:home|local|free|weekly|doorstep) delivery|we deliver|delivery (?:available|area|day|zone)s?|delivers? (?:to|within)/i],
    ["wholesale", "high", /wholesale/i],
    ["farmers_market", "medium", /(?:find us|sell|selling|vendors?|booth|sold|available|join us|see us) (?:at|in) (?:the |our |several |local |these )?(?:[\w'’-]+ ){0,3}farmers[’']?\s?markets?|farmers[’']?\s?markets? (?:schedule|vendor|booth)/i],
  ];
  const NEGATION = /\b(?:no|not|never|without|n['’]t|isn['’]t|don['’]t|doesn['’]t|aren['’]t|longer|closed|cancel(?:l)?ed|sold out|waitlist|full)\b/i;
  const PAGE_LINK = /shop|store|csa|share|u-?pick|pick-?your|farm-?stand|farm-?store|visit|order|buy|deliver|wholesale|market|products|purchase|where/i;
  const OTHERS_PAGE = /retailer|stockist|where-to-buy|find-us|locations/i;

  // ---------- fetching ----------
  const OWN_PROXY = ((window.FOODWEB_DEMO || {}).PROXY_URL || "").replace(/\/$/, "");
  const REFUSALS = {
    "robots-disallowed": "This site's robots.txt asks automated tools not to read that page, so the demo stops here.",
    "not-a-web-page": "That address isn't a web page.",
    "too-large": "That page is too large for the demo.",
    "rate-limited": "Too many requests just now; wait a minute and try again.",
    "url-not-allowed": "That address can't be read by the demo.",
  };

  async function viaProxy(url) {
    if (OWN_PROXY) {
      const ctl = new AbortController();
      const timer = setTimeout(() => ctl.abort(), 20000);
      try {
        const r = await fetch(OWN_PROXY + "/?url=" + encodeURIComponent(url), { signal: ctl.signal });
        const body = await r.text();
        if (r.ok) return body;
        const err = new Error(REFUSALS[body.trim()] || "The site returned HTTP " + r.status + ".");
        err.final = true;
        throw err;
      } finally { clearTimeout(timer); }
    }
    let lastErr;
    for (const p of PROXIES) {
      try {
        const ctl = new AbortController();
        const timer = setTimeout(() => ctl.abort(), 15000);
        const r = await fetch(p(url), { signal: ctl.signal });
        clearTimeout(timer);
        if (r.ok) return await r.text();
        lastErr = new Error("HTTP " + r.status);
      } catch (e) { lastErr = e; }
    }
    throw lastErr || new Error("fetch failed");
  }

  async function robotsAllows(url) {
    if (OWN_PROXY) return true;     // the Worker checks robots.txt itself
    // Honors "Disallow: /" and prefix rules under User-agent: * (a simplified reading of robots.txt).
    try {
      const u = new URL(url);
      const txt = await viaProxy(u.origin + "/robots.txt");
      if (/<html/i.test(txt)) return true;
      let applies = false, ok = true;
      for (const raw of txt.split(/\r?\n/)) {
        const line = raw.split("#")[0].trim();
        const m = line.match(/^([a-z-]+)\s*:\s*(.*)$/i);
        if (!m) continue;
        const k = m[1].toLowerCase(), v = m[2].trim();
        if (k === "user-agent") applies = v === "*";
        else if (applies && k === "disallow" && v && u.pathname.startsWith(v)) ok = false;
        else if (applies && k === "allow" && v && u.pathname.startsWith(v)) ok = true;
      }
      return ok;
    } catch (e) { return true; }
  }

  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const normUrl = (s) => {
    s = s.trim();
    if (!/^https?:\/\//i.test(s)) s = "https://" + s;
    return new URL(s).href;
  };
  const host = (u) => new URL(u).hostname.replace(/^www\./, "");

  // ---------- text helpers ----------
  function docOf(html) { return new DOMParser().parseFromString(html, "text/html"); }
  function visibleText(doc) {
    const c = doc.body ? doc.body.cloneNode(true) : doc.documentElement.cloneNode(true);
    c.querySelectorAll("script,style,noscript,svg").forEach((n) => n.remove());
    return (c.textContent || "").replace(/[–—]/g, "-").replace(/\s+/g, " ").trim();
  }
  function jsonld(doc) {
    const out = [];
    doc.querySelectorAll('script[type="application/ld+json"]').forEach((s) => {
      try {
        const stack = [].concat(JSON.parse(s.textContent));
        while (stack.length) {
          const d = stack.pop();
          if (d && typeof d === "object") { out.push(d); if (Array.isArray(d["@graph"])) stack.push(...d["@graph"]); }
        }
      } catch (e) { /* ignore bad JSON-LD */ }
    });
    return out;
  }
  const isBusiness = (d) => /LocalBusiness|Farm|Store|Restaurant|Organization|FoodEstablishment|Winery|Brewery/.test([].concat(d["@type"] || []).join(" "));

  // ---------- hours (a compact version of scripts/scrape/hours.py) ----------
  const DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"];
  const DAY_RX = "(?:mon(?:day)?|tue(?:s(?:day)?)?|wed(?:s|nesday)?|thu(?:r(?:s(?:day)?)?)?|fri(?:day)?|sat(?:urday)?|sun(?:day)?)";
  const T_RX = "(?:\\d{1,2}(?::\\d{2})?\\s*(?:a\\.?m\\.?|p\\.?m\\.?)?|noon)";
  const RANGE_RX = "(" + T_RX + ")\\s*(?:-|to|until|till)\\s*(" + T_RX + ")";
  const DAYS_RX = DAY_RX + "(?:\\s*(?:-|to|through|thru)\\s*" + DAY_RX + ")?|daily|every\\s*day";
  const HOURS_RE = new RegExp("(" + DAYS_RX + ")\\s*[:,]?\\s*(?:open\\s*)?" + RANGE_RX, "ig");
  function clock(t, borrow) {
    t = t.trim().toLowerCase().replace(/\./g, "");
    if (t === "noon") return "12:00";
    const m = t.match(/^(\d{1,2})(?::(\d{2}))?\s*(am|pm)?$/);
    if (!m) return null;
    let h = +m[1]; const min = m[2] || "00"; const ap = m[3] || borrow;
    if (!ap || h < 1 || h > 12) return null;
    if (ap === "pm" && h < 12) h += 12;
    if (ap === "am" && h === 12) h = 0;
    return String(h).padStart(2, "0") + ":" + min;
  }
  function expandDays(expr) {
    expr = expr.toLowerCase();
    if (/daily|every/.test(expr)) return DAYS.slice();
    const idx = (s) => DAYS.indexOf(s.slice(0, 3));
    const r = expr.split(/\s*(?:-|to|through|thru)\s*/);
    if (r.length === 2) {
      const a = idx(r[0]), b = idx(r[1]); const out = [];
      for (let i = a; ; i = (i + 1) % 7) { out.push(DAYS[i]); if (i === b) break; }
      return out;
    }
    return [DAYS[idx(r[0])]];
  }
  function parseHours(text) {
    const slots = [];
    for (const m of text.matchAll(HOURS_RE)) {
      const ap2 = (m[3].toLowerCase().match(/am|pm/) || [])[0];
      const o = clock(m[2], ap2), c = clock(m[3]);
      if (!o || !c) continue;
      for (const d of expandDays(m[1])) slots.push({ day: d, opens: o, closes: c });
    }
    return slots;
  }
  function findHours(text, ld) {
    for (const d of ld) {
      const spec = d.openingHours;
      if (spec) { const raw = [].concat(spec).join("; "); if (parseHours(raw).length) return { text: raw, slots: parseHours(raw) }; }
    }
    for (const m of text.matchAll(/\bhours\b|open (?:daily|every|mon|tue|wed|thu|fri|sat|sun)/gi)) {
      const snip = text.slice(m.index, m.index + 160);
      if (!parseHours(snip).length) continue;
      let end = 0;
      for (const t of snip.matchAll(new RegExp(RANGE_RX, "ig"))) {
        if (end && t.index - end > 40) break;
        end = t.index + t[0].length;
      }
      const cut = snip.slice(0, end).replace(/^[ ,;:]+|[ ,;:]+$/g, "");
      return { text: cut, slots: parseHours(cut) };
    }
    return { text: "", slots: [] };
  }

  // ---------- derive ----------
  function fmtPhone(m) { return "(" + m[1] + ") " + m[2] + "-" + m[3]; }
  const PHONE_RE = /(?<!\d)\(?(\d{3})\)?[\s.-]?(\d{3})[\s.-](\d{4})(?!\d)/;
  const ADDR_RE = /(\d{1,6}\s+[A-Za-z0-9 .'#-]{3,60}?),?\s+([A-Z][A-Za-z .'-]{2,30}),?\s+(?:Colorado|CO)\.?,?\s+(\d{5})/;

  function emailFrom(doc, html, own) {
    const found = new Set();
    doc.querySelectorAll('a[href^="mailto:"]').forEach((a) => found.add(decodeURIComponent(a.getAttribute("href").slice(7).split("?")[0]).toLowerCase()));
    for (const m of visibleText(doc).matchAll(/[\w.+-]+@[\w-]+(?:\.[\w-]+)+/g)) found.add(m[0].toLowerCase());
    const list = [...found].filter((e) => !/@example\.|^noreply@|\.(png|jpg|gif|webp)$/.test(e));
    const mine = list.find((e) => e.split("@")[1].replace(/^www\./, "") === own);
    return mine || (list.length === 1 ? list[0] : "");
  }

  function socials(doc) {
    const out = {};
    const skip = /\/(?:sharer|share|plugins|tr|dialog|login|p|reel|explore)\b/i;
    doc.querySelectorAll("a[href]").forEach((a) => {
      const h = a.getAttribute("href") || "";
      for (const [k, rx] of [["facebook", /^https?:\/\/(?:www\.)?facebook\.com\/[\w.\-/%]+/i], ["instagram", /^https?:\/\/(?:www\.)?instagram\.com\/[\w.]+\/?/i]]) {
        const m = h.match(rx);
        if (m && !out[k] && !skip.test(m[0]) && m[0].replace(/\/$/, "").split("/").length > 3) out[k] = m[0];
      }
    });
    return out;
  }

  function candidatePages(url, doc) {
    const base = new URL(url), seen = new Set([url.replace(/\/$/, "")]), out = [];
    doc.querySelectorAll("a[href]").forEach((a) => {
      let u;
      try { u = new URL(a.getAttribute("href"), url); } catch (e) { return; }
      if (!/^https?:$/.test(u.protocol) || u.hostname.replace(/^www\./, "") !== base.hostname.replace(/^www\./, "")) return;
      if (/\.(jpe?g|png|gif|pdf|webp|zip)$/i.test(u.pathname)) return;
      u.hash = "";
      const key = u.href.replace(/\/$/, "");
      if (!seen.has(key) && (PAGE_LINK.test(u.pathname) || PAGE_LINK.test(a.textContent))) { seen.add(key); out.push(u.href); }
    });
    return out.slice(0, MAX_PAGES - 1);
  }

  function phraseAround(text, m) {
    const before = text.slice(0, m.index).split(" ").slice(-3), after = text.slice(m.index + m[0].length).split(" ").slice(0, 3);
    let words = before.concat(m[0].split(" "), after);
    if (words.length > 14) words = m[0].split(" ").slice(0, 14);
    return words.join(" ").trim();
  }
  function channelEvidence(text) {
    const out = {};
    for (const [ch, conf, rx] of CHANNEL_RULES) {
      for (const m of text.matchAll(new RegExp(rx.source, "gi"))) {
        const before = text.slice(Math.max(0, m.index - 40), m.index).split(/[.!?]/).pop();
        const after = text.slice(m.index + m[0].length, m.index + m[0].length + 25).split(/[.!?]/)[0];
        if (NEGATION.test(before + " " + after)) continue;
        out[ch] = { confidence: conf, phrase: phraseAround(text, m) };
        break;
      }
    }
    return out;
  }

  async function derive(url, onStatus) {
    onStatus("Checking robots.txt…");
    if (!(await robotsAllows(url))) throw new Error("This site's robots.txt asks automated tools not to read that page, so the demo stops here.");
    onStatus("Reading the home page…");
    const homeHtml = await viaProxy(url);
    const doc = docOf(homeHtml), text = visibleText(doc), ld = jsonld(doc), own = host(url);

    const biz = ld.find((d) => isBusiness(d) && d.name);
    const title = (doc.querySelector("title") || {}).textContent || "";
    const og = (doc.querySelector('meta[property="og:site_name"]') || {}).content;
    const name = (biz && String(biz.name).trim()) || og || title.split(/\s+[|–—-]\s+/)[0].trim() || own;

    let phone = "";
    const bizPhone = ld.find((d) => isBusiness(d) && d.telephone);
    if (bizPhone) { const m = String(bizPhone.telephone).match(PHONE_RE); phone = m ? fmtPhone(m) : String(bizPhone.telephone); }
    if (!phone) {
      const tel = doc.querySelector('a[href^="tel:"]');
      const m = (tel ? decodeURIComponent(tel.getAttribute("href")) : text).match(PHONE_RE);
      phone = m ? fmtPhone(m) : "";
    }

    let address = "";
    const a = ld.map((d) => d.address).find((x) => x && typeof x === "object" && x.streetAddress);
    if (a) address = [a.streetAddress, a.addressLocality, a.addressRegion, a.postalCode].filter(Boolean).join(", ");
    else { const m = text.match(ADDR_RE); if (m) address = m[1].trim() + ", " + m[2].trim() + ", CO " + m[3]; }

    const hours = findHours(text, ld);
    const soc = socials(doc);

    const evidence = {};
    const absorb = (pageUrl, t) => {
      for (const [ch, ev] of Object.entries(channelEvidence(t))) {
        if (!evidence[ch] || (evidence[ch].confidence === "medium" && ev.confidence === "high")) evidence[ch] = { ...ev, page: pageUrl };
      }
    };
    absorb(url, text);
    const pages = candidatePages(url, doc);
    for (let i = 0; i < pages.length; i++) {
      if (OTHERS_PAGE.test(new URL(pages[i]).pathname)) continue;
      onStatus("Reading page " + (i + 2) + " of " + (pages.length + 1) + "…");
      await sleep(DELAY_MS);
      try { absorb(pages[i], visibleText(docOf(await viaProxy(pages[i])))); } catch (e) { /* skip unreadable page */ }
    }

    return {
      name, website: url, phone, email: emailFrom(doc, homeHtml, own), address,
      hours_text: hours.text, hours: hours.slots, facebook: soc.facebook || "", instagram: soc.instagram || "",
      sales_channels: Object.keys(evidence).sort(), channel_evidence: evidence,
      product_groups: PRODUCT_GROUPS.filter(([, rx]) => rx.test(text.toLowerCase())).map(([k]) => k),
      status: "unverified",
    };
  }

  // ---------- diff + snapshots ----------
  const empty = (v) => v === "" || v == null || (Array.isArray(v) && !v.length);
  function diff(oldL, newL) {
    const out = [];
    for (const [f, label] of FIELDS) {
      const a = oldL[f], b = newL[f];
      if (JSON.stringify(a) === JSON.stringify(b)) continue;
      const kind = empty(a) ? "new" : empty(b) ? "gone" : "changed";
      const c = { field: f, label, kind, old: a, new: b };
      if (Array.isArray(a) && Array.isArray(b) && kind === "changed") {
        c.added = b.filter((x) => !a.includes(x)); c.removed = a.filter((x) => !b.includes(x));
      }
      out.push(c);
    }
    return out;
  }
  function load() { try { return JSON.parse(localStorage.getItem(STORE) || "{}"); } catch (e) { return {}; } }
  function save(all) { try { localStorage.setItem(STORE, JSON.stringify(all)); } catch (e) { /* storage unavailable: demo still works, history just isn't kept */ } }

  // ---------- UI ----------
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const show = (v) => (Array.isArray(v) ? v.join(", ") : v) || "—";
  const link = (u) => (u ? `<a href="${esc(u)}" rel="noopener">${esc(u)}</a>` : "—");

  function render(listing, prev, checked) {
    const rows = FIELDS.filter(([f]) => f !== "name").map(([f, label]) => {
      const v = f === "facebook" || f === "instagram" ? link(listing[f]) : esc(show(listing[f]));
      return `<tr><th scope="row">${label}</th><td>${v}</td></tr>`;
    }).join("");
    const ev = Object.entries(listing.channel_evidence).map(([ch, e]) =>
      `<li><b>${esc(ch.replace("_", " "))}</b>: &ldquo;${esc(e.phrase)}&rdquo; <a href="${esc(e.page)}" rel="noopener">source page</a></li>`).join("");
    let changes;
    if (!prev) changes = `<p class="demo-note">First look at this site. A snapshot is saved in this browser; check again later, or use the button below to simulate an update.</p>`;
    else {
      const d = diff(prev.listing, listing);
      changes = `<p class="demo-note">Compared with the snapshot from ${esc(new Date(prev.checked).toLocaleString())}:</p>` +
        (d.length ? "<ul class=\"demo-changes\">" + d.map((c) => {
          const tag = c.kind === "gone" ? "gone — needs review" : c.kind;
          const body = c.added ? `added ${esc(c.added.join(", ") || "nothing")}; removed ${esc(c.removed.join(", ") || "nothing")}`
            : `${esc(show(c.old))} &rarr; ${esc(show(c.new))}`;
          return `<li class="${c.kind}"><b>${esc(c.label)}</b> <span class="demo-tag">${tag}</span><br>${body}</li>`;
        }).join("") + "</ul>" : "<p><b>No listing fields changed.</b></p>");
    }
    $("result").hidden = false;
    $("result").innerHTML = `
      <article class="demo-card">
        <p class="eyebrow">Auto-derived &middot; unverified</p>
        <h2>${esc(listing.name)}</h2>
        <p>${link(listing.website)}</p>
        <table class="demo-table"><tbody>${rows}</tbody></table>
        <h3>Where the sales channels come from</h3>
        <ul>${ev || "<li>No channel evidence found. Unknown never means none.</li>"}</ul>
      </article>
      <section class="demo-card demo-diff"><h3>Changes since last check</h3>${changes}
        <div class="cta"><button class="btn" id="recheck" type="button">Check again</button>
        <button class="btn" id="simulate" type="button">Simulate a site update</button>
        <button class="btn" id="forget" type="button">Forget this site</button></div>
        <p class="demo-small">Simulating edits the saved snapshot (not the website) so the next check shows how a real change would look.</p>
      </section>`;
    const url = listing.website;
    $("recheck").onclick = () => run(url);
    $("forget").onclick = () => { const all = load(); delete all[url]; save(all); $("result").hidden = true; setStatus("Snapshot removed."); };
    $("simulate").onclick = () => {
      const all = load(), s = all[url];
      if (!s) return;
      const l = s.listing;
      l.hours_text = "Sat 9am-12pm";
      l.sales_channels = l.sales_channels.filter((c, i) => i !== 0);
      if (l.phone) l.phone = "(970) 555-0100";
      all[url] = s; save(all);
      setStatus("Snapshot altered. Click “Check again” to see the differences detected.");
    };
  }

  function setStatus(msg, err) { const s = $("status"); s.textContent = msg; s.className = err ? "demo-error" : ""; }

  async function run(raw) {
    let url;
    try { url = normUrl(raw); } catch (e) { return setStatus("That doesn't look like a web address.", true); }
    $("go").disabled = true;
    try {
      const listing = await derive(url, setStatus);
      const all = load(), prev = all[url] || null;
      const checked = Date.now();
      render(listing, prev, checked);
      all[url] = { listing, checked };
      save(all);
      setStatus("Done.");
    } catch (e) {
      const msg = e && e.message ? e.message : String(e);
      setStatus(e && e.final ? msg : "Couldn't read that site: " + msg + " The proxy may be busy; try again in a moment.", true);
    } finally { $("go").disabled = false; }
  }

  document.addEventListener("DOMContentLoaded", () => {
    $("form").addEventListener("submit", (e) => { e.preventDefault(); const v = $("url").value; if (v.trim()) run(v); });
    document.querySelectorAll("[data-example]").forEach((b) => b.addEventListener("click", () => { $("url").value = b.dataset.example; run(b.dataset.example); }));
  });

  // exposed for tests / console experiments
  window.FoodWebDemo = { parseHours, channelEvidence, diff };
})();
