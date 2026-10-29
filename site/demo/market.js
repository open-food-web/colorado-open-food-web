// Demo: a farmers market's website changes its hours and dates, and the Food Web notices on its own.
// The market and its website are made up for the demo. The "website" is a real HTML page served from the
// browser (a blob URL); the watcher fetches it every few seconds, reads the hours, season and location
// with the same parsers the listing demo uses, and compares what it finds with the last check.
// Detected changes wait for a person to approve them, like a pipeline PR, before the listing changes.
(function () {
  "use strict";
  const POLL_MS = 5000;
  const MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"];
  const MONTH_RX = "(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\\.?";
  const DEFAULT = {
    name: "Sample Valley Farmers Market",
    hours: "Saturdays 8am-12pm",
    season: "Season: May 2 - October 24, 2026",
    place: "Riverside Park, 100 Main St, Salida, CO 81201",
    notice: "",
  };
  const PRESETS = [
    ["Winter hours", { hours: "Saturdays 10am-1pm", season: "Season: November 14 - December 19, 2026" }],
    ["Add a Wednesday evening market", { hours: "Saturdays 8am-12pm; Wednesdays 4pm-7pm" }],
    ["Extend the season", { season: "Season: May 2 - November 7, 2026" }],
    ["Move to a new location", { place: "Alpine Park, 404 E Street, Salida, CO 81201" }],
    ["Cancel one Saturday", { notice: "No market on October 10 due to weather." }],
  ];

  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const D = () => window.FoodWebDemo;
  const DAY_LABEL = { mon: "Mon", tue: "Tue", wed: "Wed", thu: "Thu", fri: "Fri", sat: "Sat", sun: "Sun" };
  const ORDER = Object.keys(DAY_LABEL);

  let site = { ...DEFAULT };       // what the market has published
  let siteUrl = null;              // blob URL of the current page
  let baseline = null;             // last approved reading (the published listing)
  let lastSeen = null;             // reading at the most recent check
  let pending = [];                // detected changes waiting for review
  let events = [];                 // timeline
  let approvedAt = "", timer = null, countdown = POLL_MS / 1000, checks = 0, auto = true;

  // ----- the simulated website -----
  function siteHtml(s) {
    return `<!doctype html><html lang="en"><head><meta charset="utf-8"><title>${esc(s.name)}</title>
<style>body{font:16px/1.6 Georgia,serif;max-width:560px;margin:0 auto;padding:20px;color:#2a2a2a}h1{font-size:1.6rem;margin:.2em 0}
.bar{background:#7a4fa3;color:#fff;padding:8px 12px;font:600 14px system-ui}.n{background:#fff3cd;padding:8px 12px;border-left:4px solid #c9892b}</style></head>
<body><div class="bar">${esc(s.name)}</div><h1>Welcome to the market</h1>
<p>Fresh produce, meat, eggs, bread and flowers from local growers.</p>
<h2>When and where</h2><p>Open ${esc(s.hours)}</p><p>${esc(s.season)}</p><p>Find us at ${esc(s.place)}</p>
${s.notice ? `<p class="n">${esc(s.notice)}</p>` : ""}
<p>Vendors: apply by emailing the market manager.</p></body></html>`;
  }
  function publish() {
    if (siteUrl) URL.revokeObjectURL(siteUrl);
    siteUrl = URL.createObjectURL(new Blob([siteHtml(site)], { type: "text/html" }));
    $("site-frame").src = siteUrl;
  }

  // ----- reading a market page -----
  function readPage(html) {
    const doc = new DOMParser().parseFromString(html, "text/html");
    doc.querySelectorAll("script,style").forEach((n) => n.remove());
    let text = (doc.body.textContent || "").replace(/[–—]/g, "-").replace(/\s+/g, " ").trim();
    text = text.replace(/\b(mon|tues|wednes|thurs|fri|satur|sun)days?\b/gi, "$1day");
    const slots = D().parseHours(text);
    const hoursText = (text.match(/Open\s+(.+?)(?=\s+Season|\s+Find us|$)/i) || [, ""])[1].trim();
    const sm = text.match(new RegExp(MONTH_RX + "\\s+(\\d{1,2})(?:st|nd|rd|th)?\\s*(?:-|to|through)\\s*(?:" + MONTH_RX + "\\s+)?(\\d{1,2})(?:st|nd|rd|th)?,?\\s*(\\d{4})?", "i"));
    const yr = sm && sm[6] ? +sm[6] : new Date().getFullYear();
    const mi = (m) => MONTHS.indexOf(m.slice(0, 3).toLowerCase()) + 1;
    const iso = (m, d) => `${yr}-${String(m).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
    const season = sm ? { start: iso(mi(sm[1]), +sm[2]), end: iso(mi(sm[3] || sm[1]), +sm[4]) } : { start: "", end: "" };
    const place = (text.match(/Find us at\s+(.+?)(?=\s+(?:No market|Vendors|Closed)|$)/i) || [, ""])[1].replace(/\.$/, "").trim();
    const closures = [];
    for (const m of text.matchAll(new RegExp("(?:no market|closed|cancel(?:l)?ed)[^.]{0,30}?on\\s+" + MONTH_RX + "\\s+(\\d{1,2})", "gi"))) closures.push(iso(mi(m[1]), +m[2]));
    const byDay = {};
    for (const s of slots) (byDay[s.day] = byDay[s.day] || []).push(s.opens + "-" + s.closes);
    return { hours: ORDER.filter((d) => byDay[d]).map((d) => ({ day: d, times: byDay[d].join(", ") })), hours_text: hoursText, season_start: season.start, season_end: season.end, address: place, closures };
  }
  const t12 = (t) => { const [h, m] = t.split(":").map(Number); return ((h % 12) || 12) + (m ? ":" + String(m).padStart(2, "0") : "") + (h < 12 ? "am" : "pm"); };
  const nice = (times) => times.split(", ").map((r) => r.split("-").map(t12).join(" - ")).join(", ");
  const fmtHours = (h) => (h.length ? h.map((x) => DAY_LABEL[x.day] + " " + nice(x.times)).join("; ") : "none found");
  const fmtDate = (iso) => (iso ? new Date(iso + "T12:00:00").toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" }) : "—");

  function compare(a, b) {
    const out = [];
    const ah = fmtHours(a.hours), bh = fmtHours(b.hours);
    if (ah !== bh) out.push({ field: "Hours", old: ah, new: bh });
    if (a.season_start !== b.season_start) out.push({ field: "Season opens", old: fmtDate(a.season_start), new: fmtDate(b.season_start) });
    if (a.season_end !== b.season_end) out.push({ field: "Season closes", old: fmtDate(a.season_end), new: fmtDate(b.season_end) });
    if (a.address !== b.address) out.push({ field: "Location", old: a.address || "—", new: b.address || "—" });
    const ac = a.closures.join(","), bc = b.closures.join(",");
    if (ac !== bc) out.push({ field: "Closed dates", old: a.closures.map(fmtDate).join(", ") || "none", new: b.closures.map(fmtDate).join(", ") || "none" });
    return out;
  }

  // ----- the watcher -----
  const stamp = () => new Date().toLocaleTimeString();
  function log(kind, msg) { events.unshift({ kind, msg, at: stamp() }); events = events.slice(0, 40); drawTimeline(); }

  async function check(manual) {
    $("next").textContent = "Checking the website…";
    let html;
    try { html = await (await fetch(siteUrl, { cache: "no-store" })).text(); } catch (e) { return log("warn", "Couldn't read the website."); }
    checks++;
    const now = readPage(html);
    if (!baseline) {
      baseline = now; lastSeen = now; approvedAt = stamp();
      log("info", "First look at the website. Listing created from it.");
      drawListing(); drawPending(); return;
    }
    const changes = compare(lastSeen, now);
    lastSeen = now;
    if (!changes.length) { log("quiet", manual ? "Checked now: nothing changed." : "Checked: nothing changed."); drawStatus(); return; }
    // Compare to what is published, so a change that was undone before review disappears from the queue.
    pending = compare(baseline, now).map((c) => ({ ...c, detected: stamp() }));
    log("change", "Change detected: " + changes.map((c) => c.field).join(", ") + ". Waiting for review.");
    drawPending(); drawListing(); drawStatus();
  }

  function approve() {
    if (!lastSeen) return;
    baseline = lastSeen; pending = []; approvedAt = stamp();
    log("ok", "A person approved the changes. The listing now matches the website.");
    drawPending(); drawListing();
  }
  function dismiss() {
    pending = [];
    log("warn", "A person dismissed the changes. The listing stays as it was.");
    drawPending(); drawListing();
  }

  function schedule() {
    clearInterval(timer);
    countdown = POLL_MS / 1000;
    drawStatus();
    if (!auto) return;
    timer = setInterval(() => {
      countdown -= 1;
      if (countdown <= 0) { countdown = POLL_MS / 1000; check(false); } else drawStatus();
    }, 1000);
  }

  // ----- drawing -----
  function drawStatus() {
    $("next").textContent = auto ? `Next automatic check in ${countdown}s` : "Automatic checks paused";
    $("checks").textContent = `${checks} check${checks === 1 ? "" : "s"} so far`;
    $("toggle").textContent = auto ? "Pause watching" : "Resume watching";
  }
  function drawTimeline() {
    $("timeline").innerHTML = events.length ? events.map((e) => `<li class="ev-${e.kind}"><span class="ev-at">${esc(e.at)}</span> ${esc(e.msg)}</li>`).join("") : "<li class=\"ev-quiet\">Nothing yet.</li>";
  }
  function drawPending() {
    const box = $("pending");
    if (!pending.length) { box.innerHTML = `<p class="demo-note">No changes waiting for review. The listing matches the website.</p>`; return; }
    box.innerHTML = `<p><span class="cp-pill warn">${pending.length} change${pending.length === 1 ? "" : "s"} waiting for review</span></p>`
      + `<ul class="demo-changes">${pending.map((c) => `<li class="changed"><b>${esc(c.field)}</b> <span class="demo-tag">detected ${esc(c.detected)}</span><br>${esc(c.old)} &rarr; ${esc(c.new)}</li>`).join("")}</ul>`
      + `<div class="cta"><button class="btn" id="approve" type="button">Approve changes</button><button class="btn" id="dismiss" type="button">Dismiss</button></div>`;
    $("approve").onclick = approve; $("dismiss").onclick = dismiss;
  }
  function drawListing() {
    if (!baseline) return;
    const b = baseline, changed = new Set(pending.map((c) => c.field));
    const days = b.hours.length ? b.hours.map((h) => `<li>${DAY_LABEL[h.day]} <span class="cp-muted">${esc(nice(h.times))}</span></li>`).join("") : `<li class="cp-muted">${esc(b.hours_text || "Hours not found")}</li>`;
    const flag = (f) => (changed.has(f) ? ` <span class="cp-pill warn">website now differs</span>` : "");
    $("listing").innerHTML = `<div class="cp">
      <p class="cp-crumbs">Directory › ${esc(site.name)}</p><h1>${esc(site.name)}</h1>
      <div><span class="cp-tag" style="color:#7a4fa3">Farmers market</span></div>
      <p><span class="cp-pill">Made-up market for the demo</span></p>
      <h2>When</h2><ul class="cp-ways cp-hours">${days}</ul>${flag("Hours")}
      <h2>Season</h2><p>${b.season_start ? esc(fmtDate(b.season_start)) + " to " + esc(fmtDate(b.season_end)) : "Not found"}${flag("Season opens")}${flag("Season closes")}</p>
      ${b.closures.length ? `<p><strong>No market:</strong> ${b.closures.map((c) => esc(fmtDate(c))).join(", ")}${flag("Closed dates")}</p>` : ""}
      <h2>Where</h2><p>${esc(b.address || "Not found")}${b.address ? ` <span class="cp-muted">·</span> <a href="https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(b.address)}" target="_blank" rel="noopener">Directions</a>` : ""}${flag("Location")}</p>
      <p class="cp-faint"><i>Data last approved ${esc(approvedAt)}</i></p></div>`;
  }

  // ----- the editor -----
  function readForm() { return { name: DEFAULT.name, hours: $("f-hours").value, season: $("f-season").value, place: $("f-place").value, notice: $("f-notice").value }; }
  function fillForm(s) { $("f-hours").value = s.hours; $("f-season").value = s.season; $("f-place").value = s.place; $("f-notice").value = s.notice; }

  document.addEventListener("DOMContentLoaded", () => {
    fillForm(site);
    publish();
    $("presets").innerHTML = PRESETS.map((p, i) => `<button class="btn" type="button" data-p="${i}">${esc(p[0])}</button>`).join("") + `<button class="btn" type="button" id="reset">Reset the website</button>`;
    $("presets").onclick = (e) => {
      const b = e.target.closest("button"); if (!b) return;
      site = b.id === "reset" ? { ...DEFAULT } : { ...site, ...PRESETS[+b.dataset.p][1] };
      fillForm(site); publish(); $("published").textContent = "Website updated at " + stamp() + ". The watcher will notice on its next check.";
    };
    $("editor").onsubmit = (e) => { e.preventDefault(); site = readForm(); publish(); $("published").textContent = "Website updated at " + stamp() + ". The watcher will notice on its next check."; };
    $("toggle").onclick = () => { auto = !auto; schedule(); };
    $("now").onclick = () => { check(true); countdown = POLL_MS / 1000; };
    drawTimeline(); drawPending();
    // read the first version as soon as the page has loaded, then every few seconds
    $("site-frame").addEventListener("load", () => { if (!baseline) check(false); }, { once: true });
    schedule();
  });
})();
