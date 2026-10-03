"""Watchdog: Vibe passively scans every new message.

- Scam/phishing, slurs, spam bursts -> delete + warn, timeout if nasty.
- Respects per-server antispam / antiswear toggles set via "enable antispam".
- Direct questions about the server (or "vibe" called by name) -> answered with tools.
- Normal chat -> ignored silently.
"""
import os
import json
import re
import time
import asyncio
import datetime
from collections import deque, defaultdict

import discord

import llm
from tools import _find_member, _manageable
import settings as cfg

WATCHDOG_GROQ_MODEL = os.getenv("WATCHDOG_MODEL", "openai/gpt-oss-20b")
ENABLED = os.getenv("WATCHDOG_ENABLED", "true").lower() == "true"
VIBE_RE = re.compile(r"\bvibe\b", re.I)

ANSWER_COOLDOWN = 60
MOD_COOLDOWN = 300
REPEAT_WINDOW = 120

_last_answer: dict[int, float] = {}
_last_mod: dict[int, float] = {}
_last_levelup: dict[int, float] = {}
_last_trigger: dict[int, float] = {}
_recent: dict[int, deque] = defaultdict(lambda: deque(maxlen=30))
_burst: dict[int, deque] = defaultdict(lambda: deque(maxlen=10))

_client = None

CLASSIFIER = """You moderate a Discord server. Classify the new message.
Reply ONLY with JSON: {"decision": "ignore|answer|moderate", "severity": "low|high", "reason": "..."}.

- moderate/high: phishing or scam links (free nitro, steam gifts, airdrops), malware, slurs/hate, threats, gore/NSFW text, discord invite spam to other servers.
- moderate/low: ALL-CAPS shouting, flooding emojis, obvious ad spam for other servers/products.
- answer: a direct question about THIS server (roles, channels, rules, events, members) or someone talking to "vibe" by name.
- ignore: everything else — normal chat, jokes, opinions, short reactions. When unsure, ignore."""

INVITE_RE = re.compile(r"discord\.gg/\S+|discord\.com/invite/\S+", re.I)
LINK_RE = re.compile(r"https?://\S+", re.I)
EMOJI_RE = re.compile(r"<a?:\w+:\d+>|[\U0001F300-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF\u2300-\u23FF]", re.UNICODE)


def get_client():
    return None  # legacy stub — classifier now goes through llm.py (gemini -> groq)


def _is_repeat(guild_id, author_id, text):
    key = (author_id, hash(text.strip().lower()))
    now = time.monotonic()
    buf = _recent[guild_id]
    buf.append((now, key))
    hits = sum(1 for t, k in buf if k == key and now - t < REPEAT_WINDOW)
    return hits >= 3 and len(text.strip()) > 0


def _local_spam_check(text, author_id):
    """Fast local antispam: caps, emoji flood, links, mentions, burst. Returns reason or ''."""
    t = text.strip()
    if len(t) < 4:
        return ""
    # burst: 5 msgs in 8s
    now = time.monotonic()
    buf = _burst[author_id]
    buf.append(now)
    if len(buf) >= 5 and now - buf[0] < 8:
        return "sending messages too fast"
    letters = [c for c in t if c.isalpha()]
    if len(letters) > 12 and sum(1 for c in letters if c.isupper()) / len(letters) > 0.75:
        return "all-caps shouting"
    if len(EMOJI_RE.findall(t)) > 8:
        return "emoji flood"
    if len(LINK_RE.findall(t)) > 3 or len(INVITE_RE.findall(t)) >= 1 and len(t) < 60:
        return "invite/link spam"
    if len(t) > 400 and len(set(t.lower().split())) < 6:
        return "repetitive spam"
    return ""


def _swear_hit(guild_id, text):
    words = cfg.get_words(guild_id)
    low = text.lower()
    for w in words:
        if w and re.search(r"\b" + re.escape(w) + r"\b", low):
            return w
    return ""


# cheap pre-filter so we don't burn Groq TPD on every "lol" / "ok" message.
# classify() costs ~500-1000 tokens each — with 11 servers that kills the
# 200K/day free quota and causes the "all providers down" hiccup.
_SUS_RE = re.compile(
    r"nitro|free.*(gift|nitro|steam|robux|airdrop)|steam.*gift|discord\.gg|"
    r"@everyone|@here|<@&\d+>|http|ww+\.|question|how|what|where|when|who|why|"
    r"help|rule|role|channel|event|vibe|mod|admin|ban|kick|timeout",
    re.I,
)

