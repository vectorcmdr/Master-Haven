# Phase 6 — NPM proxy setup

One-time setup to put the Travelers Archive behind your existing NPM
at `https://archive.havenmap.online`. Backend is already configured to
trust proxy headers (`X-Forwarded-Proto`, `X-Forwarded-For`) and to
flip session cookies to `Secure` when `ENV=production`. The work below
is on the NPM side — you'll do it in the NPM admin UI.

## Prereqs

- [x] Phase 5a deployed. `http://pi8gb:8020/` loads.
- [x] Archive container is attached to the `docker_default` network
      (as of the Phase 6 compose update). Verify:
      `ssh pi8gb@pi8gb "docker inspect archive | grep docker_default"`
      → should print one match.
- [x] NPM container is running at `http://10.0.0.229:81` (admin port).

## Step 1 — Cloudflare DNS

Add an A or CNAME record at your DNS provider (you use Cloudflare per
the Haven setup):

```
Name:    archive
Type:    CNAME           (or A record pointing to your home IP)
Target:  havenmap.online (or your home IP)
Proxy:   DNS only (the gray cloud, NOT orange) — Let's Encrypt needs
         direct HTTP-01 to the Pi for the cert challenge. Once the
         cert is issued you can flip it to proxied.
TTL:     Auto
```

Wait ~1 minute, then verify:
```
nslookup archive.havenmap.online
```
should resolve to the same IP as `havenmap.online`.

## Step 2 — NPM proxy host

In a browser, open `http://10.0.0.229:81` (NPM admin).

**Hosts → Proxy Hosts → Add Proxy Host**

### Details tab

| Field | Value |
|---|---|
| Domain Names | `archive.havenmap.online` (hit enter to chip-it) |
| Scheme | `http` |
| Forward Hostname / IP | `archive` |
| Forward Port | `8020` |
| Cache Assets | ☐ (off — Vite already fingerprints) |
| Block Common Exploits | ☑ |
| Websockets Support | ☑ |
| Access List | Publicly Accessible |

### Custom Locations tab
Leave empty.

### SSL tab

| Field | Value |
|---|---|
| SSL Certificate | "Request a new SSL Certificate" |
| Force SSL | ☑ |
| HTTP/2 Support | ☑ |
| HSTS Enabled | ☑ |
| HSTS Subdomains | ☐ |
| Email Address | (your Let's Encrypt email — same as the other hosts) |
| I Agree to the Let's Encrypt Terms of Service | ☑ |

### Advanced tab
Leave empty.

Click **Save**. NPM will request the cert from Let's Encrypt (takes ~30
seconds). If the cert request fails, double-check Cloudflare is set to
"DNS only" (gray cloud, not orange) and that `archive.havenmap.online`
resolves to your home IP.

## Step 3 — Verify

```bash
# From anywhere with internet:
curl -sI https://archive.havenmap.online/health
# expect: HTTP/2 200, Server: nginx

curl -s https://archive.havenmap.online/api/v1/civilizations | head -c 80
# expect: JSON starting with {"data":[{"slug":"galactic-hub"...
```

Browser test: open `https://archive.havenmap.online/` — padlock should
be green, SPA loads, all routes work.

## Step 4 — (Optional, recommended) lock down direct port 8020

Once NPM is proven working, edit `archive/docker-compose.yml` and
remove the `ports:` block (the four lines under `ports:`). Redeploy:

```bash
ssh pi8gb@pi8gb "cd ~/docker/haven-ui/Master-Haven/archive && docker compose up -d"
```

The archive will then ONLY be reachable through NPM. Tailscale-direct
testing on `pi8gb:8020` will stop working — use the public URL.

## Step 5 — (Optional) set PUBLIC_HOST + ENV=production

To flip session cookies to `Secure` (HTTPS-only), set:

```bash
ssh pi8gb@pi8gb "cd ~/docker/haven-ui/Master-Haven/archive && \
  echo 'ENV=production' >> .env && \
  echo 'PUBLIC_HOST=archive.havenmap.online' >> .env && \
  echo 'SESSION_SECRET='\$(openssl rand -base64 32) >> .env && \
  docker compose up -d"
```

**Important:** flipping `ENV=production` ALSO disables the
`/api/v1/auth/dev/*` endpoints (they return 404). After this point,
the only way to log in is Phase 7's Discord OAuth flow, which
isn't built yet. **Keep `ENV=dev` until Phase 7 ships**, even with
NPM proxying — the dev login is gated by env, not by network.

## Troubleshooting

- **Let's Encrypt fails:** Cloudflare proxy must be OFF (gray cloud)
  for the HTTP-01 challenge. Flip it back to ON (orange) only after
  cert issuance succeeds.
- **NPM can't reach archive:** confirm both are on `docker_default`:
  `docker network inspect docker_default | grep -E 'archive|npm'`
  Both names should appear.
- **502 Bad Gateway:** the archive container is down. Check
  `docker compose ps` and `docker compose logs archive`.
- **Mixed-content errors after enabling SSL:** clear browser cache.
  Vite's `index.html` is fingerprinted but the SPA itself caches
  endpoint URLs in JS; a hard reload sorts it.
- **Hash routing breaks on deep links:** the SPA fallback in
  `app/main.py` serves `index.html` for any non-`/api` path, so
  `https://archive.havenmap.online/anything` should always load the
  SPA. If it 404s, the catch-all isn't reached — check route order.

## What you don't need to do

- No FastAPI changes. uvicorn already runs with `--proxy-headers
  --forwarded-allow-ips='*'` so X-Forwarded-Proto from NPM is trusted.
- No CORS config. Frontend and API share the origin.
- No port changes. Container internal port stays 8020.
