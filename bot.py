import os
import time
import discord
from dotenv import load_dotenv

from brain import ask
from watchdog import watch
import settings as cfg
from tools import set_bot, _find_text_channel, _find_role, _build_embed, _fmt
from ui import send_v2, safe_reply

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
CREDIT = "it's made by Ji-young (ji-eun) with @y.o.r.u.zekai • https://github.com/lizereride90/vibe-bot"

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True
intents.reactions = True

client = discord.Client(intents=intents)
set_bot(client)

# per-server cooldown so one server can't spam others (multi-server safe)
last_used: dict[int, float] = {}


@client.event
async def on_ready():
    print(f"Logged in as {client.user} ({client.user.id}) in {len(client.guilds)} servers")
    try:
        import llm as _llm
        await _llm.probe_and_log()
    except Exception as e:
        print(f"llm probe skipped: {e}")
    await client.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching, name="pings | made by Ji-young"
        )
    )


@client.event
async def on_member_join(member: discord.Member):
    try:
        guild = member.guild
        s = cfg.get_settings(guild.id)
        # autorole
        if s.get("autorole"):
            role = _find_role(guild, s["autorole"])
            if role:
                try:
                    await member.add_roles(role, reason="Vibe autorole")
                except Exception:
                    pass
        if not s.get("welcome_enabled"):
            return
        ch = _find_text_channel(guild, s.get("welcome_channel", ""))
        if not ch:
            # fallback: system channel or first writable channel
            ch = guild.system_channel
        if not ch:
            return
        msg = _fmt(s.get("welcome_message", "welcome {member}!"), member, guild)
        ping = member.mention if s.get("welcome_ping") else None
        if s.get("welcome_embed", True):
            await send_v2(ch, f"Welcome to {guild.name}! 🎉", msg, "#A78BFA",
                          footer=f"You're member #{guild.member_count}",
                          thumbnail=member.display_avatar.url, content=ping)
        else:
            await ch.send(f"{ping + ' ' if ping else ''}{msg}"[:1900])
    except Exception as e:
        print(f"welcome error: {e}")
    # member counter update
    try:
        await _update_counter(guild)
    except Exception:
        pass


async def _update_counter(guild: discord.Guild):
    s = cfg.get_settings(guild.id)
    tmpl = s.get("counter", "")
    if not tmpl:
        return
    label = tmpl.replace("{count}", str(guild.member_count)) if "{count}" in tmpl else f"{tmpl}: {guild.member_count}"
    for vc in guild.voice_channels:
        cur = vc.name
        base = tmpl.replace("{count}", "").strip(": ") if "{count}" in tmpl else tmpl
        if cur.startswith(base[:20]) or cur.startswith("Members"):
            try:
                await vc.edit(name=label[:100], reason="Vibe counter")
            except Exception:
                pass
            return


@client.event
async def on_member_remove(member: discord.Member):
    try:
        s = cfg.get_settings(member.guild.id)
        if not s.get("goodbye_enabled"):
            return
        ch = _find_text_channel(member.guild, s.get("goodbye_channel", ""))
        if not ch:
            return
        await ch.send(_fmt(s.get("goodbye_message", "{member} left."), member, member.guild)[:1900])
    except Exception:
        pass
    try:
        await _update_counter(member.guild)
    except Exception:
        pass


@client.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
    try:
        guild = client.get_guild(payload.guild_id) if payload.guild_id else None
        me_id = client.user.id if client.user else 0
        if payload.user_id == me_id:
            return
        # 1) first-to-react giveaway win
        if str(payload.emoji) == "🎉":
            info = cfg.get_giveaway(payload.message_id)
            if info and not info.get("ended") and info.get("mode") == "first" and guild:
                ch = guild.get_channel(payload.channel_id)
                try:
                    user = guild.get_member(payload.user_id) or await guild.fetch_member(payload.user_id)
                except Exception:
                    user = None
                if user and not user.bot:
                    cfg.end_giveaway_store(payload.message_id)
                    try:
                        from ui import send_v2 as _send_v2
                        await _send_v2(ch, "⚡ Giveaway Winner ⚡",
                                       f"Prize: **{info['prize']}**\nWinner: {user.mention} — fastest 🎉 wins! Congrats!",
                                       "#FFD700")
                    except Exception:
                        await ch.send(f"⚡ **GIVEAWAY WINNER** ⚡\nPrize: **{info['prize']}**\nWinner: {user.mention} — fastest 🎉 wins! Congrats!")
                    return
        # 2) reaction roles
        if guild:
            rr = cfg.find_rr(payload.message_id, str(payload.emoji))
            if rr and str(rr.get("guild")) == str(guild.id):
                role = _find_role(guild, rr.get("role", ""))
                try:
                    member = guild.get_member(payload.user_id) or await guild.fetch_member(payload.user_id)
                except Exception:
                    member = None
                if role and member and not member.bot:
                    try:
                        await member.add_roles(role, reason="Vibe reaction role")
                    except Exception:
                        pass
    except Exception as e:
        print(f"giveaway reaction error: {e}")


