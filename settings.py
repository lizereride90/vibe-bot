"""Per-server settings for Vibe: automod, welcome, logs, autorole.
Stored in settings.json so it survives restarts. Multi-server safe.
"""
import json
import os

SETTINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json")
WARNINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "warnings.json")
GIVEAWAYS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "giveaways.json")
TRIGGERS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "triggers.json")
AFK_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "afk.json")
XP_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "xp.json")
RR_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reaction_roles.json")
STICKY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sticky.json")

# Default bad-words. Server admins can add/remove via tools.
DEFAULT_SWEARS = {
    "fuck", "shit", "bitch", "slut", "whore", "cunt", "dick", "pussy",
    "nigger", "nigga", "faggot", "retard", "kys",
}


def _load(path):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return {}


def _save(path, data):
    try:
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


def default_guild():
    return {
        "antispam": True,      # on by default, admins can disable
        "antiswear": False,    # off by default, enable with "enable antiswear"
        "extra_words": [],     # custom filtered words
        "welcome_enabled": False,
        "welcome_channel": "",
        "welcome_message": "welcome to the server, {member}! 🎉",
        "welcome_ping": False,
        "welcome_embed": True,
        "goodbye_enabled": False,
        "goodbye_channel": "",
        "goodbye_message": "{member} left the server.",
        "autorole": "",
        "log_channel": "",
        "ticket_category": "",
        "xp_enabled": True,
        "levelup_channel": "",
        "counter": "",
    }


def get_settings(guild_id):
    data = _load(SETTINGS_FILE)
    g = data.get(str(guild_id), {})
    base = default_guild()
    base.update(g)
    return base


def update_settings(guild_id, **patch):
    data = _load(SETTINGS_FILE)
    g = data.get(str(guild_id), {})
    g.update(patch)
    data[str(guild_id)] = g
    _save(SETTINGS_FILE, data)
    merged = default_guild()
    merged.update(g)
    return merged


def get_words(guild_id):
    s = get_settings(guild_id)
    return set(w.lower() for w in list(DEFAULT_SWEARS) + s.get("extra_words", []))


def add_word(guild_id, word):
    s = get_settings(guild_id)
    words = [w for w in s.get("extra_words", [])]
    if word.lower() not in [w.lower() for w in words] and word.lower() not in DEFAULT_SWEARS:
        words.append(word.lower()[:50])
    return update_settings(guild_id, extra_words=words)


def remove_word(guild_id, word):
    s = get_settings(guild_id)
    words = [w for w in s.get("extra_words", []) if w.lower() != word.lower()]
    return update_settings(guild_id, extra_words=words)


# ---------- warnings ----------

def add_warning(guild_id, user_id, reason):
    data = _load(WARNINGS_FILE)
    key = f"{guild_id}:{user_id}"
    lst = data.get(key, [])
    lst.append({"reason": reason[:200], "id": len(lst) + 1})
    data[key] = lst[-25:]  # keep last 25
    _save(WARNINGS_FILE, data)
    return len(lst)


def get_warnings(guild_id, user_id):
    return _load(WARNINGS_FILE).get(f"{guild_id}:{user_id}", [])


def clear_warnings(guild_id, user_id):
    data = _load(WARNINGS_FILE)
    data.pop(f"{guild_id}:{user_id}", None)
    _save(WARNINGS_FILE, data)


# ---------- giveaways ----------

def save_giveaway(msg_id, info):
    data = _load(GIVEAWAYS_FILE)
    data[str(msg_id)] = info
    _save(GIVEAWAYS_FILE, data)


def get_giveaway(msg_id):
    return _load(GIVEAWAYS_FILE).get(str(msg_id))


def end_giveaway_store(msg_id):
    data = _load(GIVEAWAYS_FILE)
    info = data.pop(str(msg_id), None)
    _save(GIVEAWAYS_FILE, data)
    return info


def all_giveaways():
    return _load(GIVEAWAYS_FILE)


# ---------- autoresponder triggers ----------

def get_triggers(guild_id):
    return _load(TRIGGERS_FILE).get(str(guild_id), {})


def add_trigger(guild_id, trigger, response):
    data = _load(TRIGGERS_FILE)
    g = data.get(str(guild_id), {})
    if len(g) >= 30:
        return None
    g[trigger.lower()[:80]] = response[:500]
    data[str(guild_id)] = g
    _save(TRIGGERS_FILE, data)
    return g


def remove_trigger(guild_id, trigger):
    data = _load(TRIGGERS_FILE)
    g = data.get(str(guild_id), {})
    g.pop(trigger.lower(), None)
    data[str(guild_id)] = g
    _save(TRIGGERS_FILE, data)
    return g


# ---------- AFK ----------

def set_afk(guild_id, user_id, reason):
    data = _load(AFK_FILE)
    data[f"{guild_id}:{user_id}"] = reason[:200]
    _save(AFK_FILE, data)


def get_afk(guild_id, user_id):
    return _load(AFK_FILE).get(f"{guild_id}:{user_id}")


def clear_afk(guild_id, user_id):
    data = _load(AFK_FILE)
    data.pop(f"{guild_id}:{user_id}", None)
    _save(AFK_FILE, data)


# ---------- XP / levels ----------

def add_xp(guild_id, user_id, amount=5):
    data = _load(XP_FILE)
    key = f"{guild_id}:{user_id}"
    xp = int(data.get(key, 0)) + amount
    data[key] = xp
    _save(XP_FILE, data)
    return xp


def get_xp(guild_id, user_id):
    return int(_load(XP_FILE).get(f"{guild_id}:{user_id}", 0))


def xp_level(xp):
    # 100 xp per level, triangular-ish: level = int(sqrt(xp/100))
    import math
    return int(math.sqrt(max(0, xp) / 100))


def top_xp(guild_id, limit=10):
    data = _load(XP_FILE)
    prefix = f"{guild_id}:"
    rows = [(int(v), k.split(":", 1)[1]) for k, v in data.items() if k.startswith(prefix)]
    rows.sort(reverse=True)
    return rows[:limit]


# ---------- reaction roles ----------

def get_rr():
    return _load(RR_FILE)


def add_rr(message_id, emoji, guild_id, role_name):
    data = _load(RR_FILE)
    data[f"{message_id}:{emoji}"] = {"guild": guild_id, "role": role_name}
    _save(RR_FILE, data)


def remove_rr(message_id, emoji):
    data = _load(RR_FILE)
    data.pop(f"{message_id}:{emoji}", None)
    _save(RR_FILE, data)


def find_rr(message_id, emoji):
    return _load(RR_FILE).get(f"{message_id}:{emoji}")


# ---------- sticky + counter ----------

def get_sticky(guild_id, channel_id):
    return _load(STICKY_FILE).get(f"{guild_id}:{channel_id}")


def set_sticky(guild_id, channel_id, text):
    data = _load(STICKY_FILE)
    data[f"{guild_id}:{channel_id}"] = text[:1000]
    _save(STICKY_FILE, data)


def clear_sticky(guild_id, channel_id):
    data = _load(STICKY_FILE)
    data.pop(f"{guild_id}:{channel_id}", None)
    _save(STICKY_FILE, data)
