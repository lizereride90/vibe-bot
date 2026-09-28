"""Components V2 helpers. All bot embeds go through here.

Sends real Discord Components V2 (LayoutView + Container + TextDisplay).
Falls back to legacy Embed on old discord.py / errors, so nothing breaks.
Requires discord.py>=2.6 for V2 (2.5 has partial). requirements.txt pins >=2.5.

Also the single place that stops @everyone/@here ping leaks.
"""
import re
import discord

ZW = "\u200b"  # zero-width space: "@\u200beveryone" looks identical but never pings

_EVERYONE_RE = re.compile(r"@\s*everyone", re.IGNORECASE)
_HERE_RE = re.compile(r"@\s*here", re.IGNORECASE)


def sanitize_everyone_here(text: str) -> str:
    """Neutralize @everyone / @here so they display but never ping."""
    t = str(text or "")
    t = _EVERYONE_RE.sub("@" + ZW + "everyone", t)
    t = _HERE_RE.sub("@" + ZW + "here", t)
    return t


def sanitize_plain_reply(text: str) -> str:
    """Plain chat replies must never ping masses or roles.

    Breaks @everyone, @here AND role/user mention syntax <@...>
    so 'vibe say @everyone' just prints dead text.
    """
    t = sanitize_everyone_here(text)
    t = t.replace("<@&", "<" + ZW + "@&").replace("<@", "<" + ZW + "@")
    return t


def _parse_accent(color="#A78BFA"):
    try:
        return discord.Color(int(str(color).lstrip("#"), 16))
    except Exception:
        return discord.Color(0xA78BFA)


def has_v2() -> bool:
    ui = getattr(discord, "ui", None)
    return bool(ui and hasattr(ui, "LayoutView")
                and hasattr(ui, "Container") and hasattr(ui, "TextDisplay"))


def _make_container(accent):
    """Container ctor differs by version: accent_colour (official) vs accent_color."""
    ui = discord.ui
    try:
        return ui.Container(accent_colour=accent)
    except TypeError:
        pass
    try:
        return ui.Container(accent_color=accent)
    except TypeError:
        pass
    return ui.Container()


def _make_textdisplay(text):
    ui = discord.ui
    try:
        return ui.TextDisplay(text)
    except TypeError:
        return ui.TextDisplay(content=text)


def _add_gallery(box, url):
    """Attach image via MediaGallery, trying all known discord.py shapes."""
    ui = discord.ui
    url = str(url)[:500]
    # shape 1 (2.6+ guide): gallery = MediaGallery(); gallery.add_item(media=url)
    try:
        g = ui.MediaGallery()
        try:
            g.add_item(media=url)
        except TypeError:
            try:
                g.add_item(url)
            except Exception:
                # MediaGalleryItem shapes
                item = None
                for cls_name in ("MediaGalleryItem",):
                    cls = getattr(ui, cls_name, None) or getattr(discord, cls_name, None)
                    if cls is None:
                        continue
                    for kwargs in ({"media": url}, {"media": {"url": url}}, {"url": url}):
                        try:
                            item = cls(**kwargs)
                            break
                        except Exception:
                            continue
                    if item is not None:
                        break
                    try:
                        item = cls(url)
                        break
                    except Exception:
                        continue
                if item is None:
                    return False
                g.add_item(item)
        box.add_item(g)
        return True
    except Exception:
        pass
    # shape 2: MediaGallery(item) ctor
    try:
        item_cls = getattr(ui, "MediaGalleryItem", None) or getattr(discord, "MediaGalleryItem", None)
        if item_cls is not None:
            try:
                item = item_cls(media=url)
            except Exception:
                item = item_cls(url)
            box.add_item(ui.MediaGallery(item))
            return True
    except Exception:
        pass
    return False