@client.event
async def on_raw_reaction_remove(payload: discord.RawReactionActionEvent):
    try:
        guild = client.get_guild(payload.guild_id) if payload.guild_id else None
        if not guild or (client.user and payload.user_id == client.user.id):
            return
        rr = cfg.find_rr(payload.message_id, str(payload.emoji))
        if rr and str(rr.get("guild")) == str(guild.id):
            role = _find_role(guild, rr.get("role", ""))
            try:
                member = guild.get_member(payload.user_id) or await guild.fetch_member(payload.user_id)
            except Exception:
                member = None
            if role and member and not member.bot:
                try:
                    await member.remove_roles(role, reason="Vibe reaction role removed")
                except Exception:
                    pass
    except Exception:
        pass


@client.event
async def on_message(message: discord.Message):
    if message.author.bot or not message.guild:
        return

    pinged = client.user in message.mentions

    # also respond when replying to the bot (no ping needed)
    # Unknown-message safe: deleted/uncached references just mean "not pinged"
    if not pinged and message.reference and message.reference.message_id:
        try:
            ref = message.reference.resolved
            if ref is None:
                try:
                    ref = await message.channel.fetch_message(message.reference.message_id)
                except (discord.NotFound, discord.HTTPException):
                    ref = None  # deleted or uncached — not an error
            pinged = bool(ref) and ref.author == client.user
        except Exception:
            pinged = False

    if not pinged:
        # passive scan: watchdog watches every message for spam/scams/questions
        try:
            await watch(message)
        except Exception as e:
            print(f"watchdog error: {type(e).__name__}: {str(e)[:200]}")
        return

    text = message.content
    for m in message.mentions:
        text = text.replace(f"<@{m.id}>", "").replace(f"<@!{m.id}>", "")
    text = text.strip()

    if not text:
        await safe_reply(message, "hey, what do you want me to do? just ping me and tell me.")
        return

    # per-server 8s cooldown, keeps multi-server smooth
    now = time.monotonic()
    gid = message.guild.id
    if now - last_used.get(gid, 0) < 8:
        await safe_reply(message, "one sec, finishing the last thing — ping me again in a bit.")
        return
    last_used[gid] = now

    async with message.channel.typing():
        try:
            history = []
            async for m in message.channel.history(limit=25):
                if m.author.bot and m.author != client.user:
                    continue
                history.append(f"{m.author.display_name}: {m.content[:200]}")
            history.reverse()

            s = cfg.get_settings(gid)
            context = {
                "guild_id": gid,
                "guild_name": message.guild.name,
                "author": message.author.display_name,
                "author_is_admin": message.author.guild_permissions.administrator,
                "recent_chat": history[:-1],  # exclude the ping itself
                "channel_name": message.channel.name,
                "server_config": (
                    f"antispam={s['antispam']} antiswear={s['antiswear']} "
                    f"welcome={s['welcome_enabled']}#{s['welcome_channel']} "
                    f"autorole={s['autorole'] or 'off'} log=#{s['log_channel'] or 'off'}"
                ),
            }

            reply, created_roles = await ask(
                prompt=text,
                guild=message.guild,
                author_is_admin=context["author_is_admin"],
                context=context,
                origin=message.channel,
                author=message.author,
            )
            if reply is None:
                # both gemini + groq down — only direct pings get an error message.
                # watchdog path stays silent (handled in watchdog._answer).
                reply = "my AI brain hiccuped (all providers down) — ping me again in a bit."
                created_roles = created_roles or []
        except Exception as e:
            print(f"on_message error: {type(e).__name__}: {str(e)[:300]}")
            await safe_reply(message, "something broke on my end — ping me again in a bit.")
            return

        if created_roles:
            lines = "\n".join(f"`{r.name}` — `{r.id}`" for r in created_roles)
            reply += f"\n\n**Role IDs:**\n{lines}\n-# {CREDIT}"

        if len(reply) > 1900:
            reply = reply[:1900] + "..."

        await safe_reply(message, reply)


if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("Missing DISCORD_TOKEN in .env")
    client.run(TOKEN)
