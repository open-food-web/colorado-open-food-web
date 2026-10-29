import test from "node:test";
import assert from "node:assert/strict";
import worker, { robotsAllows } from "./worker.js";

test("robots: wildcard disallow and allow override", () => {
  const txt = "User-agent: *\nDisallow: /private\nAllow: /private/ok\n";
  assert.equal(robotsAllows(txt, "/"), true);
  assert.equal(robotsAllows(txt, "/private/x"), false);
  assert.equal(robotsAllows(txt, "/private/ok/page"), true);
});

test("robots: empty Disallow allows everything; no robots allows", () => {
  assert.equal(robotsAllows("User-agent: *\nDisallow:\n", "/a"), true);
  assert.equal(robotsAllows("", "/a"), true);
});

test("robots: our own group wins over *", () => {
  const txt = "User-agent: *\nDisallow: /\n\nUser-agent: ColoradoOpenFoodWeb\nAllow: /\n";
  assert.equal(robotsAllows(txt, "/farm"), true);
  assert.equal(robotsAllows("User-agent: *\nDisallow: /\n", "/farm"), false);
});

const OK = "https://open-food-web.github.io";
const call = (qs, origin = OK) => worker.fetch(new Request("https://p.example/?url=" + encodeURIComponent(qs), { headers: { Origin: origin } }));

test("refuses unknown origins, private hosts and non-http", async () => {
  assert.equal((await call("https://example.com/", "https://evil.example")).status, 403);
  assert.equal((await call("http://localhost/")).status, 400);
  assert.equal((await call("http://192.168.1.5/")).status, 400);
  assert.equal((await call("http://169.254.169.254/latest")).status, 400);
  assert.equal((await call("file:///etc/passwd")).status, 400);
});
