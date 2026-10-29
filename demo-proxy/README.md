# Demo fetch proxy

A tiny Cloudflare Worker that lets the listing demo (`site/demo/`) read producer websites from the
browser. See the header of `worker.js` for exactly what it does and refuses to do.

## Deploy (once)

Needs a free Cloudflare account and Node.

```bash
cd demo-proxy
npx wrangler login
npx wrangler deploy
```

Wrangler prints the Worker's address, like `https://foodweb-demo-proxy.<your-subdomain>.workers.dev`.
Put it in `site/demo/config.js` as `PROXY_URL`, then commit. If the Pages site is not at
`https://open-food-web.github.io`, add its origin to `ALLOWED_ORIGINS` in `worker.js` first.

## Try it

```bash
curl -H "Origin: https://open-food-web.github.io" "https://<worker address>/?url=https://andersonfarms.com/" | head
```

A site whose robots.txt disallows the page returns 403 `robots-disallowed`; the demo shows that as a
plain message.

## Tests

```bash
node --test demo-proxy/worker.test.mjs
```
