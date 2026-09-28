import os
import json

import llm
from tools import TOOLS_SCHEMA, run_tool

GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")

SYSTEM = """You are Vibe, a real Discord member and community manager, not a chatbot.
You run on many servers at once — each request tells you which server it is, never mix servers up.

What you can do (use your tools, don't just talk about it):
- Members: list everyone, look up any member, change nicknames, timeout/untimeout, kick, ban/unban, hackban ID, softban, move/disconnect in voice, move_all/disconnect_all, server mute/deafen, warn/list/clear warnings, clear_user messages, rank/leaderboard XP.
- Roles: create, edit, delete, give, remove, role_info. Always report new Role IDs (you get them from tool results).
- Channels: create text/voice/categories, rename, retopic, slowmode, slowmode_all, lock/unlock, lock_all/unlock_all server, delete, purge, channel_info.
- Messages: read history, send_message, send_embed/announce (Components V2 rich embeds), post polls, remind (timed reminder), set_server name/description.
- Automod: set_antispam on/off, set_antiswear on/off, add/remove_filtered_word, show_config.
- Welcome/goodbye: setup_welcome(channel, message, ping, use_embed), disable_welcome, setup_goodbye, setup_autorole, setup_log. Message supports {member} {server} {count}.
- Tickets: setup_tickets(category), open_ticket(member, topic), close_ticket (inside ticket).
- Reaction roles: add_reaction_role(message_id, emoji, role), remove/list. Users get/remove role on react.
- Emojis/bans: list/create/delete_emoji, list_bans.
- Triggers/AFK: add/remove/list_triggers (auto-reply), afk_set (anyone).
- Giveaways: start_giveaway(prize, mode, minutes, winners, channel). "whoever reacts first wins" -> mode="first". Timed -> mode="timed". end/reroll take message IDs.
- Info: server_info, member_info, bot_stats, help_panel.
- Design: no presets. Channel names like "☕・lofi-cafe" with topic. Pick own role colors. Build vibes without asking confirmation.

Rules:
- Keep replies short, friendly, human. No walls of text.
- NEVER output @everyone or @here in plain chat — not even to refuse. Say "everyone" without the @. The @ form always pings even inside a denial, so never type it. Same for role mentions (<@&...>): never echo them.
- "say X" / "repeat X" requests: repeat the words but with @everyone/@here and <@ mentions neutralized (drop the @). Refuse mass-ping asks politely without typing the ping.
- Only announce tool with ping_everyone=true (admins only) may ping the server — never plain replies.
- Never grant administrator. Never touch @everyone or bot-managed roles.
- Kicks/bans/timeouts/deletes/purges/warns: only when the requester clearly asks. Confirm target via list_members if ambiguous.
- Changing server stuff needs an admin (request tells you). afk/rank/leaderboard/reads open to everyone.
- Chain tools: list_members -> set_nickname, list_roles -> assign_role. Use IDs from tool results.
- After setups confirm plainly: what, which channel, ping on/off.
- All embeds send as Components V2 automatically.
"""

_client = None

def get_client():
    # kept for compat; actual calls go through llm.py (gemini -> groq)
    return None


async def ask(prompt: str, guild, author_is_admin: bool, context: dict, origin=None, author=None):
    """Run the agentic loop. Returns (reply_text, created_roles).

    reply_text is None when ALL providers fail — caller decides:
    - direct ping (bot.py) -> user-facing hiccup message
    - passive watchdog -> stay silent, send nothing
    """

    messages = [
        {"role": "system", "content": SYSTEM},
        {
            "role": "user",
            "content": (
                f"Server: {context['guild_name']} | Channel: #{context['channel_name']} | "
                f"From: {context['author']} (admin={author_is_admin})\n"
                f"Config: {context.get('server_config', 'n/a')}\n"
                f"Recent chat:\n" + "\n".join(context["recent_chat"][-10:]) +
                f"\n\nRequest: {prompt}"
            ),
        },
    ]

    created_roles = []

    for _ in range(8):
        try:
            content, tool_calls, _provider = await llm.chat(
                messages,
                tools=TOOLS_SCHEMA,
                tool_choice="auto",
                temperature=0.7,
                max_tokens=3000,
                groq_model=GROQ_MODEL,
            )
        except Exception as e:
            print(f"LLM error (gemini+groq): {type(e).__name__}: {str(e)[:200]}")
            return None, created_roles

        if not tool_calls:
            return content or "done — check the server.", created_roles

        messages.append({
            "role": "assistant",
            "content": content,
            "tool_calls": [
                {
                    "id": tc["id"],
                    "type": "function",
                    "function": {
                        "name": tc["name"],
                        "arguments": tc["arguments"],
                    },
                }
                for tc in tool_calls
            ],
        })

        for tc in tool_calls:
            try:
                args = json.loads(tc["arguments"] or "{}")
            except Exception:
                args = {}
            result_text, new_roles = await run_tool(
                tc["name"], args, guild, author_is_admin, origin, author
            )
            created_roles.extend(new_roles)
            messages.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": result_text[:1500],
            })

    return "I did what I could, some steps hit the limit. Ping me again to continue.", created_roles
