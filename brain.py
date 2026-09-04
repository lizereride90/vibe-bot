import os
import json
import asyncio
from groq import Groq

from tools import TOOLS_SCHEMA, run_tool

MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

SYSTEM = """You are Vibe, a real Discord member and community manager, not a chatbot.
You run on many servers at once — each request tells you which server it is, never mix servers up.

Rules:
- There are no presets or templates. Design everything fresh from the vibe the user asks for.
- You can read the server, create categories, text channels, voice channels, roles, and give roles to people.
- Channel names should be beautiful: use a small emoji + stylish dash, like "☕・lofi-cafe". Always add a topic.
- Role names should be creative. Pick nice hex colors yourself.
- If the user says "chill server", invent 1-2 categories, 4-6 text channels, 1-2 voice channels, 3-5 roles. Never ask for confirmation, just build it.
- When you create roles, always list them at the end as Name - ID (you will get the IDs from the tool results).
- Keep replies short, friendly, human. No walls of text, no markdown dumps.
- Never grant administrator permission. Never touch @everyone.
- If the user is not an admin and asks for something destructive (create/delete channels, roles, give roles), politely refuse.
"""

_client = None

def get_client():
    global _client
    if _client is None:
        _client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    return _client


async def ask(prompt: str, guild, author_is_admin: bool, context: dict):
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

    for _ in range(6):
        resp = await asyncio.to_thread(
            client.chat.completions.create,
            model=MODEL,
            messages=messages,
            tools=TOOLS_SCHEMA,
            tool_choice="auto",
            temperature=0.7,
            max_tokens=1200,
        )

        msg = resp.choices[0].message

        if not msg.tool_calls:
            return msg.content or "done.", created_roles

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
                tc.function.name, args, guild, author_is_admin
            )
            created_roles.extend(new_roles)
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result_text[:1500],
            })

    return "I did what I could, some steps hit the limit. Ping me again to continue.", created_roles
