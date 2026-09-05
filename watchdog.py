"""Watchdog: Vibe passively scans every new message.

- Scam/phishing, slurs, spam bursts -> delete + warn, timeout if nasty.
- Direct questions about the server (or "vibe" called by name) -> answered with tools.
- Normal chat -> ignored silently.

Cheap classifier model decides in one fast call; the big brain only wakes up to answer.
"""
import os
import json
import time
import asyncio
import datetime
from collections import deque, defaultdict

import discord
from groq import Groq

from tools import _find_member, _manageable

MODEL = os.getenv("WATCHDOG_MODEL", "groq/compound-mini")
ENABLED = os.getenv("WATCHDOG_ENABLED", "true").lower() == "true"

ANSWER_COOLDOWN = 60   # one helpful reply per channel per minute
MOD_COOLDOWN = 300     # one mod action per user per 5 min
REPEAT_WINDOW = 120    # same text 3x in 2 min = spam burst

_last_answer: dict[int, float] = {}
_last_mod: dict[int, float] = {}
_recent: dict[int, deque] = defaultdict(lambda: deque(maxlen=30))

_client = None

CLASSIFIER = """You moderate a Discord server. Classify the new message.
Reply ONLY with JSON: {"decision": "ignore|answer|moderate", "severity": "low|high", "reason": "..."}.

- moderate/high: phishing or scam links (free nitro, steam gifts, airdrops), malware, slurs/hate, threats, gore/NSFW text, discord invite spam to other servers.
- moderate/low: ALL-CAPS shouting, flooding emojis, obvious ad spam for other servers/products.
- answer: a direct question about THIS server (roles, channels, rules, events, members) or someone talking to "vibe" by name.
- ignore: everything else — normal chat, jokes, opinions, short reactions. When unsure, ignore."""


def get_client():
    global _client
    if _client is None:
        _client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    return _client


def _is_repeat(guild_id, author_id, text):
    key = (author_id, hash(text.strip().lower()))
    now = time.monotonic()
    buf = _recent[guild_id]
    buf.append((now, key))
    hits = sum(1 for t, k in buf if k == key and now - t < REPEAT_WINDOW)
    return hits >= 3 and len(text.strip()) > 0


async def _late_delete(message, delay=15):
    await asyncio.sleep(delay)
    try:
        await message.delete()
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

    # cheap local check first: same user repeating the same text
    if _is_repeat(guild.id, message.author.id, text):
        await _moderate(message, "high", "spam burst (same message 3x)")
        return

    # called by name without a ping -> answer path, skip the classifier
    if "vibe" in text.lower():
        await _answer(message)
        return

    try:
        resp = get_client().chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": CLASSIFIER},
                {"role": "user", "content": (
                    f"#{message.channel.name} | {message.author.display_name}"
                    f" (admin={message.author.guild_permissions.administrator}):\n{text[:500]}"
                )},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
            max_tokens=200,
        )
        verdict = json.loads(resp.choices[0].message.content or "{}")
    except Exception as e:
        print(f"watchdog classifier error: {type(e).__name__}: {str(e)[:150]}")
        return

    decision = verdict.get("decision", "ignore")
    if decision == "moderate":
        if now - _last_mod.get(message.author.id, 0) < MOD_COOLDOWN:
            return
        _last_mod[message.author.id] = now
        await _moderate(message, verdict.get("severity", "low"), verdict.get("reason", ""))
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
            )
            if len(reply) > 1900:
                reply = reply[:1900] + "..."
            await message.reply(reply)
    except Exception as e:
        print(f"watchdog answer error: {type(e).__name__}: {str(e)[:200]}")
