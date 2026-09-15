# Remote mobile access (research)

Grocery Wizard runs as a **Streamlit** app (`just grocery-ui`) with **Notion** as the data store. Credentials live in `.env` (`NOTION_API_KEY`, database IDs). There is **no in-app login** today—anyone who can reach the URL can use your Notion integration.

This document compares ways to use the UI on a phone **outside home Wi‑Fi**, records a **household decision**, and points at backlog work if that decision changes.

## Household decision (2026)

| Use case | Approach |
| --- | --- |
| **Default** | Run `just grocery-ui` on the Mac when it is on; use the **CLI** when the UI is not running. Optional: phone on **same Wi‑Fi** while the Mac is up (`just grocery-ui -- --server.address=0.0.0.0` if needed). |
| **Phone on cellular / anytime** | Only if we add an **always-on hosted** Streamlit (#138) plus **auth** (#139). Not tunnel-to-Mac—the laptop is often off, so that path is not worth building in this repo. |

No committed Just recipes or config exist for tunnels or LAN bind; pass Streamlit flags yourself if you ever experiment locally.

## Requirements (implicit)

| Need | Notes |
| --- | --- |
| Phone browser from anywhere | HTTPS URL, not only `localhost` / LAN IP |
| Secrets stay out of git | Already true; hosted deploy needs platform secret store |
| Single household / low traffic | No multi-tenant product requirements |
| Notion is source of truth | Remote access does not require syncing `.local/` to the cloud for core flows; some session files may still be laptop-local |

## Options compared

### A. Tunnel to the machine running Streamlit

Run Streamlit on your Mac (or a home server) and expose it through a tunnel (Tailscale, Cloudflare Tunnel, ngrok, etc.).

| Approach | Pros | Cons |
| --- | --- | --- |
| **Tailscale** (or similar mesh VPN) | Private; secrets stay on your machine | Host must be **on**; VPN app on phone |
| **Cloudflare Tunnel** (`cloudflared`) | Stable HTTPS; optional **Cloudflare Access** in front | Host must be **on**; setup outside the repo |
| **ngrok / similar** | Fast to try | Ephemeral URLs on free tiers |

**Not chosen here:** with the Mac often off, tunnel-to-laptop does not meet “use the UI when I want from my phone.”

### B. Always-on hosted Streamlit

Deploy the same app to a PaaS (Railway, Fly.io, Render, a small VPS, etc.) or **Streamlit Community Cloud**.

| Approach | Pros | Cons |
| --- | --- | --- |
| **Streamlit Community Cloud** | Minimal ops if repo + secrets fit their model | Public/community constraints; **no built-in auth** on the app URL |
| **Railway / Fly / Render / VPS** | Always on | Monthly cost; `NOTION_*` in platform secrets; **auth required** before a public URL; Dockerfile or build config |
| **Serverless** | — | Poor fit for Streamlit |

**If we want remote UI later:** this is the path (#138, #139), not tunnels to the Mac.

### C. Mobile shell (PWA vs native)

| Approach | Pros | Cons |
| --- | --- | --- |
| **Mobile browser + “Add to Home Screen”** | No backend change | Streamlit is not a full PWA; offline does not work |
| **PWA metadata + UI pass** (#140) | More app-like launch | Does not replace hosting or auth |
| **Native wrapper** | Store presence | High cost for a personal tool |

## Recommendation

**Today:** use **local Streamlit + CLI** when the Mac is on; do **not** invest in tunnel-to-Mac automation in this repo.

**If remote UI becomes a requirement:** implement **always-on host + auth** (#138, #139) in that order. Treat Cloudflare Tunnel-to-Mac as a personal ops note only, not a product path.

**Defer:** Native app; Streamlit Community Cloud as default (auth + repo visibility); Mac tunnel runbook (#137 — closed as not planned).

## Staged follow-up issues

| Phase | Backlog issue | Topic |
| --- | --- | --- |
| — | ~~[#137](https://github.com/rachelgramlich/personal-repo/issues/137)~~ | Mac tunnel runbook — **not planned** (Mac often off) |
| 1 | [#138](https://github.com/rachelgramlich/personal-repo/issues/138) | Always-on Streamlit deploy (container + platform secrets) |
| 2 | [#139](https://github.com/rachelgramlich/personal-repo/issues/139) | Access control in-app or at edge |
| 3 | [#140](https://github.com/rachelgramlich/personal-repo/issues/140) | Mobile UX: Add to Home Screen hints, optional PWA meta, touch layout pass |

## Security checklist (any public URL)

- [ ] Gate the URL (Cloudflare Access, or app auth)—**do not** expose raw Streamlit to the internet.
- [ ] Keep `.env` out of git; rotate `NOTION_API_KEY` if it was ever leaked.
- [ ] Notion integration should only have access to the databases you intend.
- [ ] Optional: NYT cookies in `.env` are sensitive; same rules apply on a hosted machine.

## Manual smoke test (local UI only)

1. With `.env` set and Mac on: `just grocery-ui` → `http://localhost:8501` → Notion-backed tabs load.
2. If you need same-Wi‑Fi phone once: `just grocery-ui -- --server.address=0.0.0.0` and open the Mac’s LAN IP (no repo recipe required).
