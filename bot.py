import os
import discord
from dotenv import load_dotenv

from brain import ask

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

client = discord.Client(intents=intents)


@client.event
async def on_ready():
    print(f"Logged in as {client.user} ({client.user.id})")


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

    async with message.channel.typing():
        history = []
        async for m in message.channel.history(limit=15):
            if m.author.bot and m.author != client.user:
                continue
            history.append(f"{m.author.display_name}: {m.content[:200]}")
        history.reverse()

        context = {
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

        if created_roles:
            lines = "\n".join(f"`{r.name}` — `{r.id}`" for r in created_roles)
            reply += f"\n\n**Role IDs:**\n{lines}"

        if len(reply) > 1900:
            reply = reply[:1900] + "..."

        await message.reply(reply)


if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("Missing DISCORD_TOKEN in .env")
    client.run(TOKEN)
