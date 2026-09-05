"""Everything Vibe can do on a server, exposed as tools for the AI.

Reads are open to everyone. Anything that changes the server needs an admin.
"""
import json
import os
import datetime
import discord

NOTES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "notes.json")

# ---------- descriptions (kept short so the AI stays fast) ----------

READ_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_members",
            "description": "List server members with display names, usernames and IDs. Use this to find who is who.",
            "parameters": {
                "type": "object",
                "properties": {
                    "search": {"type": "string", "description": "Optional name filter"},
                    "role": {"type": "string", "description": "Optional role name filter"},
                    "limit": {"type": "integer", "description": "Max results, default 20"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "member_info",
            "description": "Full details on one member: nickname, ID, roles, join date, timeout status.",
            "parameters": {
                "type": "object",
                "properties": {"member": {"type": "string"}},
                "required": ["member"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "recent_messages",
            "description": "Read recent messages from a text channel.",
            "parameters": {
                "type": "object",
                "properties": {
                    "channel": {"type": "string", "description": "Channel name, omit for current channel"},
                    "limit": {"type": "integer", "description": "How many, default 10, max 25"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "server_info",
            "description": "Server overview: owner, member/channel/role counts, boosts, emojis, age.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_roles",
            "description": "List all roles with names and IDs",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_channels",
            "description": "List all channels and categories with names and IDs",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "member_avatar",
            "description": "Get a member's profile picture / avatar link.",
            "parameters": {
                "type": "object",
                "properties": {"member": {"type": "string"}},
                "required": ["member"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_notes",
            "description": "Show things I remembered about this server.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]

WRITE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "set_nickname",
            "description": "Change a member's nickname. Empty nickname resets it.",
            "parameters": {
                "type": "object",
                "properties": {
                    "member": {"type": "string"},
                    "nickname": {"type": "string"},
                },
                "required": ["member", "nickname"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "timeout_member",
            "description": "Timeout a member so they can't chat. Minutes, max 40320.",
            "parameters": {
                "type": "object",
                "properties": {
                    "member": {"type": "string"},
                    "minutes": {"type": "integer"},
                    "reason": {"type": "string"},
                },
                "required": ["member", "minutes"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "untimeout_member",
            "description": "Remove a member's timeout early.",
            "parameters": {
                "type": "object",
                "properties": {"member": {"type": "string"}},
                "required": ["member"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "kick_member",
            "description": "Kick a member from the server.",
            "parameters": {
                "type": "object",
                "properties": {
                    "member": {"type": "string"},
                    "reason": {"type": "string"},
                },
                "required": ["member"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ban_member",
            "description": "Ban a member. delete_days optionally wipes recent messages (0-7).",
            "parameters": {
                "type": "object",
                "properties": {
                    "member": {"type": "string"},
                    "reason": {"type": "string"},
                    "delete_days": {"type": "integer"},
                },
                "required": ["member"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "unban_member",
            "description": "Unban someone by username or user ID.",
            "parameters": {
                "type": "object",
                "properties": {"user": {"type": "string"}},
                "required": ["user"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "move_voice",
            "description": "Move a member to a voice channel, or 'disconnect' to drop them.",
            "parameters": {
                "type": "object",
                "properties": {
                    "member": {"type": "string"},
                    "channel": {"type": "string"},
                },
                "required": ["member", "channel"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "voice_state",
            "description": "Server mute/deafen a member in voice.",
            "parameters": {
                "type": "object",
                "properties": {
                    "member": {"type": "string"},
                    "mute": {"type": "boolean"},
                    "deafen": {"type": "boolean"},
                },
                "required": ["member"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_role",
            "description": "Create a new role",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "color": {"type": "string", "description": "Hex like #A78BFA"},
                    "hoist": {"type": "boolean"},
                    "mentionable": {"type": "boolean"},
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "edit_role",
            "description": "Rename, recolor or toggle a role.",
            "parameters": {
                "type": "object",
                "properties": {
                    "role": {"type": "string"},
                    "name": {"type": "string"},
                    "color": {"type": "string"},
                    "hoist": {"type": "boolean"},
                    "mentionable": {"type": "boolean"},
                },
                "required": ["role"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_role",
            "description": "Delete a role.",
            "parameters": {
                "type": "object",
                "properties": {"role": {"type": "string"}},
                "required": ["role"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "assign_role",
            "description": "Give a role to a member. Both accept name or ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "member": {"type": "string"},
                    "role": {"type": "string"},
                },
                "required": ["member", "role"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "remove_role",
            "description": "Remove a role from a member",
            "parameters": {
                "type": "object",
                "properties": {
                    "member": {"type": "string"},
                    "role": {"type": "string"},
                },
                "required": ["member", "role"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_category",
            "description": "Create a channel category",
            "parameters": {
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_text_channel",
            "description": "Create a text channel, optionally in a category",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "topic": {"type": "string"},
                    "category": {"type": "string", "description": "Category name"},
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_voice_channel",
            "description": "Create a voice channel, optionally in a category",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "category": {"type": "string"},
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "rename_channel",
            "description": "Rename any channel or category.",
            "parameters": {
                "type": "object",
                "properties": {
                    "channel": {"type": "string"},
                    "new_name": {"type": "string"},
                },
                "required": ["channel", "new_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_topic",
            "description": "Set a text channel's topic/description.",
            "parameters": {
                "type": "object",
                "properties": {
                    "channel": {"type": "string"},
                    "topic": {"type": "string"},
                },
                "required": ["channel", "topic"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_slowmode",
            "description": "Set slowmode delay on a text channel, 0-21600 seconds.",
            "parameters": {
                "type": "object",
                "properties": {
                    "channel": {"type": "string"},
                    "seconds": {"type": "integer"},
                },
                "required": ["channel", "seconds"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lock_channel",
            "description": "Lock a text channel so regular members can't send messages.",
            "parameters": {
                "type": "object",
                "properties": {"channel": {"type": "string"}},
                "required": ["channel"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "unlock_channel",
            "description": "Unlock a locked text channel.",
            "parameters": {
                "type": "object",
                "properties": {"channel": {"type": "string"}},
                "required": ["channel"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_channel",
            "description": "Delete a channel or category.",
            "parameters": {
                "type": "object",
                "properties": {"channel": {"type": "string"}},
                "required": ["channel"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "purge",
            "description": "Bulk delete recent messages from a channel. Max 50 at once.",
            "parameters": {
                "type": "object",
                "properties": {
                    "channel": {"type": "string", "description": "Omit for current channel"},
                    "limit": {"type": "integer"},
                },
                "required": ["limit"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_message",
            "description": "Send a message to a specific channel as the bot.",
            "parameters": {
                "type": "object",
                "properties": {
                    "channel": {"type": "string", "description": "Omit for current channel"},
                    "text": {"type": "string"},
                },
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_poll",
            "description": "Post a poll with 2-4 options. Runs for 24 hours.",
            "parameters": {
                "type": "object",
                "properties": {
                    "channel": {"type": "string", "description": "Omit for current channel"},
                    "question": {"type": "string"},
                    "options": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "2 to 4 choices",
                    },
                },
                "required": ["question", "options"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_invite",
            "description": "Make a server invite link for a channel. max_uses 0 = unlimited.",
            "parameters": {
                "type": "object",
                "properties": {
                    "channel": {"type": "string", "description": "Omit for current channel"},
                    "max_age_hours": {"type": "integer", "description": "Link expiry, 0 = never"},
                    "max_uses": {"type": "integer"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_note",
            "description": "Remember something about this server for later (rules, vibes, birthdays...).",
            "parameters": {
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_note",
            "description": "Forget a saved note by its number.",
            "parameters": {
                "type": "object",
                "properties": {"number": {"type": "integer"}},
                "required": ["number"],
            },
        },
    },
]

TOOLS_SCHEMA = READ_TOOLS + WRITE_TOOLS
WRITE_NAMES = {t["function"]["name"] for t in WRITE_TOOLS}
OPEN_WRITES = {"save_note", "delete_note"}  # harmless, anyone can use


# ---------- finders ----------

def _clean_mention(query):
    return str(query).strip().replace("@", "").replace("<", "").replace(">", "").replace("!", "")


def _find_role(guild, query):
    q = str(query).lower().strip()
    for r in guild.roles:
        if str(r.id) == q or r.name.lower() == q:
            return r
    for r in guild.roles:
        if q in r.name.lower():
            return r
    return None


def _find_member(guild, query):
    q = _clean_mention(query).lower()
    if not q:
        return None
    for m in guild.members:
        if str(m.id) == q or m.name.lower() == q or m.display_name.lower() == q:
            return m
    for m in guild.members:
        if q in m.name.lower() or q in m.display_name.lower():
            return m
    return None


def _find_channel(guild, query):
    q = str(query).lower().strip().lstrip("#")
    if not q:
        return None
    for ch in guild.channels:
        if str(ch.id) == q or ch.name.lower() == q:
            return ch
    for ch in guild.channels:
        if q in ch.name.lower():
            return ch
    return None


def _find_text_channel(guild, query):
    ch = _find_channel(guild, query)
    return ch if isinstance(ch, discord.TextChannel) else None


def _find_voice_channel(guild, query):
    q = str(query).lower().strip()
    for ch in guild.voice_channels:
        if str(ch.id) == q or ch.name.lower() == q:
            return ch
    for ch in guild.voice_channels:
        if q in ch.name.lower():
            return ch
    return None


def _find_category(guild, name):
    for c in guild.categories:
        if c.name.lower() == str(name).lower():
            return c
    return None


def _parse_color(hex_str):
    try:
        return discord.Color(int(str(hex_str).lstrip("#"), 16))
    except Exception:
        return discord.Color.default()


def _manageable(guild, member):
    """Can the bot actually touch this member? Returns (ok, reason)."""
    me = guild.me
    if member.id == guild.owner_id:
        return False, "that's the server owner, I can't touch them."
    if member.id == me.id:
        return False, "that's me, leave me alone."
    if member.top_role >= me.top_role:
        return False, f"{member.display_name} outranks me — move my role above theirs."
    return True, ""


# ---------- memory ----------

def _load_notes():
    try:
        with open(NOTES_FILE) as f:
            return json.load(f)
    except Exception:
        return {}


def _save_notes(data):
    try:
        with open(NOTES_FILE, "w") as f:
            json.dump(data, f)
    except Exception:
        pass


# ---------- main entry ----------

async def run_tool(name, args, guild, author_is_admin, origin=None):
    """Returns (result_text, created_roles). origin is the channel the ping came from."""
    if name in WRITE_NAMES and name not in OPEN_WRITES and not author_is_admin:
        return "Failed: that needs an admin. Ask an admin to ping me.", []

    if name not in {t["function"]["name"] for t in TOOLS_SCHEMA}:
        return f"Unknown tool: {name}", []

    try:
        return await _execute(name, args, guild, origin)
    except discord.Forbidden:
        return ("Failed: I don't have permission for that. "
                "Move my role to the top and give me the matching permission.", [])
    except discord.HTTPException as e:
        return f"Failed: Discord error ({e}). Try again in a bit.", []


async def _execute(name, args, guild, origin):
    # ----- reads -----
    if name == "list_members":
        members = [m for m in guild.members if not m.bot]
        if args.get("search"):
            q = args["search"].lower()
            members = [m for m in members if q in m.name.lower() or q in m.display_name.lower()]
        if args.get("role"):
            role = _find_role(guild, args["role"])
            if not role:
                return f"No role matching '{args['role']}'.", []
            members = [m for m in members if role in m.roles]
        limit = max(1, min(int(args.get("limit", 20)), 50))
        members = sorted(members, key=lambda m: m.display_name.lower())[:limit]
        if not members:
            return "No members matched.", []
        lines = []
        for m in members:
            nick = f" (nick: {m.nick})" if m.nick else ""
            lines.append(f"{m.display_name} @{m.name}{nick} — {m.id}")
        total = len([m for m in guild.members if not m.bot])
        return f"{len(lines)} shown / {total} humans:\n" + "\n".join(lines), []

    if name == "member_info":
        m = _find_member(guild, args["member"])
        if not m:
            return f"Couldn't find anyone matching '{args['member']}'.", []
        roles = ", ".join(r.name for r in reversed(m.roles) if not r.is_default()) or "none"
        joined = m.joined_at.strftime("%Y-%m-%d") if m.joined_at else "?"
        created = m.created_at.strftime("%Y-%m-%d")
        timed = f"timed out until {m.timed_out_until:%Y-%m-%d %H:%M}" if m.timed_out_until else "no"
        boost = m.premium_since.strftime("%Y-%m-%d") if m.premium_since else "no"
        return (f"{m.display_name} (@{m.name}) — {m.id}\n"
                f"Nick: {m.nick or 'none'} | Bot: {'yes' if m.bot else 'no'}\n"
                f"Joined server: {joined} | Account made: {created}\n"
                f"Roles: {roles}\nTimeout: {timed} | Boosting: {boost}"), []

    if name == "recent_messages":
        ch = _find_text_channel(guild, args["channel"]) if args.get("channel") else origin
        if not isinstance(ch, discord.TextChannel):
            return "Couldn't find that text channel.", []
        limit = max(1, min(int(args.get("limit", 10)), 25))
        lines = []
        async for m in ch.history(limit=limit):
            if len(m.content) > 250:
                continue
            lines.append(f"{m.author.display_name}: {m.content or '[attachment/embed]'}")
        lines.reverse()
        return f"Last {len(lines)} in #{ch.name}:\n" + "\n".join(lines) or "Channel is empty.", []

    if name == "server_info":
        o = guild.owner.display_name if guild.owner else "?"
        humans = len([m for m in guild.members if not m.bot])
        bots = len([m for m in guild.members if m.bot])
        emojis = len(guild.emojis)
        made = guild.created_at.strftime("%Y-%m-%d")
        return (f"{guild.name} (ID {guild.id})\nOwner: {o} | Made: {made}\n"
                f"Members: {humans} humans + {bots} bots\n"
                f"Channels: {len(guild.channels)} | Roles: {len(guild.roles)} | Emojis: {emojis}\n"
                f"Boosts: {guild.premium_subscription_count} (level {guild.premium_tier})"), []

    if name == "list_roles":
        out = "\n".join(f"{r.name} — {r.id} ({len(r.members)} members)"
                        for r in guild.roles if not r.is_default())
        return out or "No custom roles yet.", []

    if name == "list_channels":
        lines = []
        for c in guild.categories:
            lines.append(f"[category] {c.name} — {c.id}")
            for ch in c.channels:
                lines.append(f"  #{ch.name} ({type(ch).__name__}) — {ch.id}")
        for ch in guild.channels:
            if not ch.category:
                lines.append(f"#{ch.name} ({type(ch).__name__}) — {ch.id}")
        return "\n".join(lines) or "No channels.", []

    if name == "list_notes":
        notes = _load_notes().get(str(guild.id), [])
        if not notes:
            return "No notes saved for this server yet.", []
        return "\n".join(f"{n['id']}. {n['text']}" for n in notes), []

    # ----- member management -----
    if name == "set_nickname":
        m = _find_member(guild, args["member"])
        if not m:
            return f"Couldn't find anyone matching '{args['member']}'.", []
        ok, why = _manageable(guild, m)
        if not ok:
            return f"Failed: {why}", []
        nick = args["nickname"].strip()[:32]
        await m.edit(nick=nick or None, reason="Vibe bot")
        return f"{'Cleared' if not nick else f'Set nick to {nick} for'} {m.display_name}.", []

    if name == "timeout_member":
        m = _find_member(guild, args["member"])
        if not m:
            return f"Couldn't find anyone matching '{args['member']}'.", []
        ok, why = _manageable(guild, m)
        if not ok:
            return f"Failed: {why}", []
        minutes = max(1, min(int(args["minutes"]), 40320))
        await m.timeout(datetime.timedelta(minutes=minutes), reason=args.get("reason", "Vibe bot")[:200])
        return f"Timed out {m.display_name} for {minutes} min.", []

    if name == "untimeout_member":
        m = _find_member(guild, args["member"])
        if not m:
            return f"Couldn't find anyone matching '{args['member']}'.", []
        await m.timeout(None, reason="Vibe bot")
        return f"Removed timeout from {m.display_name}.", []

    if name == "kick_member":
        m = _find_member(guild, args["member"])
        if not m:
            return f"Couldn't find anyone matching '{args['member']}'.", []
        ok, why = _manageable(guild, m)
        if not ok:
            return f"Failed: {why}", []
        await m.kick(reason=args.get("reason", "Vibe bot")[:200])
        return f"Kicked {m.display_name}.", []

    if name == "ban_member":
        m = _find_member(guild, args["member"])
        if not m:
            return f"Couldn't find anyone matching '{args['member']}'.", []
        ok, why = _manageable(guild, m)
        if not ok:
            return f"Failed: {why}", []
        days = max(0, min(int(args.get("delete_days", 0)), 7))
        await guild.ban(m, reason=args.get("reason", "Vibe bot")[:200], delete_message_days=days)
        return f"Banned {m.display_name}.", []

    if name == "unban_member":
        q = _clean_mention(args["user"]).lower()
        async for entry in guild.bans():
            u = entry.user
            if str(u.id) == q or u.name.lower() == q or f"{u.name}".lower() == q:
                await guild.unban(u, reason="Vibe bot")
                return f"Unbanned {u.name}.", []
        return f"No banned user matching '{args['user']}'.", []

    if name == "move_voice":
        m = _find_member(guild, args["member"])
        if not m:
            return f"Couldn't find anyone matching '{args['member']}'.", []
        ok, why = _manageable(guild, m)
        if not ok:
            return f"Failed: {why}", []
        target = str(args["channel"]).lower().strip()
        if target in {"disconnect", "none", "kick"}:
            await m.move_to(None, reason="Vibe bot")
            return f"Disconnected {m.display_name} from voice.", []
        vc = _find_voice_channel(guild, args["channel"])
        if not vc:
            return f"No voice channel matching '{args['channel']}'.", []
        await m.move_to(vc, reason="Vibe bot")
        return f"Moved {m.display_name} to {vc.name}.", []

    if name == "voice_state":
        m = _find_member(guild, args["member"])
        if not m:
            return f"Couldn't find anyone matching '{args['member']}'.", []
        ok, why = _manageable(guild, m)
        if not ok:
            return f"Failed: {why}", []
        await m.edit(mute=args.get("mute"), deafen=args.get("deafen"), reason="Vibe bot")
        bits = []
        if args.get("mute") is not None:
            bits.append("muted" if args["mute"] else "unmuted")
        if args.get("deafen") is not None:
            bits.append("deafened" if args["deafen"] else "undeafened")
        return f"{m.display_name}: {' + '.join(bits) or 'no change'}.", []

    # ----- roles -----
    if name == "create_role":
        if len(guild.roles) >= 240:
            return "Failed: role limit reached.", []
        role = await guild.create_role(
            name=args["name"][:100],
            colour=_parse_color(args.get("color", "#99AAB5")),
            hoist=bool(args.get("hoist", False)),
            mentionable=bool(args.get("mentionable", False)),
            reason="Vibe bot",
        )
        return f"Created role {role.name} with ID {role.id}.", [role]

    if name == "edit_role":
        role = _find_role(guild, args["role"])
        if not role:
            return f"No role matching '{args['role']}'.", []
        patch = {}
        if args.get("name"):
            patch["name"] = args["name"][:100]
        if args.get("color"):
            patch["colour"] = _parse_color(args["color"])
        if args.get("hoist") is not None:
            patch["hoist"] = bool(args["hoist"])
        if args.get("mentionable") is not None:
            patch["mentionable"] = bool(args["mentionable"])
        if not patch:
            return "Nothing to change — give me a name, color, hoist or mentionable.", []
        await role.edit(reason="Vibe bot", **patch)
        return f"Updated role {role.name} ({role.id}).", []

    if name == "delete_role":
        role = _find_role(guild, args["role"])
        if not role:
            return f"No role matching '{args['role']}'.", []
        if role.is_default() or role.managed:
            return "Failed: can't delete @everyone or bot-managed roles.", []
        await role.delete(reason="Vibe bot")
        return f"Deleted role {role.name}.", []

    if name == "assign_role":
        member = _find_member(guild, args["member"])
        role = _find_role(guild, args["role"])
        if not member:
            return f"Failed: couldn't find member '{args['member']}'.", []
        if not role:
            return f"Failed: couldn't find role '{args['role']}'.", []
        await member.add_roles(role, reason="Vibe bot")
        return f"Gave {role.name} ({role.id}) to {member.display_name}.", []

    if name == "remove_role":
        member = _find_member(guild, args["member"])
        role = _find_role(guild, args["role"])
        if not member or not role:
            return "Failed: member or role not found.", []
        await member.remove_roles(role, reason="Vibe bot")
        return f"Removed {role.name} from {member.display_name}.", []

    # ----- channels -----
    if name == "create_category":
        cat = await guild.create_category(name=args["name"][:100], reason="Vibe bot")
        return f"Created category {cat.name} ({cat.id}).", []

    if name == "create_text_channel":
        cat = _find_category(guild, args.get("category", "")) if args.get("category") else None
        ch = await guild.create_text_channel(
            name=args["name"][:100].lower().replace(" ", "-"),
            topic=args.get("topic", "")[:250],
            category=cat,
            reason="Vibe bot",
        )
        return f"Created text channel #{ch.name} ({ch.id}).", []

    if name == "create_voice_channel":
        cat = _find_category(guild, args.get("category", "")) if args.get("category") else None
        ch = await guild.create_voice_channel(
            name=args["name"][:100],
            category=cat,
            reason="Vibe bot",
        )
        return f"Created voice channel {ch.name} ({ch.id}).", []

    if name == "rename_channel":
        ch = _find_channel(guild, args["channel"])
        if not ch:
            return f"No channel matching '{args['channel']}'.", []
        new = args["new_name"][:100]
        if isinstance(ch, discord.TextChannel):
            new = new.lower().replace(" ", "-")
        await ch.edit(name=new, reason="Vibe bot")
        return f"Renamed to {new}.", []

    if name == "set_topic":
        ch = _find_text_channel(guild, args["channel"])
        if not ch:
            return f"No text channel matching '{args['channel']}'.", []
        await ch.edit(topic=args["topic"][:250], reason="Vibe bot")
        return f"Set topic on #{ch.name}.", []

    if name == "set_slowmode":
        ch = _find_text_channel(guild, args["channel"])
        if not ch:
            return f"No text channel matching '{args['channel']}'.", []
        secs = max(0, min(int(args["seconds"]), 21600))
        await ch.edit(slowmode_delay=secs, reason="Vibe bot")
        return f"Slowmode on #{ch.name}: {secs}s.", []

    if name == "lock_channel":
        ch = _find_text_channel(guild, args["channel"])
        if not ch:
            return f"No text channel matching '{args['channel']}'.", []
        await ch.set_permissions(guild.default_role, send_messages=False, reason="Vibe bot")
        return f"Locked #{ch.name}.", []

    if name == "unlock_channel":
        ch = _find_text_channel(guild, args["channel"])
        if not ch:
            return f"No text channel matching '{args['channel']}'.", []
        await ch.set_permissions(guild.default_role, send_messages=None, reason="Vibe bot")
        return f"Unlocked #{ch.name}.", []

    if name == "delete_channel":
        ch = _find_channel(guild, args["channel"])
        if not ch:
            return f"No channel matching '{args['channel']}'.", []
        await ch.delete(reason="Vibe bot")
        return f"Deleted {ch.name}.", []

    if name == "purge":
        ch = _find_text_channel(guild, args["channel"]) if args.get("channel") else origin
        if not isinstance(ch, discord.TextChannel):
            return "Couldn't find that text channel.", []
        limit = max(1, min(int(args["limit"]), 50))
        deleted = await ch.purge(limit=limit)
        return f"Deleted {len(deleted)} messages in #{ch.name}.", []

    # ----- messages & fun -----
    if name == "send_message":
        ch = _find_text_channel(guild, args["channel"]) if args.get("channel") else origin
        if not isinstance(ch, discord.TextChannel):
            return "Couldn't find that text channel.", []
        await ch.send(args["text"][:1900])
        return f"Sent to #{ch.name}.", []

    if name == "create_poll":
        ch = _find_text_channel(guild, args["channel"]) if args.get("channel") else origin
        if not isinstance(ch, discord.TextChannel):
            return "Couldn't find that text channel.", []
        options = [o.strip()[:55] for o in args["options"] if o.strip()][:4]
        if len(options) < 2:
            return "Need at least 2 poll options.", []
        poll = discord.Poll(args["question"][:300], datetime.timedelta(hours=24))
        for o in options:
            poll.add_answer(text=o)
        await ch.send(poll=poll)
        return f"Posted poll in #{ch.name}: {args['question'][:100]}", []

    if name == "create_invite":
        ch = _find_text_channel(guild, args["channel"]) if args.get("channel") else origin
        if ch is None and args.get("channel"):
            ch = _find_voice_channel(guild, args["channel"])
        if ch is None:
            ch = origin
        if ch is None:
            return "Couldn't find that channel.", []
        age = max(0, min(int(args.get("max_age_hours", 24)), 168)) * 3600
        uses = max(0, min(int(args.get("max_uses", 0)), 100))
        inv = await ch.create_invite(max_age=age, max_uses=uses, reason="Vibe bot")
        return f"Invite for #{ch.name}: {inv.url}", []

    if name == "member_avatar":
        m = _find_member(guild, args["member"])
        if not m:
            return f"Couldn't find anyone matching '{args['member']}'.", []
        pic = m.display_avatar.url
        return f"{m.display_name}'s avatar: {pic}", []

    # ----- memory -----
    if name == "save_note":
        data = _load_notes()
        notes = data.get(str(guild.id), [])
        if len(notes) >= 30:
            return "Memory full (30 notes). Delete one first.", []
        nid = max([n["id"] for n in notes], default=0) + 1
        notes.append({"id": nid, "text": args["text"][:300]})
        data[str(guild.id)] = notes
        _save_notes(data)
        return f"Noted #{nid}.", []

    if name == "delete_note":
        data = _load_notes()
        notes = data.get(str(guild.id), [])
        kept = [n for n in notes if n["id"] != int(args["number"])]
        if len(kept) == len(notes):
            return f"No note #{args['number']}.", []
        data[str(guild.id)] = kept
        _save_notes(data)
        return f"Forgot note #{args['number']}.", []

    return f"Unknown tool: {name}", []
