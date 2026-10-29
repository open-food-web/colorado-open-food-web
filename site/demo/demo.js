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
    const t0 = Date.now(), pagesRead = [], fieldSources = [];
    onStatus("Checking robots.txt…");
    if (!(await robotsAllows(url))) throw new Error("This site's robots.txt asks automated tools not to read that page, so the demo stops here.");
    onStatus("Reading the home page…");
    const homeHtml = await viaProxy(url);
    pagesRead.push(url);
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

    let address = "", town = "", addrParts = {};
    const a = ld.map((d) => d.address).find((x) => x && typeof x === "object" && x.streetAddress);
    if (a) { address = [a.streetAddress, a.addressLocality, a.addressRegion, a.postalCode].filter(Boolean).join(", "); town = a.addressLocality || ""; addrParts = { street: a.streetAddress, zip: a.postalCode }; }
    else { const m = text.match(ADDR_RE); if (m) { address = m[1].trim() + ", " + m[2].trim() + ", CO " + m[3]; town = m[2].trim(); addrParts = { street: m[1].trim(), zip: m[3] }; } }

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
      try { absorb(pages[i], visibleText(docOf(await viaProxy(pages[i])))); pagesRead.push(pages[i]); } catch (e) { /* skip unreadable page */ }
    }
    const lower = (name + " " + text).toLowerCase();
    const kind = /winery|vineyard/.test(lower) ? "winery" : /orchard/.test(lower) ? "orchard" : /ranch/.test(lower) ? "ranch" : /farm/.test(lower) ? "farm" : "";
    const email = emailFrom(doc, homeHtml, own);
    const from = (field, value, method, page) => { if (!(value === "" || (Array.isArray(value) && !value.length))) fieldSources.push({ field, source_url: page || url, method }); };
    from("name", name, biz ? "json-ld" : og ? "og:site_name" : "page title");
    from("phone", phone, bizPhone ? "json-ld" : "tel link or page text");
    from("email", email, "printed on the business's own page");
    from("address", address, a ? "json-ld" : "page text pattern");
    from("hours_text", hours.text, "page text, parsed with the hours parser");
    from("facebook", soc.facebook, "link on page"); from("instagram", soc.instagram, "link on page");
    for (const [ch, ev] of Object.entries(evidence)) fieldSources.push({ field: "sales_channels:" + ch, source_url: ev.page, method: "phrase match (" + ev.confidence + ")" });
    const textHash = Array.from(new TextEncoder().encode(text)).reduce((h, b) => ((h * 31 + b) >>> 0), 7).toString(16);

    return {
      name, website: url, phone, email, address, town, address_parts: addrParts, kind,
      hours_text: hours.text, hours: hours.slots, hours_status: hours.slots.length ? "parsed" : (hours.text ? "text_only" : "none"), facebook: soc.facebook || "", instagram: soc.instagram || "",
      sales_channels: Object.keys(evidence).sort(), channel_evidence: evidence,
      product_groups: PRODUCT_GROUPS.filter(([, rx]) => rx.test(text.toLowerCase())).map(([k]) => k),
      status: "unverified",
      _derive: { pages_read: pagesRead, field_sources: fieldSources, elapsed_ms: Date.now() - t0, text_hash: textHash },
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

  const LABELS = {
    "veggies": "Veggies", "fruit": "Fruit", "beef-meat": "Beef & meat", "poultry-eggs": "Poultry & eggs", "dairy": "Dairy",
    "honey": "Honey", "flowers": "Flowers", "garlic-herbs": "Garlic & herbs", "mushrooms": "Mushrooms",
    "baked-goods": "Baked goods", "seeds-plants": "Seeds & plants", "drinks": "Wine & drinks",
  };
  const KIND_LABEL = { farm: "Farm", ranch: "Ranch", orchard: "Orchard", winery: "Winery", maker: "Maker" };
  const mapsLink = (l) => "https://www.google.com/maps/search/?api=1&query=" + encodeURIComponent([l.name, l.address].filter(Boolean).join(", "));
  const fmtDate = (ms) => new Date(ms).toLocaleDateString(undefined, { year: "numeric", month: "long", day: "numeric" });
  const hostOf = (u) => { try { return new URL(u).hostname.replace(/^www\./, ""); } catch (e) { return u; } };

  // ----- the end product: a producer listing page in the style of Chaffee Provides -----
  function listingPage(l, checked) {
    const site = l.website ? `<a href="${esc(l.website)}" rel="noopener">${esc(hostOf(l.website))}</a>` : "";
    const src = (ch) => (l.channel_evidence[ch] ? ` <span class="cp-muted">·</span> <a href="${esc(l.channel_evidence[ch].page)}" rel="noopener">Where they say so</a>` : "");
    const has = (ch) => l.sales_channels.includes(ch);
    const dir = l.address ? ` <span class="cp-muted">·</span> <a href="${esc(mapsLink(l))}" target="_blank" rel="noopener">Directions</a>` : "";
    const ways = [];
    const add = (title, html) => ways.push(`<li><strong>${esc(title)}</strong><div>${html}</div></li>`);
    if (has("farm_stand")) add("Visit the farm stand", (l.address ? esc(l.address) : "Ask them for the address.") + (l.hours_text ? ` <span class="cp-muted">· ${esc(l.hours_text)}</span>` : "") + dir + src("farm_stand"));
    if (has("u_pick")) add("Pick your own", esc(l.hours_text || "Ask them when you can come pick.") + src("u_pick"));
    if (has("csa")) add("Join their CSA", "A weekly share of the harvest. " + (site ? `Sign up on ${site}.` : "Contact them to sign up.") + src("csa"));
    if (has("farmers_market")) add("At the farmers market", "They sell at local farmers markets. Check their website for the schedule." + src("farmers_market"));
    if (has("online")) add("Order online", (site ? `Order at ${site}.` : "Order online.") + src("online"));
    if (has("pickup")) add("Pick up an order", "They offer order pickup. Ask them where and when." + src("pickup"));
    if (has("delivery")) add("Delivery", "They deliver. Ask them about their delivery area." + src("delivery"));
    if (has("wholesale")) add("Wholesale", (l.sales_channels.length === 1 ? "They sell to restaurants and stores, not to the public." : "They also sell wholesale to restaurants and stores.") + src("wholesale"));
    if (!ways.length) add("How to buy", "We haven't confirmed how to buy from them yet. " + (l.phone ? `Call <a href="tel:${esc(l.phone.replace(/[^0-9+]/g, ""))}">${esc(l.phone)}</a>. ` : "") + (site ? `Or see ${site}.` : ""));

    const chips = l.product_groups.map((g) => `<span class="cp-chip">${esc(LABELS[g] || g)}</span>`).join(" ");
    const fact = (label, html) => (html ? `<div class="cp-fact"><span class="cp-ic">${label}</span><div>${html}</div></div>` : "");
    const social = [l.facebook && `<a href="${esc(l.facebook)}" rel="noopener">Facebook</a>`, l.instagram && `<a href="${esc(l.instagram)}" rel="noopener">Instagram</a>`].filter(Boolean).join(" · ");
    const facts = fact("Phone", l.phone && `<a href="tel:${esc(l.phone.replace(/[^0-9+]/g, ""))}">${esc(l.phone)}</a>`)
      + fact("Email", l.email && `<a href="mailto:${esc(l.email)}">${esc(l.email)}</a>`)
      + fact("Website", site) + fact("Social", social)
      + fact("Hours", !has("farm_stand") && esc(l.hours_text || ""));
    return `<div class="cp">
      <p class="cp-crumbs">Directory › ${esc(l.name)}</p>
      <h1>${esc(l.name)}</h1>
      <div><span class="cp-tag">${esc(KIND_LABEL[l.kind] || "Producer")}</span>${l.town ? ` <span class="cp-muted">· Based in ${esc(l.town)}</span>` : ""}</div>
      <p><span class="cp-pill warn">Auto-derived, not yet checked by a person</span></p>
      <h2>Places to find them</h2>
      <ul class="cp-ways">${ways.join("")}</ul>
      ${chips ? `<h2>What they offer</h2><div class="cp-chips">${chips}</div>` : ""}
      <div class="cp-facts">${facts}</div>
      <p class="cp-faint"><i>Data last checked ${esc(fmtDate(checked))}</i></p>
      <p class="cp-actions"><button class="cp-btn" type="button" disabled title="Not active in the demo">Suggest an update</button>
        <button class="cp-btn" type="button" disabled title="Not active in the demo">Remove this listing</button></p>
    </div>`;
  }

  // ----- the raw data: the record as the schema would hold it, with where each value came from -----
  function rawRecord(l, checked, d) {
    const iso = new Date(checked).toISOString();
    const slug = (l.name || "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
    const addr = l.address_parts || {};
    return {
      generated_by: "Colorado Open Food Web listing demo (prototype)",
      checked_at: iso,
      read: { url: l.website, pages_read: d.pages_read, via: OWN_PROXY ? "foodweb-demo-proxy (robots.txt checked, ColoradoOpenFoodWeb user agent)" : "public CORS proxy", elapsed_ms: d.elapsed_ms, page_text_hash: d.text_hash },
      tables: {
        producers: [{
          producer_id: null, slug, name: l.name, kind: l.kind || "", categories: [], products: [], product_groups: l.product_groups,
          website: l.website, phone: l.phone, email: l.email, facebook: l.facebook, instagram: l.instagram,
          sales_channels: l.sales_channels, hours_text: l.hours_text, hours_status: l.hours_status,
          status: "unverified", claimed: false, first_seen: iso.slice(0, 10), last_verified: "",
        }],
        locations: l.address ? [{ location_id: null, address: addr.street || l.address, city: l.town || "", state: "CO", postal_code: addr.zip || "", lat: null, lng: null, county_fips: null }] : [],
        hours: l.hours.map((h) => ({ record_type: "producer", record_id: null, day: h.day, opens: h.opens, closes: h.closes, closes_next_day: false, inferred: false })),
        field_sources: d.field_sources.map((s) => ({ record_type: "producer", record_id: null, ...s, retrieved: iso.slice(0, 10) })),
      },
      channel_evidence: l.channel_evidence,
      not_derived: ["producer_id", "categories", "products", "lat/lng", "county_fips", "certified_organic", "accepts_snap", "visits", "seasonal_months"],
      notes: ["kind is guessed from the name and page text", "empty means not found on the page, never 'none'", "hours rows are only what the text states"],
      changes_since_last_check: d.changes,
    };
  }

  function render(listing, prev, checked, d) {
    let changes = [], changesHtml;
    if (!prev) changesHtml = `<p class="demo-note">First look at this site. A snapshot is saved in this browser; check again later, or use the button below to simulate an update.</p>`;
    else {
      changes = diff(prev.listing, listing);
      changesHtml = `<p class="demo-note">Compared with the snapshot from ${esc(new Date(prev.checked).toLocaleString())}:</p>` +
        (changes.length ? "<ul class=\"demo-changes\">" + changes.map((c) => {
          const tag = c.kind === "gone" ? "gone — needs review" : c.kind;
          const body = c.added ? `added ${esc(c.added.join(", ") || "nothing")}; removed ${esc(c.removed.join(", ") || "nothing")}`
            : `${esc(show(c.old))} &rarr; ${esc(show(c.new))}`;
          return `<li class="${c.kind}"><b>${esc(c.label)}</b> <span class="demo-tag">${tag}</span><br>${body}</li>`;
        }).join("") + "</ul>" : "<p><b>No listing fields changed.</b></p>");
    }
    d.changes = changes;
    const json = JSON.stringify(rawRecord(listing, checked, d), null, 2);
    $("result").hidden = false;
    $("result").innerHTML = `
      <div class="demo-tabs" role="tablist" aria-label="Output">
        <button role="tab" id="tab-page" aria-selected="true" aria-controls="pane-page" type="button">Listing page</button>
        <button role="tab" id="tab-raw" aria-selected="false" aria-controls="pane-raw" type="button">Raw data</button>
      </div>
      <div id="pane-page" role="tabpanel" aria-labelledby="tab-page">${listingPage(listing, checked)}</div>
      <div id="pane-raw" role="tabpanel" aria-labelledby="tab-raw" hidden>
        <div class="demo-card">
          <p class="demo-note">The same result as rows for the schema tables (<code>producers</code>, <code>locations</code>, <code>hours</code>, <code>field_sources</code>), plus the evidence behind each value. Fields the demo can't derive are listed under <code>not_derived</code>.</p>
          <div class="cta"><button class="btn" id="copy-json" type="button">Copy JSON</button><button class="btn" id="dl-json" type="button">Download JSON</button></div>
          <pre class="demo-json" tabindex="0">${esc(json)}</pre>
        </div>
      </div>
      <section class="demo-card demo-diff"><h3>Changes since last check</h3>${changesHtml}
        <div class="cta"><button class="btn" id="recheck" type="button">Check again</button>
        <button class="btn" id="simulate" type="button">Simulate a site update</button>
        <button class="btn" id="forget" type="button">Forget this site</button></div>
        <p class="demo-small">Simulating edits the saved snapshot (not the website) so the next check shows how a real change would look.</p>
      </section>`;
    const pick = (which) => {
      for (const k of ["page", "raw"]) { $("tab-" + k).setAttribute("aria-selected", String(k === which)); $("pane-" + k).hidden = k !== which; }
    };
    $("tab-page").onclick = () => pick("page");
    $("tab-raw").onclick = () => pick("raw");
    $("copy-json").onclick = async () => { try { await navigator.clipboard.writeText(json); $("copy-json").textContent = "Copied"; } catch (e) { $("copy-json").textContent = "Copy failed"; } };
    $("dl-json").onclick = () => {
      const a = document.createElement("a");
      a.href = URL.createObjectURL(new Blob([json], { type: "application/json" }));
      a.download = hostOf(listing.website) + "-listing.json"; a.click(); URL.revokeObjectURL(a.href);
    };
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
      const d = listing._derive; delete listing._derive;
      const all = load(), prev = all[url] || null;
      const checked = Date.now();
      render(listing, prev, checked, d);
      all[url] = { listing, checked };
      save(all);
      setStatus("Done.");
    } catch (e) {
      const msg = e && e.message ? e.message : String(e);
      setStatus(e && e.final ? msg : "Couldn't read that site: " + msg + " The proxy may be busy; try again in a moment.", true);
    } finally { $("go").disabled = false; }
  }

  document.addEventListener("DOMContentLoaded", () => {
    if (!$("form")) return;     // loaded by another demo page for its parsers only
    $("form").addEventListener("submit", (e) => { e.preventDefault(); const v = $("url").value; if (v.trim()) run(v); });
    document.querySelectorAll("[data-example]").forEach((b) => b.addEventListener("click", () => { $("url").value = b.dataset.example; run(b.dataset.example); }));
  });

  // exposed for tests / console experiments
  window.FoodWebDemo = { parseHours, channelEvidence, diff };
})();
