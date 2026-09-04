import os
import json
import asyncio
from groq import Groq

from tools import TOOLS_SCHEMA, run_tool

MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")

SYSTEM = """You are Vibe, a real Discord member and community manager, not a chatbot.
You run on many servers at once — each request tells you which server it is, never mix servers up.

What you can do (use your tools, don't just talk about it):
- Members: list everyone, look up any member, change nicknames, timeout/untimeout, kick, ban/unban, move/disconnect in voice, server mute/deafen.
- Roles: create, edit, delete, give, remove. Always report new Role IDs (you get them from tool results).
- Channels: create text/voice/categories, rename, retopic, slowmode, lock/unlock, delete, purge messages.
- Messages: read any channel's history, send messages to any channel, post polls.
- Server: give overviews (owner, counts, boosts). Remember things with notes.
- Design: no presets or templates. Channel names get a small emoji + stylish dash like "☕・lofi-cafe" with a topic. Role colors you pick yourself. When asked for a vibe (e.g. "chill server"), invent categories, channels and roles fresh and just build it — never ask for confirmation.

Rules:
- Keep replies short, friendly, human. No walls of text.
- Never grant administrator. Never touch @everyone or bot-managed roles.
- Kicks/bans/timeouts/deletes/purges: only when the requester clearly asks. Confirm the target by listing members first if the name is ambiguous.
- Changing servers stuff (create/delete/give/moderate) needs an admin — the request tells you if they are one. If not, politely refuse.
- Chain tools: e.g. list_members -> set_nickname, list_roles -> assign_role. Use IDs returned by tools for follow-up calls.
"""

_client = None

def get_client():
    global _client
    if _client is None:
        _client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    return _client


async def ask(prompt: str, guild, author_is_admin: bool, context: dict, origin=None):
    """Run the agentic loop. Returns (reply_text, created_roles)."""
    client = get_client()

    messages = [
        {"role": "system", "content": SYSTEM},
        {
            "role": "user",
            "content": (
                f"Server: {context['guild_name']} | Channel: #{context['channel_name']} | "
                f"From: {context['author']} (admin={author_is_admin})\n"
                f"Recent chat:\n" + "\n".join(context["recent_chat"][-10:]) +
                f"\n\nRequest: {prompt}"
            ),
        },
    ]

    created_roles = []

    for _ in range(8):
        try:
            resp = await asyncio.to_thread(
                client.chat.completions.create,
                model=MODEL,
                messages=messages,
                tools=TOOLS_SCHEMA,
                tool_choice="auto",
                temperature=0.7,
                max_tokens=3000,
            )
        except Exception as e:
            print(f"Groq error: {type(e).__name__}: {str(e)[:200]}")
            return (
                "my AI brain hiccuped (Groq API error) — ping me again in a bit.",
                created_roles,
            )

        msg = resp.choices[0].message

        if not msg.tool_calls:
            return msg.content or "done — check the server.", created_roles

        messages.append({
            "role": "assistant",
            "content": msg.content,
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in msg.tool_calls
            ],
        })

        for tc in msg.tool_calls:
            args = json.loads(tc.function.arguments or "{}")
            result_text, new_roles = await run_tool(
                tc.function.name, args, guild, author_is_admin, origin
            )
            created_roles.extend(new_roles)
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result_text[:1500],
            })

    return "I did what I could, some steps hit the limit. Ping me again to continue.", created_roles
