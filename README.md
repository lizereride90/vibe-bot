# Vibe Bot

Ping-only Discord member bot powered by OpenRouter (primary) + Gemini + Groq fallback chain. Multi-server ready — just invite it anywhere, no setup per server. Currently running in 53 servers.

> it's made by Ji-young (ji-eun) with @y.o.r.u.zekai • GitHub: https://github.com/lizereride90/vibe-bot

A Discord bot that acts like a real member. Ping it and it builds stuff with AI. No slash commands, no presets — everything is generated through a three-leg LLM chain with automatic failover. It also watches every message: kills scam/spam automatically and answers server questions.
Pre hosted bot: https://discord.com/oauth2/authorize?client_id=1545382459305365645

## What it does (ping it or reply to it — no slash commands)

- `@Vibe hey can u create some beautiful channels like chill server` → builds categories, channels, roles, replies with Role IDs
- `@Vibe who is in this server?` / `@Vibe give Vibester to @Ram` → member lookup + roles
- `@Vibe change Ram's nickname to Lofi King` → nicknames
- `@Vibe timeout @spammer for 10 minutes` / `kick` / `ban` / `unban` → moderation (admins only)
- `@Vibe move Ram to Chill VC` / `mute him` → voice control
- `@Vibe lock #general` / `purge 20` / `slowmode 5 on #chat` → channel control
- `@Vibe post a poll: best game?` / `send "event at 8pm" to #announcements` → messages + polls
- `@Vibe make an invite for #general` / `show me Ram's avatar` → invites + avatars
- `@Vibe remember that our game night is Friday` → per-server memory

Reads work for everyone. Anything that changes the server needs an admin.

## Brains (three-leg failover chain)

Every request tries each leg in order — models outer, keys inner, so every model gets every key before moving on:

1. **OpenRouter** (primary) — one free key fans out to ~24 `:free` models server-side. Default chain: `nvidia/nemotron-3.5-lightning:free → openai/gpt-oss-20b:free → z-ai/glm-4.5-air:free → qwen/qwen3-32b:free`. Get a key at https://openrouter.ai/keys — no card, free models cost $0. Override with `OPENROUTER_MODEL` / `OPENROUTER_BACKUPS`.
2. **Gemini** (second leg) — get a key at https://aistudio.google.com/. Default `gemini-3.5-flash-lite` with auto-tried backups on 404.
3. **Groq** (last resort) — get a key at https://console.groq.com. Default `openai/gpt-oss-20b`.

All legs are OpenAI-compatible, so the same tool schema works everywhere with zero conversion. Keys are comma-separated and auto-rotate on 429/503/5xx: `KEY1,KEY2,KEY3`. Empty legs are skipped automatically.

## Setup

1. Discord Developer Portal → New Application → Bot → copy token
   - Enable `MESSAGE CONTENT INTENT` + `SERVER MEMBERS INTENT`
   - Invite with `bot` scope, perms: Manage Channels + Manage Roles
   - Move the bot's role to the top of the role list

2. Keys — OpenRouter (https://openrouter.ai/keys) for the primary leg, Gemini (https://aistudio.google.com/) + Groq (https://console.groq.com) as backups. At minimum, one leg needs a key.

3. Run:

```bash
pip install -r requirements.txt
cp .env.example .env
# fill in DISCORD_TOKEN, OPENROUTER_API_KEY, GEMINI_API_KEY, GROQ_API_KEY
python bot.py
```

## Watchdog (always-on scanning)

Every message gets scanned: phishing/nitro scams, slurs, spam bursts → deleted + warned, timed out if nasty. Server questions and "vibe" name-calls get answered with full tool access. Normal chat is ignored. Toggle with `WATCHDOG_ENABLED=false`. Needs Manage Messages + Moderate Members perms for the mod actions.

## Host on Discloud (free, 24/7)

1. Zip the project (`bot.py`, `brain.py`, `llm.py`, `tools.py`, `ui.py`, `settings.py`, `watchdog.py`, `requirements.txt`, `discloud.config`, `.env`) or connect the GitHub repo.
2. Upload via dashboard / CLI / their Discord bot — `discloud.config` already sets `MAIN=bot.py`, `RAM=100` (free max), `AUTORESTART=true`.
3. Set env vars on Discloud if `.env` wasn't included: `DISCORD_TOKEN`, `OPENROUTER_API_KEY`, `OPENROUTER_MODEL`, `GEMINI_API_KEY`, `GEMINI_MODEL`, `GROQ_API_KEY`, `GROQ_MODEL`, `WATCHDOG_MODEL`, `WATCHDOG_ENABLED`.
4. Give the bot Manage Messages + Moderate Members perms for watchdog mod actions.

## Files

- `bot.py` — connects to Discord, listens for pings, feeds everything else to the watchdog
- `brain.py` — agentic tool loop (OpenRouter → Gemini → Groq via `llm.py`)
- `llm.py` — three-leg failover chain (OpenAI-compat REST, no extra deps)
- `watchdog.py` — scans all new messages, auto-mod + auto-answer
- `tools.py` — the actual Discord actions the AI can call
- `ui.py` — real Components V2 embeds (Container+TextDisplay+MediaGallery) with legacy fallback

Only admins can trigger creates / assigns. Everyone can chat.