def build_v2(title="", description="", color="#A78BFA", footer="", image="", thumbnail="",
             ping_text=None):
    """Return a LayoutView, or None if V2 unavailable.

    ping_text: raw "@everyone" or user mention to prepend INSIDE the
    component (V2 messages can't use content=). Caller controls
    allowed_mentions separately.
    """
    if not has_v2():
        return None
    try:
        accent = _parse_accent(color)
        view = discord.ui.LayoutView()
        box = _make_container(accent)

        md = ""
        if ping_text:
            md += f"{str(ping_text)[:100]}\n"
        if title:
            md += f"## {sanitize_everyone_here(str(title)[:200])}\n"
        if description:
            md += sanitize_everyone_here(str(description)[:3500])

        thumb = str(thumbnail or "") if str(thumbnail or "").startswith("http") else ""
        img = str(image or "") if str(image or "").startswith("http") else ""

        # thumbnail -> proper Section+Thumbnail accessory when available
        use_section = False
        if thumb:
            try:
                sec = discord.ui.Section()
                sec.add_item(_make_textdisplay(md or "…"))
                tcls = getattr(discord.ui, "Thumbnail", None)
                if tcls is not None:
                    try:
                        acc = tcls(media=thumb)
                    except TypeError:
                        try:
                            acc = tcls(thumb)
                        except Exception:
                            acc = None
                    if acc is not None:
                        try:
                            sec.accessory = acc
                        except Exception:
                            try:
                                sec.add_item(acc)
                            except Exception:
                                pass
                        box.add_item(sec)
                        use_section = True
            except Exception:
                use_section = False

        if not use_section:
            if thumb:
                md += f"\n-# thumbnail: {thumb}"
            if footer:
                md += f"\n-# {sanitize_everyone_here(str(footer)[:200])}"
            box.add_item(_make_textdisplay(md or "…"))
        else:
            if footer:
                box.add_item(_make_textdisplay(f"-# {sanitize_everyone_here(str(footer)[:200])}"))

        if img:
            if not _add_gallery(box, img):
                # last resort: visible link so image isn't silently dropped
                try:
                    box.add_item(_make_textdisplay(f"-# 📷 {img}"))
                except Exception:
                    pass

        view.add_item(box)
        return view
    except Exception as e:
        print(f"v2 build failed: {type(e).__name__}: {str(e)[:150]}")
        return None


def build_legacy_embed(title="", description="", color="#A78BFA", footer="", image="", thumbnail=""):
    e = discord.Embed(
        title=sanitize_everyone_here(str(title or "")[:256]),
        description=sanitize_everyone_here(str(description or "")[:4000]),
        color=_parse_accent(color),
    )
    if footer:
        e.set_footer(text=sanitize_everyone_here(str(footer)[:200]))
    if image and str(image).startswith("http"):
        e.set_image(url=str(image)[:500])
    if thumbnail and str(thumbnail).startswith("http"):
        e.set_thumbnail(url=str(thumbnail)[:500])
    return e


async def send_v2(channel, title="", description="", color="#A78BFA",
                  footer="", image="", thumbnail="", content=None, allow_everyone=False):
    """Send via Components V2, fallback to legacy embed. Returns the message.

    V2 messages CANNOT carry content=/embeds= (Discord rejects 40060).
    So in V2 mode content is folded INTO the component:
    - allow_everyone=True + content="@everyone" -> "@everyone" line inside
      TextDisplay with AllowedMentions(everyone=True)
    - normal user pings (welcome etc.) -> mention line inside component,
      users allowed, everyone/roles blocked
    - no content -> plain component, pings blocked except users
    """
    if content and not allow_everyone:
        content = sanitize_everyone_here(content)
    view = build_v2(title, description, color, footer, image, thumbnail,
                    ping_text=content if content else None)
    if view is not None:
        try:
            if allow_everyone:
                allowed = discord.AllowedMentions(everyone=True, roles=True, users=True)
            else:
                allowed = discord.AllowedMentions(everyone=False, roles=False, users=True)
            # NOTE: no content=, no embed= — V2 only. Anything else -> 40060.
            return await channel.send(view=view, allowed_mentions=allowed)
        except Exception as e:
            # V2 rejected (old client perms etc.) -> fall through to embed
            print(f"v2 send failed, falling back: {type(e).__name__}: {str(e)[:200]}")
    return await channel.send(content=content,
                              embed=build_legacy_embed(title, description, color, footer, image, thumbnail))


async def safe_reply(message: discord.Message, text: str):
    """Reply without ever raising 'Unknown message', and never mass-pinging."""
    text = sanitize_plain_reply(str(text or "")[:1900])
    try:
        return await message.reply(text, mention_author=False)
    except (discord.NotFound, discord.HTTPException):
        # Unknown message / deleted reference -> plain send
        try:
            return await message.channel.send(text[:1900], reference=None)
        except Exception:
            return None
