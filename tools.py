"""Everything Vibe can do on a server, exposed as tools for the AI.

Reads are open to everyone. Anything that changes the server needs an admin.
"""
import json
import os
import asyncio
import random
import datetime
import re
import discord

import settings as cfg
from ui import send_v2

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
    # ----- staff: warns -----
    {
        "type": "function",
        "function": {
            "name": "warn_member",
            "description": "Warn a member (staff action). 3 warns = suggest timeout. Logged per server.",
            "parameters": {
                "type": "object",
                "properties": {
                    "member": {"type": "string"},
                    "reason": {"type": "string"},
                },
                "required": ["member", "reason"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_warnings",
            "description": "Show all warnings for a member.",
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
            "name": "clear_warnings",
            "description": "Clear all warnings for a member.",
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
            "name": "clear_user",
            "description": "Delete up to 50 recent messages from one user in a channel.",
            "parameters": {
                "type": "object",
                "properties": {
                    "member": {"type": "string"},
                    "channel": {"type": "string", "description": "Omit for current channel"},
                    "limit": {"type": "integer", "description": "Max to scan, default 50"},
                },
                "required": ["member"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lock_all",
            "description": "Lock ALL text channels at once (raid / lockdown mode).",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "unlock_all",
            "description": "Unlock ALL text channels after a lockdown.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    # ----- embeds -----
    {
        "type": "function",
        "function": {
            "name": "send_embed",
            "description": "Send a rich embed to a channel. Use for announcements, rules, welcomes, giveaways. Supports {member} {server} {count} placeholders.",
            "parameters": {
                "type": "object",
                "properties": {
                    "channel": {"type": "string", "description": "Channel name, omit for current"},
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "color": {"type": "string", "description": "Hex like #A78BFA"},
                    "footer": {"type": "string"},
                    "image": {"type": "string", "description": "Image URL"},
                    "thumbnail": {"type": "string", "description": "Thumbnail URL"},
                    "ping_everyone": {"type": "boolean"},
                },
                "required": ["description"],
            },
        },
    },
    # ----- automod -----
    {
        "type": "function",
        "function": {
            "name": "set_antispam",
            "description": "Enable or disable anti-spam for this server.",
            "parameters": {
                "type": "object",
                "properties": {"enabled": {"type": "boolean"}},
                "required": ["enabled"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_antiswear",
            "description": "Enable or disable anti-swear filter for this server.",
            "parameters": {
                "type": "object",
                "properties": {"enabled": {"type": "boolean"}},
                "required": ["enabled"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_filtered_word",
            "description": "Add a custom word to the swear/blocked list.",
            "parameters": {
                "type": "object",
                "properties": {"word": {"type": "string"}},
                "required": ["word"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "remove_filtered_word",
            "description": "Remove a custom word from the blocked list.",
            "parameters": {
                "type": "object",
                "properties": {"word": {"type": "string"}},
                "required": ["word"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "show_config",
            "description": "Show this server's Vibe config: antispam, antiswear, welcome, goodbye, autorole, log channel.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    # ----- welcome / goodbye / autorole / logs -----
    {
        "type": "function",
        "function": {
            "name": "setup_welcome",
            "description": "Enable welcome messages. Example: channel=#welcome message='welcome to my server {member}' ping=false embed=true",
            "parameters": {
                "type": "object",
                "properties": {
                    "channel": {"type": "string"},
                    "message": {"type": "string", "description": "Supports {member} {server} {count}"},
                    "ping": {"type": "boolean", "description": "Ping the newcomer? default false"},
                    "use_embed": {"type": "boolean", "description": "Send as embed? default true"},
                },
                "required": ["channel", "message"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "disable_welcome",
            "description": "Turn off welcome messages.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "setup_goodbye",
            "description": "Enable goodbye messages when members leave.",
            "parameters": {
                "type": "object",
                "properties": {
                    "channel": {"type": "string"},
                    "message": {"type": "string"},
                },
                "required": ["channel", "message"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "setup_autorole",
            "description": "Auto-give a role to everyone who joins. Use role name or 'off' to disable.",
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
            "name": "setup_log",
            "description": "Set a mod-log channel for warns/timeouts/joins, or 'off' to disable.",
            "parameters": {
                "type": "object",
                "properties": {"channel": {"type": "string"}},
                "required": ["channel"],
            },
        },
    },
    # ----- giveaways -----
    {
        "type": "function",
        "function": {
            "name": "start_giveaway",
            "description": "Start a giveaway. mode=first (whoever reacts first wins instantly) or mode=timed (random winner after minutes).",
            "parameters": {
                "type": "object",
                "properties": {
                    "channel": {"type": "string", "description": "Omit for current channel"},
                    "prize": {"type": "string"},
                    "winners": {"type": "integer", "description": "How many winners, default 1"},
                    "minutes": {"type": "integer", "description": "For timed mode, default 60"},
                    "mode": {"type": "string", "description": "'first' or 'timed', default timed"},
                },
                "required": ["prize"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "end_giveaway",
            "description": "End a giveaway early and pick winner(s) by message ID.",
            "parameters": {
                "type": "object",
                "properties": {"message_id": {"type": "string"}},
                "required": ["message_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "reroll_giveaway",
            "description": "Pick a new winner for an ended giveaway by message ID.",
            "parameters": {
                "type": "object",
                "properties": {"message_id": {"type": "string"}},
                "required": ["message_id"],
            },
        },
    },
    # ----- tickets -----
    {
        "type": "function",
        "function": {
            "name": "setup_tickets",
            "description": "Set the category where support ticket channels are created. Then 'open ticket for X' makes a private channel.",
            "parameters": {
                "type": "object",
                "properties": {"category": {"type": "string"}},
                "required": ["category"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_ticket",
            "description": "Open a private support ticket channel for a member.",
            "parameters": {
                "type": "object",
                "properties": {
                    "member": {"type": "string"},
                    "topic": {"type": "string"},
                },
                "required": ["member"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "close_ticket",
            "description": "Close/delete the current ticket channel (run inside the ticket).",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ticket_add",
            "description": "Add a member to the current ticket channel (run inside the ticket).",
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
            "name": "ticket_remove",
            "description": "Remove a member from the current ticket channel (run inside the ticket).",
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
            "name": "ticket_transcript",
            "description": "Save this ticket's history as a transcript file to the log channel, then close it.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "tempban",
            "description": "Ban a member for N minutes, then auto-unban. e.g. minutes=60.",
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
            "name": "temprole",
            "description": "Give a role for N minutes, then auto-remove. e.g. minutes=60.",
            "parameters": {
                "type": "object",
                "properties": {
                    "member": {"type": "string"},
                    "role": {"type": "string"},
                    "minutes": {"type": "integer"},
                },
                "required": ["member", "role", "minutes"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "level_role_add",
            "description": "Auto-give a role when a member hits an XP level. e.g. level=5 role=Veteran.",
            "parameters": {
                "type": "object",
                "properties": {
                    "level": {"type": "integer"},
                    "role": {"type": "string"},
                },
                "required": ["level", "role"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "level_role_remove",
            "description": "Remove an XP level reward role.",
            "parameters": {
                "type": "object",
                "properties": {"level": {"type": "integer"}},
                "required": ["level"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "level_roles_list",
            "description": "List all XP level reward roles.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "verify_setup",
            "description": "Gate new joins: newcomers get this role until staff approve them (use assign_role to approve).",
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
            "name": "verify_off",
            "description": "Turn off the new-member verification gate.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "antiraid",
            "description": "Auto-lockdown when >5 joins hit within 30s. Use mode='on' or 'off'.",
            "parameters": {
                "type": "object",
                "properties": {"mode": {"type": "string"}},
                "required": ["mode"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "report",
            "description": "Report a member to mods — posts to the log channel with reason.",
            "parameters": {
                "type": "object",
                "properties": {
                    "member": {"type": "string"},
                    "reason": {"type": "string"},
                },
                "required": ["member", "reason"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "snipe",
            "description": "Show the last deleted message in this channel (or a named channel).",
            "parameters": {
                "type": "object",
                "properties": {"channel": {"type": "string"}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "welcome_test",
            "description": "Preview the welcome message right here without a new join.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    # ----- reaction roles -----
    {
        "type": "function",
        "function": {
            "name": "add_reaction_role",
            "description": "When users react with emoji on a message, they get the role. Give message ID, emoji, role.",
            "parameters": {
                "type": "object",
                "properties": {
                    "message_id": {"type": "string"},
                    "emoji": {"type": "string"},
                    "role": {"type": "string"},
                },
                "required": ["message_id", "emoji", "role"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "remove_reaction_role",
            "description": "Remove a reaction-role binding.",
            "parameters": {
                "type": "object",
                "properties": {
                    "message_id": {"type": "string"},
                    "emoji": {"type": "string"},
                },
                "required": ["message_id", "emoji"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_reaction_roles",
            "description": "List all reaction-role bindings on this server.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    # ----- bans / emojis -----
    {
        "type": "function",
        "function": {
            "name": "list_bans",
            "description": "List banned users with reasons.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "hackban",
            "description": "Ban a user ID who isn't in the server.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "string"},
                    "reason": {"type": "string"},
                },
                "required": ["user_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "softban",
            "description": "Ban then instantly unban to wipe messages (kick + clean).",
            "parameters": {
                "type": "object",
                "properties": {
                    "member": {"type": "string"},
                    "delete_days": {"type": "integer"},
                },
                "required": ["member"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_emojis",
            "description": "List server emojis with IDs.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_emoji",
            "description": "Create a server emoji from an image URL.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "url": {"type": "string"},
                },
                "required": ["name", "url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_emoji",
            "description": "Delete a server emoji by name.",
            "parameters": {
                "type": "object",
                "properties": {"emoji": {"type": "string"}},
                "required": ["emoji"],
            },
        },
    },
    # ----- info -----
    {
        "type": "function",
        "function": {
            "name": "role_info",
            "description": "Details on a role: members, color, permissions, position.",
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
            "name": "channel_info",
            "description": "Details on a channel: type, topic, slowmode, category.",
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
            "name": "bot_stats",
            "description": "Bot uptime, latency, server count.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "help_panel",
            "description": "Post a help panel listing what Vibe can do.",
            "parameters": {
                "type": "object",
                "properties": {"channel": {"type": "string"}},
            },
        },
    },
    # ----- voice mass -----
    {
        "type": "function",
        "function": {
            "name": "move_all_voice",
            "description": "Move everyone from one voice channel to another.",
            "parameters": {
                "type": "object",
                "properties": {
                    "from": {"type": "string"},
                    "to": {"type": "string"},
                },
                "required": ["from", "to"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "disconnect_all_voice",
            "description": "Disconnect everyone in a voice channel (or all if omitted).",
            "parameters": {
                "type": "object",
                "properties": {"channel": {"type": "string"}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "slowmode_all",
            "description": "Set slowmode on ALL text channels at once (0 to disable).",
            "parameters": {
                "type": "object",
                "properties": {"seconds": {"type": "integer"}},
                "required": ["seconds"],
            },
        },
    },
    # ----- reminders / announce -----
    {
        "type": "function",
        "function": {
            "name": "remind",
            "description": "Remind in this channel after N minutes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "minutes": {"type": "integer"},
                    "text": {"type": "string"},
                },
                "required": ["minutes", "text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "announce",
            "description": "Post a styled announcement embed, optionally pinging everyone.",
            "parameters": {
                "type": "object",
                "properties": {
                    "channel": {"type": "string"},
                    "title": {"type": "string"},
                    "text": {"type": "string"},
                    "ping_everyone": {"type": "boolean"},
                },
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_server",
            "description": "Rename server and/or set description.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                },
            },
        },
    },
    # ----- autoresponder / afk / xp -----
    {
        "type": "function",
        "function": {
            "name": "add_trigger",
            "description": "Auto-reply when someone says trigger. E.g. trigger=good morning response=Good morning!",
            "parameters": {
                "type": "object",
                "properties": {
                    "trigger": {"type": "string"},
                    "response": {"type": "string"},
                },
                "required": ["trigger", "response"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "remove_trigger",
            "description": "Delete an auto-response trigger.",
            "parameters": {
                "type": "object",
                "properties": {"trigger": {"type": "string"}},
                "required": ["trigger"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_triggers",
            "description": "List all auto-response triggers.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "afk_set",
            "description": "Mark yourself AFK with a reason. Anyone can use.",
            "parameters": {
                "type": "object",
                "properties": {"reason": {"type": "string"}},
                "required": ["reason"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "leaderboard",
            "description": "Top 10 most active members by XP.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "rank",
            "description": "Show XP level for a member (omit for requester context).",
            "parameters": {
                "type": "object",
                "properties": {"member": {"type": "string"}},
            },
        },
    },
    # ----- final 16 to hit 100 -----
    {
        "type": "function",
        "function": {
            "name": "nuke_channel",
            "description": "Wipe a channel clean by cloning + deleting it (raid cleanup).",
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
            "name": "clone_channel",
            "description": "Clone a channel with same perms/topic.",
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
            "name": "role_all",
            "description": "Give a role to ALL human members.",
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
            "name": "unrole_all",
            "description": "Remove a role from ALL members who have it.",
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
            "name": "list_timeouts",
            "description": "List all currently timed-out members.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "pin_message",
            "description": "Pin a message by ID in a channel (omit channel = current).",
            "parameters": {
                "type": "object",
                "properties": {
                    "message_id": {"type": "string"},
                    "channel": {"type": "string"},
                },
                "required": ["message_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_thread",
            "description": "Create a thread on the last message or a given message ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "message_id": {"type": "string"},
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "quickvote",
            "description": "Yes/No vote embed with ✅❌ reactions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "channel": {"type": "string"},
                    "question": {"type": "string"},
                },
                "required": ["question"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "dm_member",
            "description": "DM a member directly from the bot.",
            "parameters": {
                "type": "object",
                "properties": {
                    "member": {"type": "string"},
                    "text": {"type": "string"},
                },
                "required": ["member", "text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "setup_counter",
            "description": "Member-count voice channel (auto-updates). Use 'off' to disable.",
            "parameters": {
                "type": "object",
                "properties": {"name": {"type": "string", "description": "'off' or template like Members: {count}"}},
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_sticky",
            "description": "Sticky message reposted after every message in a channel.",
            "parameters": {
                "type": "object",
                "properties": {
                    "channel": {"type": "string"},
                    "text": {"type": "string"},
                },
                "required": ["channel", "text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "remove_sticky",
            "description": "Remove the sticky message from a channel.",
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
            "name": "massnick",
            "description": "Set nickname prefix for all members, e.g. prefix='VIBE | '.",
            "parameters": {
                "type": "object",
                "properties": {"prefix": {"type": "string"}},
                "required": ["prefix"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "reset_nicks",
            "description": "Reset ALL nicknames to default.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "server_icon",
            "description": "Show server icon / banner URLs.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_invites",
            "description": "List active invites with uses and creators.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]

TOOLS_SCHEMA = READ_TOOLS + WRITE_TOOLS
WRITE_NAMES = {t["function"]["name"] for t in WRITE_TOOLS}
OPEN_WRITES = {"save_note", "delete_note", "afk_set", "rank", "leaderboard", "report", "snipe"}  # harmless, anyone can use
START_TIME = datetime.datetime.now(datetime.timezone.utc)
_SNIPE: dict[str, dict] = {}  # "guild:channel" -> {who, text} last deleted message


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


# ---------- shared helpers for new staff features ----------

_bot = None  # set by bot.py so giveaways/logs can act

def set_bot(client):
    global _bot
    _bot = client


def _fmt(text, member=None, guild=None):
    t = str(text or "")
    if guild:
        t = t.replace("{server}", guild.name).replace("{count}", str(guild.member_count or 0))
    if member:
        try:
            t = t.replace("{member}", member.mention).replace("{user}", str(member)).replace("{name}", member.display_name)
        except Exception:
            pass
    return t


def _build_embed(title="", description="", color="#A78BFA", footer="", image="", thumbnail=""):
    try:
        col = int(str(color).lstrip("#"), 16)
    except Exception:
        col = 0xA78BFA
    e = discord.Embed(title=str(title or "")[:256], description=str(description or "")[:4000], color=col)
    if footer:
        e.set_footer(text=str(footer)[:200])
    if image and str(image).startswith("http"):
        e.set_image(url=str(image)[:500])
    if thumbnail and str(thumbnail).startswith("http"):
        e.set_thumbnail(url=str(thumbnail)[:500])
    return e


async def _log(guild, text):
    try:
        s = cfg.get_settings(guild.id)
        name = s.get("log_channel", "")
        if not name or not _bot:
            return
        ch = _find_text_channel(guild, name)
        if ch:
            try:
                await send_v2(ch, "🛡️ Mod log", text, "#5865F2")
            except Exception:
                await ch.send(f"🛡️ {text}"[:1900])
    except Exception:
        pass


async def _finish_giveaway(guild, channel_id, message_id):
    """Pick winner(s) for a timed giveaway."""
    import settings as cfg2
    info = cfg2.get_giveaway(message_id)
    if not info or info.get("ended"):
        return
    try:
        ch = guild.get_channel(int(channel_id))
        if ch is None and _bot:
            try:
                ch = await _bot.fetch_channel(int(channel_id))
            except Exception:
                ch = None
        if ch is None:
            return
        try:
            msg = await ch.fetch_message(int(message_id))
        except Exception:
            return
        users = []
        for r in msg.reactions:
            if str(r.emoji) == "🎉":
                async for u in r.users():
                    if not u.bot:
                        users.append(u)
                break
        users = list({u.id: u for u in users}.values())
        info["ended"] = True
        cfg2.save_giveaway(message_id, info)
        cfg2.end_giveaway_store(message_id)
        if not users:
            await send_v2(ch, "🎉 Giveaway ended", f"Prize **{info['prize']}** — no one entered.", "#FFD700")
            return
        winners = random.sample(users, min(int(info.get("winners", 1)), len(users)))
        mentions = ", ".join(w.mention for w in winners)
        await send_v2(ch, "🎉 Giveaway Ended 🎉",
                      f"Prize: **{info['prize']}**\nWinner(s): {mentions} — congrats!", "#FFD700")
    except Exception as e:
        print(f"giveaway finish error: {e}")


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

async def run_tool(name, args, guild, author_is_admin, origin=None, author=None):
    """Returns (result_text, created_roles). origin is the channel the ping came from."""
    if name in WRITE_NAMES and name not in OPEN_WRITES and not author_is_admin:
        return "Failed: that needs an admin. Ask an admin to ping me.", []

    if name not in {t["function"]["name"] for t in TOOLS_SCHEMA}:
        return f"Unknown tool: {name}", []

    try:
        return await _execute(name, args, guild, origin, author)
    except discord.Forbidden:
        return ("Failed: I don't have permission for that. "
                "Move my role to the top and give me the matching permission.", [])
    except discord.HTTPException as e:
        return f"Failed: Discord error ({e}). Try again in a bit.", []


async def _execute(name, args, guild, origin, author=None):
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
        from ui import sanitize_everyone_here
        # Never mass-ping via say/send — admins use announce with ping_everyone=true
        await ch.send(sanitize_everyone_here(args["text"][:1900]).replace("<@&", "<\u200b@&"))
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

    # ----- staff: warns / cleanup / lockdown -----
    if name == "warn_member":
        m = _find_member(guild, args["member"])
        if not m:
            return f"Couldn't find anyone matching '{args['member']}'.", []
        ok, why = _manageable(guild, m)
        if not ok:
            return f"Failed: {why}", []
        n = cfg.add_warning(guild.id, m.id, args.get("reason", "no reason"))
        await _log(guild, f"⚠️ {m.display_name} warned ({n}x): {args.get('reason','')[:150]}")
        extra = " — 3 warns, consider a timeout." if n >= 3 else ""
        return f"Warned {m.display_name} (#{n}){extra}.", []

    if name == "list_warnings":
        m = _find_member(guild, args["member"])
        if not m:
            return f"Couldn't find anyone matching '{args['member']}'.", []
        ws = cfg.get_warnings(guild.id, m.id)
        if not ws:
            return f"{m.display_name} has no warnings.", []
        return f"{m.display_name} warnings:\n" + "\n".join(f"{w['id']}. {w['reason']}" for w in ws), []

    if name == "clear_warnings":
        m = _find_member(guild, args["member"])
        if not m:
            return f"Couldn't find anyone matching '{args['member']}'.", []
        cfg.clear_warnings(guild.id, m.id)
        return f"Cleared warnings for {m.display_name}.", []

    if name == "clear_user":
        ch = _find_text_channel(guild, args["channel"]) if args.get("channel") else origin
        if not isinstance(ch, discord.TextChannel):
            return "Couldn't find that text channel.", []
        m = _find_member(guild, args["member"])
        if not m:
            return f"Couldn't find anyone matching '{args['member']}'.", []
        limit = max(10, min(int(args.get("limit", 50)), 100))

        def _check(msg):
            return msg.author.id == m.id

        deleted = await ch.purge(limit=limit, check=_check)
        return f"Deleted {len(deleted)} messages from {m.display_name} in #{ch.name}.", []

    if name == "lock_all":
        n = 0
        for ch in guild.text_channels:
            try:
                await ch.set_permissions(guild.default_role, send_messages=False, reason="Vibe lockdown")
                n += 1
            except Exception:
                pass
        await _log(guild, f"🔒 Server locked down ({n} channels).")
        return f"Locked down {n} channels. Use unlock_all to open.", []

    if name == "unlock_all":
        n = 0
        for ch in guild.text_channels:
            try:
                await ch.set_permissions(guild.default_role, send_messages=None, reason="Vibe unlock")
                n += 1
            except Exception:
                pass
        return f"Unlocked {n} channels.", []

    # ----- embeds (Components V2) -----
    if name == "send_embed":
        ch = _find_text_channel(guild, args["channel"]) if args.get("channel") else origin
        if not isinstance(ch, discord.TextChannel):
            return "Couldn't find that text channel.", []
        is_admin = bool(getattr(author, "guild_permissions", None) and author.guild_permissions.administrator)
        want_ping = bool(args.get("ping_everyone")) and is_admin
        await send_v2(
            ch, args.get("title", ""), args.get("description", ""),
            args.get("color", "#A78BFA"), args.get("footer", ""),
            args.get("image", ""), args.get("thumbnail", ""),
            content="@everyone" if want_ping else None,
            allow_everyone=want_ping,
        )
        return f"Sent embed (Components V2) to #{ch.name}.", []

    # ----- automod -----
    if name == "set_antispam":
        s = cfg.update_settings(guild.id, antispam=bool(args["enabled"]))
        return f"Anti-spam {'enabled ✅' if s['antispam'] else 'disabled ❌'}.", []

    if name == "set_antiswear":
        s = cfg.update_settings(guild.id, antiswear=bool(args["enabled"]))
        return f"Anti-swear {'enabled ✅' if s['antiswear'] else 'disabled ❌'}.", []

    if name == "add_filtered_word":
        s = cfg.add_word(guild.id, args["word"])
        return f"Added blocked word. Total custom: {len(s['extra_words'])}.", []

    if name == "remove_filtered_word":
        s = cfg.remove_word(guild.id, args["word"])
        return f"Removed. Total custom: {len(s['extra_words'])}.", []

    if name == "show_config":
        s = cfg.get_settings(guild.id)
        words = ", ".join(s.get("extra_words", [])) or "none"
        return (
            f"⚙️ **{guild.name} config**\n"
            f"Anti-spam: {'✅' if s['antispam'] else '❌'} | Anti-swear: {'✅' if s['antiswear'] else '❌'}\n"
            f"Blocked words: {words}\n"
            f"Welcome: {'✅ #' + s['welcome_channel'] if s['welcome_enabled'] else '❌'} "
            f"| ping={s['welcome_ping']} embed={s['welcome_embed']}\n"
            f"Msg: {s['welcome_message'][:120]}\n"
            f"Goodbye: {'✅ #' + s['goodbye_channel'] if s['goodbye_enabled'] else '❌'}\n"
            f"Autorole: {s['autorole'] or 'off'} | Log: #{s['log_channel'] or 'off'}"
        ), []

    # ----- welcome / goodbye / autorole / logs -----
    if name == "setup_welcome":
        ch = _find_text_channel(guild, args["channel"])
        if not ch:
            return f"No text channel matching '{args['channel']}'. Try #welcome.", []
        s = cfg.update_settings(
            guild.id, welcome_enabled=True, welcome_channel=ch.name,
            welcome_message=args["message"][:500],
            welcome_ping=bool(args.get("ping", False)),
            welcome_embed=bool(args.get("use_embed", True)),
        )
        return (f"Welcome enabled ✅ in #{ch.name} — ping={'on' if s['welcome_ping'] else 'off'}. "
                f"New joins will get: {args['message'][:150]}"), []

    if name == "disable_welcome":
        cfg.update_settings(guild.id, welcome_enabled=False)
        return "Welcome messages disabled.", []

    if name == "setup_goodbye":
        ch = _find_text_channel(guild, args["channel"])
        if not ch:
            return f"No text channel matching '{args['channel']}'.", []
        cfg.update_settings(guild.id, goodbye_enabled=True, goodbye_channel=ch.name,
                            goodbye_message=args["message"][:500])
        return f"Goodbye enabled in #{ch.name}.", []

    if name == "setup_autorole":
        q = str(args["role"]).strip()
        if q.lower() in {"off", "none", "disable"}:
            cfg.update_settings(guild.id, autorole="")
            return "Autorole disabled.", []
        role = _find_role(guild, q)
        if not role:
            return f"No role matching '{q}'.", []
        cfg.update_settings(guild.id, autorole=role.name)
        return f"New members will auto-get **{role.name}**.", []

    if name == "setup_log":
        q = str(args["channel"]).strip()
        if q.lower() in {"off", "none", "disable"}:
            cfg.update_settings(guild.id, log_channel="")
            return "Mod logs disabled.", []
        ch = _find_text_channel(guild, q)
        if not ch:
            return f"No text channel matching '{q}'.", []
        cfg.update_settings(guild.id, log_channel=ch.name)
        return f"Mod logs will go to #{ch.name}.", []

    # ----- giveaways -----
    if name == "start_giveaway":
        ch = _find_text_channel(guild, args["channel"]) if args.get("channel") else origin
        if not isinstance(ch, discord.TextChannel):
            return "Couldn't find that text channel.", []
        prize = str(args.get("prize", "prize"))[:250]
        winners = max(1, min(int(args.get("winners", 1)), 10))
        mode = str(args.get("mode", "timed")).lower().strip()
        minutes = max(1, min(int(args.get("minutes", 60)), 10080))
        first = mode in {"first", "firstreact", "first_to_react", "fastest"}
        if first:
            desc = (f"⚡ **FIRST-TO-REACT WINS** ⚡\nPrize: **{prize}**\n\n"
                    f"Be the first to react with 🎉 to win!")
        else:
            desc = (f"🎉 **GIVEAWAY** 🎉\nPrize: **{prize}**\n"
                    f"Winners: {winners} | Ends in {minutes} min\n\nReact with 🎉 to enter!")
        try:
            msg = await send_v2(ch, "🎉 Giveaway 🎉", desc, "#FFD700", footer="Vibe giveaways • good luck!")
            await msg.add_reaction("🎉")
        except Exception as ex:
            return f"Failed to post giveaway: {ex}", []
        cfg.save_giveaway(msg.id, {
            "guild_id": guild.id, "channel_id": ch.id, "prize": prize,
            "winners": winners, "mode": "first" if first else "timed",
            "ended": False,
        })
        if not first and _bot:
            async def _timer(gid=guild.id, cid=ch.id, mid=msg.id, mins=minutes):
                await asyncio.sleep(mins * 60)
                try:
                    g = _bot.get_guild(gid) or guild
                    await _finish_giveaway(g, cid, mid)
                except Exception:
                    pass
            asyncio.create_task(_timer())
        how = "first 🎉 reaction wins instantly!" if first else f"ends in {minutes} min, {winners} winner(s)."
        return f"Giveaway posted in #{ch.name} (ID {msg.id}) — {how}", []

    if name == "end_giveaway":
        mid = re.sub(r"\D", "", str(args["message_id"]))
        info = cfg.get_giveaway(mid)
        if not info:
            return "No active giveaway with that message ID.", []
        await _finish_giveaway(guild, info["channel_id"], mid)
        return "Giveaway ended — winner(s) announced above.", []

    if name == "reroll_giveaway":
        mid = re.sub(r"\D", "", str(args["message_id"]))
        # need channel: search all text channels for the message
        target = None
        for ch in guild.text_channels:
            try:
                target = await ch.fetch_message(int(mid))
                break
            except Exception:
                continue
        if target is None:
            return "Couldn't find that giveaway message.", []
        users = []
        for r in target.reactions:
            if str(r.emoji) == "🎉":
                async for u in r.users():
                    if not u.bot:
                        users.append(u)
                break
        users = list({u.id: u for u in users}.values())
        if not users:
            return "No entries to reroll from.", []
        winner = random.choice(users)
        await send_v2(target.channel, "🎉 Reroll 🎉",
                      f"New winner for **giveaway**: {winner.mention} — congrats!", "#FFD700")
        return f"Rerolled — {winner.display_name} wins.", []

    # ----- tickets -----
    if name == "setup_tickets":
        cat = None
        for c in guild.categories:
            if c.name.lower() == str(args["category"]).lower().lstrip("#"):
                cat = c
                break
        if not cat:
            try:
                cat = await guild.create_category(name=str(args["category"])[:100], reason="Vibe tickets")
            except Exception:
                return "Couldn't create that category.", []
        cfg.update_settings(guild.id, ticket_category=cat.name)
        return f"Tickets will open under **{cat.name}**.", []

    if name == "open_ticket":
        m = _find_member(guild, args["member"])
        if not m:
            return f"Couldn't find anyone matching '{args['member']}'.", []
        s = cfg.get_settings(guild.id)
        cat = None
        if s.get("ticket_category"):
            for c in guild.categories:
                if c.name.lower() == s["ticket_category"].lower():
                    cat = c
                    break
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            m: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        }
        tname = f"ticket-{m.name.lower()[:20]}".replace(" ", "-")
        try:
            ch = await guild.create_text_channel(name=tname, category=cat, overwrites=overwrites,
                                                 topic=f"Ticket for {m.display_name}: {args.get('topic','')[:200]}",
                                                 reason="Vibe ticket")
        except Exception as e:
            return f"Failed to open ticket: {e}", []
        await send_v2(ch, "🎫 Ticket opened", f"{m.mention} {args.get('topic','How can staff help?')[:500]}", "#5865F2",
                      footer="Close with: @Vibe close this ticket")
        return f"Opened {ch.mention} for {m.display_name}.", []

    if name == "close_ticket":
        ch = origin
        if ch is None or not isinstance(ch, discord.TextChannel):
            return "Run this inside the ticket channel.", []
        if not ch.name.startswith("ticket-"):
            return "This doesn't look like a ticket channel.", []
        await ch.send("Closing ticket in 5s…")
        await asyncio.sleep(5)
        try:
            await ch.delete(reason="Vibe ticket closed")
        except Exception:
            pass
        return "Ticket closed.", []

    # ----- reaction roles -----
    if name == "add_reaction_role":
        role = _find_role(guild, args["role"])
        if not role:
            return f"No role matching '{args['role']}'.", []
        mid = re.sub(r"\D", "", str(args["message_id"]))
        emoji = str(args["emoji"]).strip()
        found = None
        for ch in guild.text_channels:
            try:
                found = await ch.fetch_message(int(mid))
                break
            except Exception:
                continue
        if found is None:
            return "Couldn't find that message. Use its ID (right-click > Copy ID).", []
        try:
            await found.add_reaction(emoji)
        except Exception:
            return "I couldn't react with that emoji — use a normal emoji or one from this server.", []
        cfg.add_rr(mid, emoji, guild.id, role.name)
        return f"React {emoji} on that message = **{role.name}**.", []

    if name == "remove_reaction_role":
        mid = re.sub(r"\D", "", str(args["message_id"]))
        cfg.remove_rr(mid, str(args["emoji"]).strip())
        return "Reaction-role removed.", []

    if name == "list_reaction_roles":
        rows = [(k, v) for k, v in cfg.get_rr().items() if str(v.get("guild")) == str(guild.id)]
        if not rows:
            return "No reaction roles set up.", []
        return "\n".join(f"{k} -> {v['role']}" for k, v in rows[:25]), []

    # ----- bans / emojis -----
    if name == "list_bans":
        out = []
        try:
            async for entry in guild.bans():
                out.append(f"{entry.user} ({entry.user.id}) — {entry.reason or 'no reason'}"[:150])
                if len(out) >= 20:
                    break
        except discord.Forbidden:
            return "Failed: I need Ban Members permission.", []
        return "\n".join(out) or "No bans.", []

    if name == "hackban":
        uid = re.sub(r"\D", "", str(args["user_id"]))
        if not uid:
            return "Give me a user ID.", []
        try:
            obj = discord.Object(id=int(uid))
            await guild.ban(obj, reason=args.get("reason", "Vibe hackban")[:200])
            return f"Banned ID {uid}.", []
        except Exception as e:
            return f"Failed: {e}", []

    if name == "softban":
        m = _find_member(guild, args["member"])
        if not m:
            return f"Couldn't find anyone matching '{args['member']}'.", []
        ok, why = _manageable(guild, m)
        if not ok:
            return f"Failed: {why}", []
        days = max(0, min(int(args.get("delete_days", 1)), 7))
        try:
            await guild.ban(m, reason="Vibe softban", delete_message_days=days)
            await guild.unban(m, reason="Vibe softban")
            return f"Softbanned {m.display_name} (messages wiped).", []
        except Exception as e:
            return f"Failed: {e}", []

    if name == "list_emojis":
        if not guild.emojis:
            return "No custom emojis.", []
        return "\n".join(f":{e.name}: — {e.id}" for e in guild.emojis[:30]), []

    if name == "create_emoji":
        import aiohttp
        try:
            async with aiohttp.ClientSession() as sess:
                async with sess.get(str(args["url"])) as r:
                    if r.status != 200:
                        return "Couldn't download that image.", []
                    img = await r.read()
            e = await guild.create_custom_emoji(name=str(args["name"])[:32].lower().replace(" ", "_"), image=img[:256*1024], reason="Vibe bot")
            return f"Created :{e.name}:", []
        except Exception as e:
            return f"Failed (need Manage Emojis, image <256KB): {e}", []

    if name == "delete_emoji":
        q = str(args["emoji"]).strip().strip(":").lower()
        for e in guild.emojis:
            if e.name.lower() == q:
                try:
                    await e.delete(reason="Vibe bot")
                    return f"Deleted :{e.name}:", []
                except Exception as ex:
                    return f"Failed: {ex}", []
        return f"No emoji matching '{q}'.", []

    # ----- info -----
    if name == "role_info":
        role = _find_role(guild, args["role"])
        if not role:
            return f"No role matching '{args['role']}'.", []
        perms = [p for p, v in role.permissions if v][:8]
        return (f"**{role.name}** ({role.id})\nMembers: {len(role.members)} | Color: {role.color} "
                f"| Hoist: {role.hoist} | Mentionable: {role.mentionable}\n"
                f"Key perms: {', '.join(perms) or 'none'}"), []

    if name == "channel_info":
        ch = _find_channel(guild, args["channel"])
        if not ch:
            return f"No channel matching '{args['channel']}'.", []
        extra = ""
        if isinstance(ch, discord.TextChannel):
            extra = f"Topic: {ch.topic or 'none'} | Slowmode: {ch.slowmode_delay}s"
        return (f"**#{ch.name}** ({ch.id})\nType: {type(ch).__name__} | "
                f"Category: {ch.category.name if ch.category else 'none'}\n{extra}"), []

    if name == "bot_stats":
        import time as _t
        up = datetime.datetime.now(datetime.timezone.utc) - START_TIME
        h, rem = divmod(int(up.total_seconds()), 3600)
        lat = round(_bot.latency * 1000) if _bot else -1
        n = len(_bot.guilds) if _bot else 0
        return f"Uptime: {h}h | Ping: {lat}ms | Servers: {n}", []

    if name == "help_panel":
        ch = _find_text_channel(guild, args["channel"]) if args.get("channel") else origin
        if not isinstance(ch, discord.TextChannel):
            return "Couldn't find that channel.", []
        await send_v2(ch, "✨ Vibe — what I can do",
                      "**Mod:** warn, timeout, kick, ban, softban, hackban, purge, lockdown\n"
                      "**Setup:** welcome, goodbye, autorole, logs, tickets, reaction roles, automod\n"
                      "**Fun:** giveaways, polls, embeds, announcements, reminders, XP levels\n"
                      "**Info:** server/member/role/channel, bans, emojis, leaderboard\n\n"
                      "Just ping me: `@Vibe enable antispam` `@Vibe setup welcome #hi msg: hello!`", "#A78BFA",
                      footer="Vibe • ping me to build")
        return f"Help posted in #{ch.name}.", []

    # ----- voice mass -----
    if name == "move_all_voice":
        src = _find_voice_channel(guild, args["from"])
        dst = _find_voice_channel(guild, args["to"])
        if not src or not dst:
            return "Couldn't find one of those voice channels.", []
        n = 0
        for m in list(src.members):
            try:
                await m.move_to(dst, reason="Vibe move all")
                n += 1
            except Exception:
                pass
        return f"Moved {n} members to {dst.name}.", []

    if name == "disconnect_all_voice":
        if args.get("channel"):
            vc = _find_voice_channel(guild, args["channel"])
            targets = list(vc.members) if vc else []
        else:
            targets = [m for ch in guild.voice_channels for m in ch.members]
        n = 0
        for m in targets:
            try:
                await m.move_to(None, reason="Vibe disconnect all")
                n += 1
            except Exception:
                pass
        return f"Disconnected {n} from voice.", []

    if name == "slowmode_all":
        secs = max(0, min(int(args["seconds"]), 21600))
        n = 0
        for ch in guild.text_channels:
            try:
                await ch.edit(slowmode_delay=secs, reason="Vibe slowmode all")
                n += 1
            except Exception:
                pass
        return f"Slowmode {secs}s on {n} channels.", []

    # ----- reminders / announce / server -----
    if name == "remind":
        mins = max(1, min(int(args["minutes"]), 10080))
        text = str(args["text"])[:500]
        ch = origin
        async def _timer():
            await asyncio.sleep(mins * 60)
            try:
                await send_v2(ch, "⏰ Reminder", text, "#FFD700")
            except Exception:
                pass
        asyncio.create_task(_timer())
        return f"Got it — I'll remind in {mins} min.", []

    if name == "announce":
        ch = _find_text_channel(guild, args["channel"]) if args.get("channel") else origin
        if not isinstance(ch, discord.TextChannel):
            return "Couldn't find that channel.", []
        is_admin = bool(getattr(author, "guild_permissions", None) and author.guild_permissions.administrator)
        want_ping = bool(args.get("ping_everyone")) and is_admin
        await send_v2(ch, args.get("title", "📢 Announcement"), args.get("text", ""),
                      "#FF5555", content="@everyone" if want_ping else None,
                      allow_everyone=want_ping)
        return f"Announced in #{ch.name}.", []

    if name == "set_server":
        patch = {}
        if args.get("name"):
            patch["name"] = str(args["name"])[:100]
        if args.get("description") is not None:
            patch["description"] = str(args["description"])[:500]
        if not patch:
            return "Give me a name or description.", []
        try:
            await guild.edit(reason="Vibe bot", **patch)
            return "Server updated.", []
        except Exception as e:
            return f"Failed: {e}", []

    # ----- autoresponder / afk / xp -----
    if name == "add_trigger":
        g = cfg.add_trigger(guild.id, args["trigger"], args["response"])
        if g is None:
            return "Trigger list full (30). Remove one first.", []
        return f"When someone says **{args['trigger'][:50]}** I'll reply. ({len(g)} total)", []

    if name == "remove_trigger":
        cfg.remove_trigger(guild.id, args["trigger"])
        return f"Removed trigger **{args['trigger'][:50]}**.", []

    if name == "list_triggers":
        g = cfg.get_triggers(guild.id)
        if not g:
            return "No auto-responses set. Add with: @Vibe auto reply hi with hello!", []
        return "\n".join(f"**{k}** -> {v[:80]}" for k, v in list(g.items())[:20]), []

    if name == "afk_set":
        who = author
        if who is None and origin is not None:
            # fallback: can't resolve, ask for name
            return "AFK noted — ping me again with your name so I tag the right person.", []
        try:
            cfg.set_afk(guild.id, who.id, args.get("reason", "AFK"))
            return f"{who.display_name} is now AFK: {args.get('reason','')[:150]}", []
        except Exception:
            return "Couldn't set AFK.", []

    if name == "leaderboard":
        rows = cfg.top_xp(guild.id, 10)
        if not rows:
            return "No XP yet — chat a bit first!", []
        lines = []
        for i, (xp, uid) in enumerate(rows, 1):
            m = guild.get_member(int(uid)) if uid.isdigit() else None
            nm = m.display_name if m else f"ID {uid}"
            lines.append(f"{i}. {nm} — Lvl {cfg.xp_level(xp)} ({xp} xp)")
        return "🏆 **XP Leaderboard**\n" + "\n".join(lines), []

    if name == "rank":
        q = args.get("member", "")
        m = _find_member(guild, q) if q else author
        if q and not m:
            return f"Couldn't find anyone matching '{q}'.", []
        if m is None:
            return "Ping me with a name: @Vibe rank @Ram", []
        xp = cfg.get_xp(guild.id, m.id)
        return f"**{m.display_name}** — Level {cfg.xp_level(xp)} ({xp} xp)", []

    # ----- final 16 -----
    if name == "nuke_channel":
        ch = _find_text_channel(guild, args["channel"])
        if not ch:
            return f"No text channel matching '{args['channel']}'.", []
        try:
            clone = await ch.clone(reason="Vibe nuke")
            await ch.delete(reason="Vibe nuke")
            await send_v2(clone, "💥 Channel nuked", "Fresh start — wiped by Vibe.", "#FF5555")
            return f"Nuked #{args['channel']} — fresh clone ready.", []
        except Exception as e:
            return f"Failed: {e}", []

    if name == "clone_channel":
        ch = _find_channel(guild, args["channel"])
        if not ch:
            return f"No channel matching '{args['channel']}'.", []
        try:
            clone = await ch.clone(reason="Vibe clone")
            return f"Cloned as {clone.mention}.", []
        except Exception as e:
            return f"Failed: {e}", []

    if name == "role_all":
        role = _find_role(guild, args["role"])
        if not role:
            return f"No role matching '{args['role']}'.", []
        n = 0
        for m in [x for x in guild.members if not x.bot][:500]:
            try:
                await m.add_roles(role, reason="Vibe role all")
                n += 1
            except Exception:
                pass
        return f"Gave **{role.name}** to {n} members.", []

    if name == "unrole_all":
        role = _find_role(guild, args["role"])
        if not role:
            return f"No role matching '{args['role']}'.", []
        n = 0
        for m in list(role.members)[:500]:
            try:
                await m.remove_roles(role, reason="Vibe unrole all")
                n += 1
            except Exception:
                pass
        return f"Removed **{role.name}** from {n} members.", []

    if name == "list_timeouts":
        out = [f"{m.display_name} until {m.timed_out_until:%m-%d %H:%M}" for m in guild.members if m.timed_out_until]
        return "\n".join(out[:20]) or "No one timed out.", []

    if name == "pin_message":
        ch = _find_text_channel(guild, args["channel"]) if args.get("channel") else origin
        if not isinstance(ch, discord.TextChannel):
            return "Couldn't find that channel.", []
        try:
            msg = await ch.fetch_message(int(re.sub(r"\D", "", str(args["message_id"]))))
            await msg.pin(reason="Vibe bot")
            return f"Pinned in #{ch.name}.", []
        except Exception as e:
            return f"Failed: {e}", []

    if name == "create_thread":
        ch = origin
        if not isinstance(ch, discord.TextChannel):
            return "Run this in a text channel.", []
        try:
            mid = re.sub(r"\D", "", str(args.get("message_id", "")))
            base = await ch.fetch_message(int(mid)) if mid else None
            if base is None:
                async for m in ch.history(limit=5):
                    if not m.author.bot:
                        base = m
                        break
            th = await base.create_thread(name=str(args["name"])[:100], reason="Vibe bot")
            return f"Thread {th.mention} created.", []
        except Exception as e:
            return f"Failed: {e}", []

    if name == "quickvote":
        ch = _find_text_channel(guild, args["channel"]) if args.get("channel") else origin
        if not isinstance(ch, discord.TextChannel):
            return "Couldn't find that channel.", []
        msg = await send_v2(ch, "📊 Vote", str(args["question"])[:500], "#5865F2", footer="React ✅ or ❌")
        try:
            await msg.add_reaction("✅")
            await msg.add_reaction("❌")
        except Exception:
            pass
        return f"Vote posted in #{ch.name}.", []

    if name == "dm_member":
        m = _find_member(guild, args["member"])
        if not m:
            return f"Couldn't find anyone matching '{args['member']}'.", []
        try:
            from ui import sanitize_everyone_here as _sz
            await m.send(_sz(str(args["text"])[:1900]))
            return f"DMed {m.display_name}.", []
        except Exception:
            return f"Couldn't DM {m.display_name} (DMs closed?).", []

    if name == "setup_counter":
        q = str(args["name"]).strip()
        if q.lower() in {"off", "disable", "none"}:
            cfg.update_settings(guild.id, counter="")
            for vc in guild.voice_channels:
                if vc.name.startswith(("Members:", "👥", "Members ")) and len(vc.members) == 0:
                    try:
                        await vc.delete(reason="Vibe counter off")
                    except Exception:
                        pass
            return "Counter disabled.", []
        label = q.replace("{count}", str(guild.member_count))[:100] if "{count}" in q else f"{q}: {guild.member_count}"[:100]
        try:
            vc = await guild.create_voice_channel(name=label, reason="Vibe counter")
            try:
                await vc.set_permissions(guild.default_role, connect=False)
            except Exception:
                pass
            cfg.update_settings(guild.id, counter=q[:100])
            return f"Counter live: **{label}** (updates on join/leave).", []
        except Exception as e:
            return f"Failed: {e}", []

    if name == "add_sticky":
        ch = _find_text_channel(guild, args["channel"])
        if not ch:
            return f"No text channel matching '{args['channel']}'.", []
        cfg.set_sticky(guild.id, ch.id, args["text"])
        await send_v2(ch, "📌 Sticky", args["text"][:1000], "#FFD700")
        return f"Sticky set in #{ch.name}.", []

    if name == "remove_sticky":
        ch = _find_text_channel(guild, args["channel"])
        if not ch:
            return f"No text channel matching '{args['channel']}'.", []
        cfg.clear_sticky(guild.id, ch.id)
        return f"Sticky removed from #{ch.name}.", []

    if name == "massnick":
        prefix = str(args["prefix"])[:20]
        n = 0
        for m in [x for x in guild.members if not x.bot][:200]:
            ok, _ = _manageable(guild, m)
            if not ok:
                continue
            try:
                await m.edit(nick=f"{prefix}{m.name}"[:32], reason="Vibe massnick")
                n += 1
            except Exception:
                pass
        return f"Renamed {n} members with prefix **{prefix}**.", []

    if name == "reset_nicks":
        n = 0
        for m in [x for x in guild.members if not x.bot][:200]:
            if not m.nick:
                continue
            ok, _ = _manageable(guild, m)
            if not ok:
                continue
            try:
                await m.edit(nick=None, reason="Vibe reset nicks")
                n += 1
            except Exception:
                pass
        return f"Reset {n} nicknames.", []

    if name == "server_icon":
        g = guild
        icon = g.icon.url if g.icon else "none"
        banner = g.banner.url if g.banner else "none"
        splash = g.splash.url if g.splash else "none"
        return f"Icon: {icon}\nBanner: {banner}\nSplash: {splash}", []

    if name == "list_invites":
        try:
            invs = await guild.invites()
        except discord.Forbidden:
            return "Need Manage Server / invites perm.", []
        if not invs:
            return "No active invites.", []
        rows = sorted(invs, key=lambda i: (i.uses or 0), reverse=True)[:15]
        return "\n".join(f"{i.code} #{i.channel} by {i.inviter} — {i.uses}/{i.max_uses or '∞'}" for i in rows), []

    # ----- tickets+ (add/remove/transcript) -----
    if name == "ticket_add":
        ch = origin if origin and hasattr(origin, "name") else None
        if not ch or not ch.name.startswith("ticket-"):
            return "Run this inside the ticket channel.", []
        m = _find_member(guild, args["member"])
        if not m:
            return f"No member matching '{args['member']}'.", []
        try:
            await ch.set_permissions(m, read_messages=True, send_messages=True, reason="Vibe ticket add")
        except Exception as e:
            return f"Failed to add: {e}", []
        return f"Added {m.display_name} to {ch.name}.", []

    if name == "ticket_remove":
        ch = origin if origin and hasattr(origin, "name") else None
        if not ch or not ch.name.startswith("ticket-"):
            return "Run this inside the ticket channel.", []
        m = _find_member(guild, args["member"])
        if not m:
            return f"No member matching '{args['member']}'.", []
        try:
            await ch.set_permissions(m, overwrite=None, reason="Vibe ticket remove")
        except Exception as e:
            return f"Failed to remove: {e}", []
        return f"Removed {m.display_name} from {ch.name}.", []

    if name == "ticket_transcript":
        ch = origin if origin and hasattr(origin, "name") else None
        if not ch or not ch.name.startswith("ticket-"):
            return "Run this inside the ticket channel.", []
        try:
            lines = []
            async for m in ch.history(limit=200, oldest_first=True):
                tag = m.author.display_name.replace("\n", " ")
                lines.append(f"[{m.created_at:%Y-%m-%d %H:%M}] {tag}: {m.content[:500]}")
            body = "\n".join(lines) or "(empty ticket)"
            import io
            f = discord.File(io.BytesIO(body.encode()), filename=f"{ch.name}-transcript.txt")
            log = _find_text_channel(guild, (cfg.get_settings(guild.id).get("log_channel") or ""))
            if log:
                try:
                    await log.send(f"📝 Transcript for #{ch.name} ({len(lines)} msgs)", file=f)
                except Exception:
                    pass
            else:
                try:
                    await ch.send("📝 Transcript:", file=f)
                    return "No log channel set — transcript posted here instead. Set one with setup_log.", []
                except Exception as e:
                    return f"Failed to build transcript: {e}", []
            await ch.send("Transcript saved ✅ — closing in 5s…")
            await asyncio.sleep(5)
            await ch.delete(reason="Vibe ticket closed with transcript")
            return f"Transcript saved ({len(lines)} msgs), #{ch.name} closed.", []
        except Exception as e:
            return f"Failed: {e}", []

    # ----- timed moderation -----
    if name == "tempban":
        m = _find_member(guild, args["member"])
        if not m:
            return f"No member matching '{args['member']}'.", []
        ok, why = _manageable(guild, m)
        if not ok:
            return f"Can't tempban: {why}.", []
        minutes = max(1, min(int(args.get("minutes", 60)), 60 * 24 * 7))
        reason = str(args.get("reason", "tempban"))[:200]
        try:
            await m.ban(reason=f"Vibe tempban {minutes}m: {reason}", delete_message_days=1)
        except Exception as e:
            return f"Failed to ban: {e}", []

        async def _unban_later():
            await asyncio.sleep(minutes * 60)
            try:
                await guild.unban(discord.Object(id=m.id), reason="Vibe tempban expired")
                await _log(guild, f"⏳ Tempban expired — unbanned {m.display_name} ({m.id})")
            except Exception:
                pass

        asyncio.create_task(_unban_later())
        return f"🔨 Tempbanned {m.display_name} for {minutes}m ({reason}). Auto-unban scheduled — note: lost on bot restart.", []

    if name == "temprole":
        m = _find_member(guild, args["member"])
        role = _find_role(guild, args["role"])
        if not m:
            return f"No member matching '{args['member']}'.", []
        if not role:
            return f"No role matching '{args['role']}'.", []
        minutes = max(1, min(int(args.get("minutes", 60)), 60 * 24 * 7))
        try:
            await m.add_roles(role, reason=f"Vibe temprole {minutes}m")
        except Exception as e:
            return f"Failed: {e}", []

        async def _remove_later():
            await asyncio.sleep(minutes * 60)
            try:
                fresh = guild.get_member(m.id)
                if fresh and role in fresh.roles:
                    await fresh.remove_roles(role, reason="Vibe temprole expired")
                    await _log(guild, f"⏳ Temprole expired — removed {role.name} from {fresh.display_name}")
            except Exception:
                pass

        asyncio.create_task(_remove_later())
        return f"⏳ Gave {role.name} to {m.display_name} for {minutes}m. Auto-remove scheduled — note: lost on bot restart.", []

    # ----- level reward roles -----
    if name == "level_role_add":
        level = max(1, min(int(args.get("level", 1)), 100))
        role = _find_role(guild, args["role"])
        if not role:
            return f"No role matching '{args['role']}'. Create it first.", []
        cfg.update_settings(guild.id, level_roles={**cfg.get_settings(guild.id).get("level_roles", {}), str(level): role.name})
        return f"🏆 Level {level} → {role.name}. Members hitting it get the role automatically.", []

    if name == "level_role_remove":
        level = str(int(args.get("level", 0)))
        lr = dict(cfg.get_settings(guild.id).get("level_roles", {}))
        if level not in lr:
            return f"No reward set for level {level}.", []
        lr.pop(level)
        cfg.update_settings(guild.id, level_roles=lr)
        return f"Removed level {level} reward.", []

    if name == "level_roles_list":
        lr = cfg.get_settings(guild.id).get("level_roles", {})
        if not lr:
            return "No level rewards set. Use level_role_add.", []
        return "🏆 Level rewards:\n" + "\n".join(f"Level {k} → {v}" for k, v in sorted(lr.items(), key=lambda x: int(x[0]))), []

    # ----- verification gate + antiraid -----
    if name == "verify_setup":
        role = _find_role(guild, args["role"])
        if not role:
            return f"No role matching '{args['role']}'. Create it first (e.g. Unverified).", []
        cfg.update_settings(guild.id, verify_enabled=True, verify_role=role.name)
        return (f"🛡️ Verification gate ON — new joins get {role.name}. "
                "Staff approve with assign_role. Lock down the rest of the channels to hide them from this role for full effect."), []

    if name == "verify_off":
        cfg.update_settings(guild.id, verify_enabled=False, verify_role="")
        return "Verification gate OFF.", []

    if name == "antiraid":
        mode = str(args.get("mode", "")).lower() in ("on", "true", "enable", "yes")
        cfg.update_settings(guild.id, antiraid=mode)
        return f"🚨 Anti-raid {'ON — >5 joins in 30s triggers auto-lockdown + mod log ping' if mode else 'OFF'}.", []

    # ----- report + snipe + welcome preview -----
    if name == "report":
        m = _find_member(guild, args["member"])
        if not m:
            return f"No member matching '{args['member']}'.", []
        reason = str(args.get("reason", "no reason"))[:500]
        who = author.display_name if author and hasattr(author, "display_name") else "someone"
        await _log(guild, f"🚩 REPORT by {who}: {m.display_name} ({m.id}) — {reason}")
        return f"Report filed against {m.display_name} — mods can see it in the log channel.", []

    if name == "snipe":
        ch = _find_text_channel(guild, args["channel"]) if args.get("channel") else (origin if origin and hasattr(origin, "id") else None)
        if not ch:
            return "No channel found.", []
        hit = _SNIPE.get(f"{guild.id}:{ch.id}")
        if not hit:
            return "Nothing sniped in that channel yet.", []
        return f"📸 Last deleted in #{ch.name} — {hit['who']}: {hit['text'][:800]}", []

    if name == "welcome_test":
        s = cfg.get_settings(guild.id)
        if not s.get("welcome_enabled"):
            return "Welcome is off. Set it up first (setup_welcome).", []
        me = author if author and hasattr(author, "display_name") else None
        preview = _fmt(s.get("welcome_message", "welcome {member}!"), me, guild)
        ch = origin if origin and hasattr(origin, "send") else None
        if ch:
            try:
                if s.get("welcome_embed", True):
                    await send_v2(ch, f"Welcome to {guild.name}! 🎉", preview, "#A78BFA",
                                  footer=f"Preview — real joins post in #{s.get('welcome_channel')}",
                                  thumbnail=guild.icon.url if guild.icon else "")
                else:
                    await ch.send(f"👋 {preview}"[:1900])
            except Exception:
                pass
        return "Welcome preview posted above ☝️", []

    return f"Unknown tool: {name}", []
