import os
import time
import discord
from dotenv import load_dotenv

from brain import ask

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
CREDIT = "it's made by Ji-young (ji-eun) with @y.o.r.u.zekai • https://github.com/lizereride90/vibe-bot"

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

client = discord.Client(intents=intents)

# per-server cooldown so one server can't spam others (multi-server safe)
last_used: dict[int, float] = {}


@client.event
async def on_ready():
    print(f"Logged in as {client.user} ({client.user.id}) in {len(client.guilds)} servers")
    await client.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching, name="pings | made by Ji-young"
        )
    )


@client.event
async def on_message(message: discord.Message):
    if message.author.bot or not message.guild:
        return

    if client.user not in message.mentions:
        return

    text = message.content
    for m in message.mentions:
        text = text.replace(f"<@{m.id}>", "").replace(f"<@!{m.id}>", "")
    text = text.strip()

    if not text:
        await message.reply("hey, what do you want me to do? just ping me and tell me.")
        return

    # per-server 8s cooldown, keeps multi-server smooth
    now = time.monotonic()
    gid = message.guild.id
    if now - last_used.get(gid, 0) < 8:
        await message.reply("one sec, finishing the last thing — ping me again in a bit.")
        return
    last_used[gid] = now

    async with message.channel.typing():
        try:
            history = []
            async for m in message.channel.history(limit=15):
                if m.author.bot and m.author != client.user:
                    continue
                history.append(f"{m.author.display_name}: {m.content[:200]}")
            history.reverse()

            context = {
                "guild_id": gid,
                "guild_name": message.guild.name,
                "author": message.author.display_name,
                "author_is_admin": message.author.guild_permissions.administrator,
                "recent_chat": history[:-1],  # exclude the ping itself
                "channel_name": message.channel.name,
            }

            reply, created_roles = await ask(
                prompt=text,
                guild=message.guild,
                author_is_admin=context["author_is_admin"],
                context=context,
            )
        except Exception as e:
            print(f"on_message error: {type(e).__name__}: {str(e)[:300]}")
            await message.reply("something broke on my end — ping me again in a bit.")
            return

        if created_roles:
            lines = "\n".join(f"`{r.name}` — `{r.id}`" for r in created_roles)
            reply += f"\n\n**Role IDs:**\n{lines}\n-# {CREDIT}"

        if len(reply) > 1900:
            reply = reply[:1900] + "..."

        await message.reply(reply)


if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("Missing DISCORD_TOKEN in .env")
    client.run(TOKEN)