def _needs_ai(text: str) -> bool:
    t = text.strip()
    if len(t) < 4:
        return False
    # links/invites always need a check
    if LINK_RE.search(t) or INVITE_RE.search(t):
        return True
    # questions / long messages might be server questions
    if "?" in t or len(t) > 120:
        return True
    # shouting / emoji flood already handled locally, but let AI see it
    if len(EMOJI_RE.findall(t)) > 4:
        return True
    if _SUS_RE.search(t):
        return True
    return False


async def _late_delete(message, delay=15):
    await asyncio.sleep(delay)
    try:
        await message.delete()
    except (discord.NotFound, discord.HTTPException, discord.Forbidden):
        pass
    except Exception:
        pass


async def _social(message: discord.Message, s: dict, now: float):
    """XP levels, AFK notices, autoresponder triggers. Lightweight, no AI."""
    guild = message.guild
    low = message.content.lower().strip()

    # AFK: author came back -> clear
    if cfg.get_afk(guild.id, message.author.id):
        cfg.clear_afk(guild.id, message.author.id)
        try:
            await message.channel.send(f"welcome back {message.author.mention}!", delete_after=10)
        except Exception:
            pass

    # AFK: someone pinged an AFK user
    for u in message.mentions:
        if not u.bot:
            reason = cfg.get_afk(guild.id, u.id)
            if reason:
                try:
                    await message.channel.send(f"💤 {u.display_name} is AFK: {reason}"[:300], delete_after=15)
                except Exception:
                    pass
                break

    # XP
    if s.get("xp_enabled", True) and len(low) > 3:
        old = cfg.get_xp(guild.id, message.author.id)
        new = cfg.add_xp(guild.id, message.author.id, 5)
        if cfg.xp_level(new) > cfg.xp_level(old) and now - _last_levelup.get(message.author.id, 0) > 120:
            _last_levelup[message.author.id] = now
            lvl = cfg.xp_level(new)
            # level reward roles
            try:
                lr = (cfg.get_settings(guild.id).get("level_roles") or {})
                rname = lr.get(str(lvl))
                if rname:
                    from tools import _find_role as _fr
                    rr = _fr(guild, rname)
                    if rr and rr not in message.author.roles:
                        try:
                            await message.author.add_roles(rr, reason=f"Vibe level {lvl} reward")
                        except Exception:
                            pass
            except Exception:
                pass
            try:
                from ui import send_v2
                await send_v2(message.channel, "⬆️ Level up!",
                              f"{message.author.mention} hit **Level {lvl}**!", "#A78BFA")
            except Exception:
                pass

    # triggers (exact or contains)
    trigs = cfg.get_triggers(guild.id)
    if trigs and now - _last_trigger.get(message.channel.id, 0) > 20:
        for k, v in trigs.items():
            if k and (low == k or (len(k) > 3 and k in low)):
                _last_trigger[message.channel.id] = now
                try:
                    await message.channel.send(str(v)[:1500])
                except Exception:
                    pass
                break

    # sticky: repost after every non-bot message (delete old bot sticky first)
    try:
        sticky = cfg.get_sticky(guild.id, message.channel.id)
        if sticky and not message.author.bot:
            try:
                async for m in message.channel.history(limit=8):
                    if m.author.bot and sticky[:80] in (m.content or ""):
                        try:
                            await m.delete()
                        except Exception:
                            pass
                        break
                from ui import send_v2 as _sv2
                await _sv2(message.channel, "📌 Sticky", sticky, "#FFD700")
            except Exception:
                pass
    except Exception:
        pass


