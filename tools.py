import discord

TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "list_roles",
            "description": "List all roles in the server with names and IDs",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_channels",
            "description": "List all channels and categories in the server",
            "parameters": {"type": "object", "properties": {}},
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
]


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
    q = str(query).lower().strip().replace("@", "").replace("<", "").replace(">", "").replace("!", "")
    for m in guild.members:
        if str(m.id) == q or m.name.lower() == q or m.display_name.lower() == q:
            return m
    for m in guild.members:
        if q in m.name.lower() or q in m.display_name.lower():
            return m
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


async def run_tool(name, args, guild, author_is_admin):
    """Returns (result_text, created_roles)."""
    if name in {"create_role", "create_category", "create_text_channel",
                "create_voice_channel", "assign_role", "remove_role"}:
        if not author_is_admin:
            return "Failed: that needs an admin. Ask an admin to ping me.", []

    try:
        if name == "list_roles":
            out = "\n".join(f"{r.name} — {r.id}" for r in guild.roles if not r.is_default())
            return out or "No custom roles yet.", []

        if name == "list_channels":
            lines = []
            for c in guild.categories:
                lines.append(f"[category] {c.name}")
                for ch in c.channels:
                    lines.append(f"  #{ch.name} ({type(ch).__name__})")
            for ch in guild.channels:
                if not ch.category:
                    lines.append(f"#{ch.name} ({type(ch).__name__})")
            return "\n".join(lines) or "No channels.", []

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

        return f"Unknown tool: {name}", []

    except discord.Forbidden:
        return "Failed: I don't have permission. Move my role to the top and give me Manage Channels + Manage Roles.", []
    except discord.HTTPException as e:
        return f"Failed: Discord rate limit or error ({e}). Try again in a bit.", []
