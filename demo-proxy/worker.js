// Fetch proxy for the listing demo (site/demo/). Runs on Cloudflare Workers.
//
//   GET /?url=https://examplefarm.com/        -> that page's HTML, with CORS headers
//
// Why it exists: the demo is a static GitHub Pages site, and browsers cannot read other sites directly.
// What it does, and refuses to do:
//   - identifies itself with the project user agent (same as scripts/scrape/useragent.py)
//   - reads robots.txt and refuses pages it disallows (403, body "robots-disallowed")
//   - only http/https, only public hostnames, only text/HTML responses, at most 1 MB, 10 s
//   - only answers requests from the project's own pages (ALLOWED_ORIGINS), not the open web
//   - a per-IP limit (RATE_LIMIT per minute) in memory; best effort, resets when the Worker restarts
const USER_AGENT = "Mozilla/5.0 (compatible; ColoradoOpenFoodWeb/0.1; +https://github.com/open-food-web/colorado-open-food-web)";
const ROBOTS_TOKEN = "coloradoopenfoodweb";
const ALLOWED_ORIGINS = [
  "https://open-food-web.github.io",
  "http://localhost:8791",
  "http://localhost:8000",
  "http://127.0.0.1:8000",
];
const MAX_BYTES = 1_000_000;
const TIMEOUT_MS = 10_000;
const RATE_LIMIT = 30;

const hits = new Map(); // ip -> [timestamps]

function cors(origin) {
  return {
    "Access-Control-Allow-Origin": origin,
    "Access-Control-Allow-Methods": "GET, OPTIONS",
    "Vary": "Origin",
  };
}

function reply(status, body, origin, extra = {}) {
  return new Response(body, { status, headers: { ...cors(origin), "Content-Type": "text/plain; charset=utf-8", ...extra } });
}

function isPublicHost(host) {
  host = host.toLowerCase();
  if (host === "localhost" || host.endsWith(".local") || host.endsWith(".internal") || !host.includes(".")) return false;
  if (/^\[/.test(host) || host.includes(":")) return false;                      // IPv6 literals
  const m = host.match(/^(\d+)\.(\d+)\.(\d+)\.(\d+)$/);
  if (m) {
    const [a, b] = [+m[1], +m[2]];
    if (a === 10 || a === 127 || a === 0 || (a === 169 && b === 254) || (a === 172 && b >= 16 && b <= 31) || (a === 192 && b === 168)) return false;
  }
  return true;
}

// A simplified reading of robots.txt: the group for our token if there is one, else "*".
// Longest matching rule wins; Allow beats Disallow on a tie. No readable robots.txt means allowed.
export function robotsAllows(robotsTxt, path) {
  const groups = [];
  let cur = null, lastWasAgent = false;
  for (const raw of robotsTxt.split(/\r?\n/)) {
    const line = raw.split("#")[0].trim();
    const m = line.match(/^([A-Za-z-]+)\s*:\s*(.*)$/);
    if (!m) continue;
    const k = m[1].toLowerCase(), v = m[2].trim();
    if (k === "user-agent") {
      if (!lastWasAgent) { cur = { agents: [], rules: [] }; groups.push(cur); }
      cur.agents.push(v.toLowerCase());
      lastWasAgent = true;
    } else if (cur && (k === "allow" || k === "disallow")) {
      cur.rules.push([k, v]);
      lastWasAgent = false;
    } else lastWasAgent = false;
  }
  const group = groups.find((g) => g.agents.some((a) => a !== "*" && ROBOTS_TOKEN.includes(a.replace(/\s/g, "")))) ||
                groups.find((g) => g.agents.includes("*"));
  if (!group) return true;
  let best = { len: -1, allow: true };
  for (const [k, v] of group.rules) {
    if (!v) { continue; }                                                         // "Disallow:" with nothing allows everything
    const rx = new RegExp("^" + v.replace(/[.+?^${}()|[\]\\]/g, "\\$&").replace(/\*/g, ".*").replace(/\\\$$/, "$"));
    if (rx.test(path) && (v.length > best.len || (v.length === best.len && k === "allow"))) best = { len: v.length, allow: k === "allow" };
  }
  return best.allow;
}

async function get(url, accept) {
  const ctl = new AbortController();
  const timer = setTimeout(() => ctl.abort(), TIMEOUT_MS);
  try {
    return await fetch(url, { headers: { "User-Agent": USER_AGENT, "Accept": accept }, signal: ctl.signal, redirect: "follow" });
  } finally { clearTimeout(timer); }
}

export default {
  async fetch(request) {
    const origin = request.headers.get("Origin") || "";
    const allowed = ALLOWED_ORIGINS.includes(origin);
    const o = allowed ? origin : ALLOWED_ORIGINS[0];
    if (request.method === "OPTIONS") return new Response(null, { status: 204, headers: cors(o) });
    if (request.method !== "GET") return reply(405, "method-not-allowed", o);
    if (!allowed) return reply(403, "origin-not-allowed", o);

    const ip = request.headers.get("CF-Connecting-IP") || "unknown";
    const now = Date.now();
    const recent = (hits.get(ip) || []).filter((t) => now - t < 60_000);
    if (recent.length >= RATE_LIMIT) return reply(429, "rate-limited", o);
    recent.push(now);
    hits.set(ip, recent);

    let target;
    try { target = new URL(new URL(request.url).searchParams.get("url") || ""); } catch (e) { return reply(400, "bad-url", o); }
    if (!/^https?:$/.test(target.protocol) || !isPublicHost(target.hostname)) return reply(400, "url-not-allowed", o);

    try {
      if (target.pathname !== "/robots.txt") {
        const r = await get(target.origin + "/robots.txt", "text/plain");
        if (r.ok) {
          const txt = (await r.text()).slice(0, 200_000);
          if (!robotsAllows(txt, target.pathname + target.search)) return reply(403, "robots-disallowed", o);
        }
      }
      const res = await get(target.href, "text/html,text/plain,*/*");
      const finalHost = new URL(res.url).hostname;
      if (!isPublicHost(finalHost)) return reply(400, "url-not-allowed", o);
      const type = res.headers.get("Content-Type") || "";
      if (type && !/html|text/i.test(type)) return reply(415, "not-a-web-page", o);
      const buf = await res.arrayBuffer();
      if (buf.byteLength > MAX_BYTES) return reply(413, "too-large", o);
      return new Response(buf, {
        status: res.status,
        headers: { ...cors(o), "Content-Type": type || "text/html; charset=utf-8", "Cache-Control": "public, max-age=300" },
      });
    } catch (e) {
      return reply(502, "fetch-failed", o);
    }
  },
};