async def watch(message: discord.Message):
    if not ENABLED or message.author.bot or not message.guild:
        return
    text = message.content.strip()
    if not text:
        return

    guild = message.guild
    now = time.monotonic()
    s = cfg.get_settings(guild.id)
    is_admin = message.author.guild_permissions.administrator

    # 1) repeat burst — always on
    if _is_repeat(guild.id, message.author.id, text):
        if s.get("antispam", True) or not is_admin:
            await _moderate(message, "high", "spam burst (same message 3x)")
            return

    # 2) antiswear (toggleable, admins immune)
    if s.get("antiswear", False) and not is_admin:
        hit = _swear_hit(guild.id, text)
        if hit:
            if now - _last_mod.get(message.author.id, 0) < MOD_COOLDOWN:
                return
            _last_mod[message.author.id] = now
            await _moderate(message, "low", f"blocked word ({hit})")
            return

    # 3) local antispam (toggleable, admins immune)
    if s.get("antispam", True) and not is_admin:
        reason = _local_spam_check(text, message.author.id)
        if reason:
            if now - _last_mod.get(message.author.id, 0) < MOD_COOLDOWN:
                return
            _last_mod[message.author.id] = now
            await _moderate(message, "low", f"spam: {reason}")
            return

    # 3b) social: XP + AFK + triggers (never blocks, runs before AI)
    try:
        await _social(message, s, now)
    except Exception:
        pass

    # called by name without a ping -> answer path (word boundary, not "vibes")
    if VIBE_RE.search(text):
        if now - _last_answer.get(message.channel.id, 0) < ANSWER_COOLDOWN:
            return
        _last_answer[message.channel.id] = now
        await _answer(message)
        return

    # AI classifier: gemini primary, groq fallback (llm.py). Silent on total failure.
    # skip obvious normal chat to save TPD quota (see _needs_ai)
    if not _needs_ai(text):
        return
    verdict = await llm.classify(
        CLASSIFIER,
        f"#{message.channel.name} | {message.author.display_name}"
        f" (admin={is_admin}):\n{text[:500]}",
        temperature=0.2, max_tokens=200,
        groq_model=WATCHDOG_GROQ_MODEL,
    )
    if not verdict:
        return

    decision = verdict.get("decision", "ignore")
    sev = verdict.get("severity", "low")
    # admins immune to low-severity automod, but phishing/high still removed
    if decision == "moderate":
        if is_admin and sev == "low":
            return
        if now - _last_mod.get(message.author.id, 0) < MOD_COOLDOWN:
            return
        _last_mod[message.author.id] = now
        await _moderate(message, sev, verdict.get("reason", ""))
    elif decision == "answer":
        if now - _last_answer.get(message.channel.id, 0) < ANSWER_COOLDOWN:
            return
        _last_answer[message.channel.id] = now
        await _answer(message)


async def _moderate(message, severity, reason):
    member = message.author
    print(f"watchdog: {severity} from {member.display_name}: {reason[:100]}")

    try:
        await message.delete()
    except discord.Forbidden:
        print("watchdog: no Manage Messages perm, skipping")
        return
    except (discord.NotFound, discord.HTTPException):
        pass  # already gone — not an error
    except Exception:
        pass

    if severity == "high":
        m = _find_member(message.guild, str(member.id))
        if m:
            ok, _ = _manageable(message.guild, m)
            if ok:
                try:
                    await m.timeout(datetime.timedelta(minutes=10), reason=f"Vibe watchdog: {reason[:150]}")
                except Exception:
                    pass

    try:
        try:
            from ui import send_v2
            warn = await send_v2(
                message.channel, "⚠️ Message removed",
                f"{member.mention}, that got removed ({reason[:120]}). keep it clean.",
                "#FF5555",
            )
        except Exception:
            warn = await message.channel.send(
                f"hey {member.mention}, that got removed ({reason[:120]}). keep it clean."
            )
        asyncio.create_task(_late_delete(warn))
    except Exception:
        pass


async def _answer(message):
    from brain import ask

    try:
        async with message.channel.typing():
            history = []
            async for m in message.channel.history(limit=10):
                if m.author.bot and m.id != message.id:
                    continue
                history.append(f"{m.author.display_name}: {m.content[:200]}")
            history.reverse()

            reply, _ = await ask(
                prompt=message.content.strip()[:500],
                guild=message.guild,
                author_is_admin=message.author.guild_permissions.administrator,
                context={
                    "guild_id": message.guild.id,
                    "guild_name": message.guild.name,
                    "author": message.author.display_name,
                    "author_is_admin": message.author.guild_permissions.administrator,
                    "recent_chat": [h for h in history if not h.startswith(f"{message.author.display_name}: {message.content[:200]}")],
                    "channel_name": message.channel.name,
                },
                origin=message.channel,
                author=message.author,
            )
            if not reply:
                return  # all providers down — stay silent on passive path, no hiccup spam
            if len(reply) > 1900:
                reply = reply[:1900] + "..."
            from ui import safe_reply
            await safe_reply(message, reply)
    except Exception as e:
        print(f"watchdog answer error: {type(e).__name__}: {str(e)[:200]}")
