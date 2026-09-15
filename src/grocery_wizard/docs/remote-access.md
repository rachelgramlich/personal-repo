# Remote mobile access (research)

Grocery Wizard runs as a **Streamlit** app (`just grocery-ui`) with **Notion** as the data store. Credentials live in `.env` (`NOTION_API_KEY`, database IDs). There is **no in-app login** today—anyone who can reach the URL can use your Notion integration.

This document compares ways to use the UI on a phone **outside home Wi‑Fi**, picks a recommended path, and lists follow-up backlog items for later phases.

## Requirements (implicit)

| Need | Notes |
| --- | --- |
| Phone browser from anywhere | HTTPS URL, not only `localhost` / LAN IP |
| Secrets stay out of git | Already true; hosted deploy needs platform secret store |
| Single household / low traffic | No multi-tenant product requirements |
| Notion is source of truth | Remote access does not require syncing `.local/` to the cloud for core flows; some session files may still be laptop-local |

## Options compared

### A. Tunnel to the machine running Streamlit

Run Streamlit on your Mac (or a home server) and expose it through a tunnel.

| Approach | Pros | Cons |
| --- | --- | --- |
| **Tailscale** (or similar mesh VPN) | Private; no public URL; simple phone app; secrets stay on your machine | Mac (or host) must be on; not a “shareable link”; still no app-level auth (VPN *is* the gate) |
| **Cloudflare Tunnel** (`cloudflared`) | Stable HTTPS hostname; works from cellular; optional **Cloudflare Access** (email/OTP) in front | Mac/host must be running; tunnel + Access setup is one-time ops |
| **ngrok / similar** | Fast to try | Free tier URLs rotate; less ideal as a long-term “my app” URL |

**Auth:** Tailscale = network-level. Cloudflare Access = identity in front of Streamlit without changing Python code.

### B. Always-on hosted Streamlit

Deploy the same app to a PaaS (Railway, Fly.io, Render, a small VPS, etc.) or **Streamlit Community Cloud**.

| Approach | Pros | Cons |
| --- | --- | --- |
| **Streamlit Community Cloud** | Minimal ops if repo + secrets fit their model | Public/community constraints; must configure secrets in their UI; **no built-in auth** on the app URL |
| **Railway / Fly / Render / VPS** | Always on; you control region and uptime | Monthly cost; must inject all `NOTION_*` env vars; **must add auth** before exposing a public URL; Dockerfile or build config to maintain |
| **Serverless** | — | Poor fit: cold starts, long-lived WebSocket sessions, and Streamlit’s execution model |

**Auth:** Required for any **public** hostname. Options: Cloudflare Access in front of the host, OAuth reverse proxy, or a Streamlit auth layer (e.g. `streamlit-authenticator`)—each is a deliberate follow-up.

### C. Mobile shell (PWA vs native)

| Approach | Pros | Cons |
| --- | --- | --- |
| **Mobile browser + “Add to Home Screen”** | Zero backend change; works with any access path above | Streamlit is not a full PWA; offline does not work |
| **PWA metadata + UI pass** | App-icon launch, slightly more “app-like” | Does not replace hosting or auth |
| **Native wrapper (Capacitor, etc.)** | Store presence | High cost for a personal tool; still needs API/hosting story |

The app already uses `layout="centered"` and a shared theme; a dedicated **mobile layout** pass is orthogonal to **reachability**.

## Recommendation

**Primary path (phase 1): Cloudflare Tunnel + Access** to the Streamlit process on your Mac (or an always-on home machine).

**Rationale:**

1. **Secrets:** `NOTION_API_KEY` stays in your local `.env`; you are not copying household tokens onto a third-party runtime unless you choose to.
2. **Auth:** Cloudflare Access gives a practical gate (e.g. your email) without rewriting the Streamlit app.
3. **Phone use:** You get a fixed HTTPS URL on cellular; bookmark or Add to Home Screen.
4. **Cost / complexity:** Free tier is enough for personal use; less ongoing work than maintaining a container deploy for a single user.

**When to prefer Tailscale instead:** You only need access for your own devices, you are fine with the VPN app, and you do not need a normal HTTPS link to share.

**When to prefer always-on hosting (phase 2):** The Mac is often asleep/off and you still want the UI 24/7. Then deploy Streamlit in a container with env secrets **and** treat **access control** as a blocking follow-up before going public.

**Defer:** Native app; Streamlit Community Cloud as the default (auth gap + repo visibility assumptions).

## Minimal viable remote access (implemented in this repo)

These changes support tunnel/hosted runs without picking a vendor for you:

1. **`.streamlit/config.toml`** — theme + `headless` server mode, usage stats off.
2. **`just grocery-ui-remote`** — binds `0.0.0.0:8501` so a local tunnel agent can forward to Streamlit.

You still run **your** tunnel (or VPN) and **your** Access policy outside the repo.

### Example: Cloudflare Tunnel (outline)

On the machine where `.env` exists:

```shell
just grocery-ui-remote
```

In another terminal (after `cloudflared` login and creating a tunnel in the Cloudflare dashboard), publish HTTP to localhost—for example:

```yaml
# ~/.cloudflared/config.yml (user-specific, not committed)
tunnel: <tunnel-uuid>
credentials-file: /path/to/<tunnel-uuid>.json

ingress:
  - hostname: grocery.example.com
    service: http://localhost:8501
  - service: http_status:404
```

Enable **Cloudflare Access** on `grocery.example.com` (allow only your identity). Open that URL on your phone.

### Same Wi‑Fi only (unchanged)

```shell
just grocery-ui -- --server.address=0.0.0.0
```

Or use `just grocery-ui-remote` for the same bind with the committed Streamlit defaults.

### Hosted deploy (phase 2 sketch)

Not implemented here. A follow-up should add a `Dockerfile`, document required env vars (mirror `.env.example`), and require auth before exposing the service.

## Staged follow-up issues

| Phase | Backlog issue | Topic |
| --- | --- | --- |
| 1b | [#137](https://github.com/rachelgramlich/personal-repo/issues/137) | Cloudflare Tunnel + Access runbook for this repo |
| 2 | [#138](https://github.com/rachelgramlich/personal-repo/issues/138) | Always-on Streamlit deploy (container + platform secrets) |
| 3 | [#139](https://github.com/rachelgramlich/personal-repo/issues/139) | Access control in-app or at edge if not using Cloudflare Access |
| 4 | [#140](https://github.com/rachelgramlich/personal-repo/issues/140) | Mobile UX: Add to Home Screen hints, optional PWA meta, touch layout pass |

## Security checklist (any public URL)

- [ ] Gate the URL (Cloudflare Access, Tailscale, or app auth)—**do not** expose raw Streamlit to the internet.
- [ ] Keep `.env` out of git; rotate `NOTION_API_KEY` if it was ever leaked.
- [ ] Notion integration should only have access to the databases you intend.
- [ ] Optional: NYT cookies in `.env` are sensitive; same rules apply on a hosted machine.

## Manual smoke test (tunnel path)

1. On laptop: `just grocery-ui-remote` → open `http://localhost:8501` → weekly plan or grocery tab loads Notion data.
2. Configure tunnel to `localhost:8501`; open HTTPS URL on phone (on cellular, not Wi‑Fi).
3. Confirm Access (or VPN) blocks strangers; confirm you can complete one read/write flow (e.g. view pantry list).
