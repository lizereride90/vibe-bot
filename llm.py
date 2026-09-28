"""Unified LLM layer: Gemini primary, Groq fallback. Multi-key rotation supported.

Uses Gemini's OpenAI-compatible endpoint so the same TOOLS_SCHEMA works
for both providers with zero conversion:
    POST https://generativelanguage.googleapis.com/v1beta/openai/chat/completions
    Header: Authorization: Bearer GEMINI_API_KEY

No new dependencies — aiohttp is already required.
Set in .env:
    GEMINI_API_KEY=key1,key2,key3   (comma-separated, rotates on 429/503/5xx)
    GEMINI_MODEL=gemini-2.5-flash-lite   (default — 2.0-flash was shut down Sep 2026)
    GROQ_API_KEY=key1,key2,key3     (comma-separated, rotates on 429)
    GROQ_MODEL=openai/gpt-oss-20b  (fallback brain — free tier, tool-capable)
"""
import os
import json
import asyncio
import re

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
# Sep 2026: Google shut down ALL gemini-2.0 models (404 "no longer available").
# Live replacements: gemini-2.5-flash-lite (cheapest, highest quota),
# gemini-2.5-flash, gemini-3.5-flash-lite, gemini-3.5-flash.
# chat() auto-tries backups if the configured model 404s.
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
GEMINI_BACKUPS = ["gemini-3.5-flash-lite", "gemini-3.5-flash", "gemini-3.1-flash-lite", "gemini-3.6-flash", "gemini-3.7-flash", "gemini-3.8-flash"]
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
# NOTE: llama-3.3-70b-versatile went Enterprise-only on Groq (404 for free keys).
# gpt-oss-20b is free-tier, tool-capable, 250K TPM. chat() also auto-tries
# backup models if the configured one 404s.
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
GROQ_BACKUPS = ["openai/gpt-oss-20b", "llama-3.1-8b-instant", "openai/gpt-oss-120b"]

_groq_clients: dict[str, object] = {}


def _split_keys(raw: str) -> list[str]:
    return [k.strip() for k in (raw or "").replace("\n", ",").split(",") if k.strip()]


def _collect(prefix: str) -> list[str]:
    """Collect keys from PREFIX, PREFIXS (plural), and PREFIX_1.._10 numbered.
    Numbered vars make mobile manual entry easier (one key per line)."""
    parts = [
        os.getenv(f"{prefix}S", ""),
        os.getenv(prefix, ""),
    ]
    for i in range(1, 11):
        parts.append(os.getenv(f"{prefix}_{i}", ""))
    keys = _split_keys(",".join(parts))
    seen, out = set(), []
    for k in keys:
        if k not in seen and len(k) > 10:  # skip empty/placeholder stubs
            seen.add(k)
            out.append(k)
    return out


def _gemini_keys() -> list[str]:
    return _collect("GEMINI_API_KEY")


def _groq_keys() -> list[str]:
    return _collect("GROQ_API_KEY")


def _groq(api_key: str = ""):
    key = api_key or os.getenv("GROQ_API_KEY", "")
    if key in _groq_clients:
        return _groq_clients[key]
    from groq import Groq
    client = Groq(api_key=key)
    _groq_clients[key] = client
    return client


async def _gemini_chat(messages, tools=None, tool_choice="auto",
                       temperature=0.7, max_tokens=3000, json_mode=False,
                       api_key: str = "", model_override: str = ""):
    """One chat call to Gemini via OpenAI-compat REST. Returns (content, tool_calls)."""
    import aiohttp

    key = api_key or os.getenv("GEMINI_API_KEY", "").split(",")[0].strip()
    if not key:
        raise RuntimeError("no GEMINI_API_KEY")
    model = model_override or os.getenv("GEMINI_MODEL", GEMINI_MODEL) or "gemini-2.5-flash-lite"

    body = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    # Gemini compat accepts max_tokens (alias max_completion_tokens on some models)
    if max_tokens:
        body["max_tokens"] = max_tokens
    if tools:
        body["tools"] = tools
        body["tool_choice"] = tool_choice
    if json_mode:
        body["response_format"] = {"type": "json_object"}

    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    async with aiohttp.ClientSession() as sess:
        async with sess.post(GEMINI_URL, headers=headers,
                             json=body, timeout=aiohttp.ClientTimeout(total=60)) as r:
            txt = await r.text()
            if r.status != 200:
                raise RuntimeError(f"Gemini {r.status} model={model}: {txt[:800]}")
            data = json.loads(txt or "{}")

    try:
        msg = data["choices"][0]["message"]
    except Exception:
        raise RuntimeError(f"Gemini bad shape: {txt[:300]}")

    content = msg.get("content") or ""
    raw_calls = msg.get("tool_calls") or []
    calls = []
    for tc in raw_calls:
        fn = (tc.get("function") or {})
        calls.append({
            "id": tc.get("id", f"call_{len(calls)}"),
            "name": fn.get("name", ""),
            "arguments": fn.get("arguments") or "{}",
        })
    if not content and not calls:
        # flaky empty reply (seen on overloaded models) — let groq take over
        raise RuntimeError("Gemini empty response")
    return content, calls


async def _groq_chat(messages, tools=None, tool_choice="auto",
                     temperature=0.7, max_tokens=3000, json_mode=False,
                     model_override=None, api_key: str = ""):
    """One chat call to Groq via groq lib (run in thread). Returns (content, tool_calls)."""
    key = api_key or os.getenv("GROQ_API_KEY", "").split(",")[0].strip()
    if not key:
        raise RuntimeError("no GROQ_API_KEY")
    model = model_override or os.getenv("GROQ_MODEL", GROQ_MODEL)

    def _call():
        client = _groq(key)
        kwargs = dict(model=model, messages=messages,
                      temperature=temperature, max_tokens=max_tokens)
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = tool_choice
        # NOTE: gpt-oss models on Groq 400 on response_format=json_object,
        # so skip it there — the system prompt already says "reply ONLY with JSON"
        # and classify() extracts the {...} block robustly.
        if json_mode and not model.startswith("openai/gpt-oss"):
            kwargs["response_format"] = {"type": "json_object"}
        resp = client.chat.completions.create(**kwargs)
        m = resp.choices[0].message
        calls = []
        for tc in (m.tool_calls or []):
            calls.append({
                "id": tc.id,
                "name": tc.function.name,
                "arguments": tc.function.arguments or "{}",
            })
        return (m.content or "", calls)

    return await asyncio.to_thread(_call)


async def chat(messages, tools=None, tool_choice="auto",
               temperature=0.7, max_tokens=3000, json_mode=False,
               groq_model=None):
    """Gemini keys first (rotate on 429/503/5xx), then Groq keys (rotate on 429).

    Set comma-separated keys: GEMINI_API_KEY=k1,k2,k3 / GROQ_API_KEY=k1,k2,k3
    Returns (content: str, tool_calls: list, provider: str).
    Raises RuntimeError only if ALL keys fail.
    """
    last_err = None

    # 1) Gemini: models outer, keys inner — every model gets every key.
    # dead model -> next model. 429/503/auth -> next key. thought_signature
    # bug -> skip gemini entirely (falls back to groq below).
    pref_g = os.getenv("GEMINI_MODEL", GEMINI_MODEL)
    gemini_models = [pref_g] + [m for m in GEMINI_BACKUPS if m != pref_g]
    skip_gemini = False
    gkeys = _gemini_keys()
    for gmodel in gemini_models:
        if skip_gemini:
            break
        for gi, gkey in enumerate(gkeys):
            for attempt in range(2):  # 1 retry for transient spikes on same key
                try:
                    content, calls = await _gemini_chat(
                        messages, tools, tool_choice, temperature, max_tokens, json_mode,
                        api_key=gkey, model_override=gmodel)
                    return content, calls, "gemini"
                except Exception as e:
                    last_err = e
                    msg = str(e)[:300]
                    if "thought_signature" in msg:
                        print(f"llm: gemini thought_signature bug, falling back to groq...")
                        skip_gemini = True
                        break
                    dead = "404" in msg or "no longer available" in msg or "not found" in msg.lower() or "does not exist" in msg
                    if dead:
                        print(f"llm: gemini model={gmodel} dead, trying next model...")
                        break  # next model (inner key loop broken below via flag)
                    transient = any(s in msg for s in ("503", "500", "429", "overloaded", "high demand", "UNAVAILABLE", "timeout", "Timeout"))
                    is_auth = any(s in msg for s in ("401", "403", "API key", "API_KEY_INVALID", "invalid"))
                    if transient and attempt == 0:
                        await asyncio.sleep(1.2)
                        continue
                    tag = f"key{gi+1}/{len(gkeys)} model={gmodel}"
                    if is_auth or transient:
                        print(f"llm: gemini {tag} failed ({msg[:150]}), trying next key...")
                        break  # next key, same model
                    else:
                        print(f"llm: gemini {tag} failed ({type(e).__name__}: {msg[:150]}), trying groq...")
                        skip_gemini = True
                        break
            if skip_gemini:
                break
            # dead-model break above must escape the key loop too:
            if last_err and ("404" in str(last_err)[:300] or "no longer available" in str(last_err)[:300]):
                continue

    # 2) Groq keys in order — next key on 429 rate-limit (the whole point).
    # Also rotate MODELS: if configured model 404s (retired/Enterprise-only),
    # auto-try backups so one bad GROQ_MODEL doesn't kill the bot.
    gkeys = _groq_keys()
    preferred = groq_model or os.getenv("GROQ_MODEL", GROQ_MODEL)
    models = [preferred] + [m for m in GROQ_BACKUPS if m != preferred]
    for qi, qkey in enumerate(gkeys):
        for mi, model in enumerate(models):
            try:
                content, calls = await _groq_chat(
                    messages, tools, tool_choice, temperature, max_tokens, json_mode,
                    model_override=model, api_key=qkey)
                return content, calls, "groq"
            except Exception as e:
                last_err = e
                msg = str(e)[:200]
                tag = f"key{qi+1}/{len(gkeys)} model={model}"
                dead_model = "404" in msg or "does not exist" in msg or "decommissioned" in msg or "model_not_found" in msg
                if dead_model:
                    print(f"llm: groq {tag} dead, trying next model...")
                    continue
                if "429" in msg or "rate" in msg.lower() or "RateLimit" in type(e).__name__:
                    print(f"llm: groq {tag} rate-limited, trying next key...")
                    break  # next key, same model order
                print(f"llm: groq {tag} failed ({type(e).__name__}: {msg[:150]})")
                break  # next key (might be a dead key)
        continue

    raise RuntimeError(f"all LLM providers failed: {last_err}")


async def probe_and_log():
    """Startup probe: list models visible to the first Gemini key + Groq key.

    Prints full error bodies so 404s can actually be diagnosed.
    Runs once at boot, costs 1-2 tiny API calls.
    """
    import aiohttp
    for gi, gkey in enumerate(_gemini_keys()[:3]):
        try:
            headers = {"Authorization": f"Bearer {gkey}"}
            async with aiohttp.ClientSession() as sess:
                async with sess.get(
                    "https://generativelanguage.googleapis.com/v1beta/openai/models",
                    headers=headers, timeout=aiohttp.ClientTimeout(total=20)) as r:
                    txt = await r.text()
                    if r.status != 200:
                        print(f"llm probe: gemini key{gi+1} models-list {r.status}: {txt[:500]}")
                        continue
                    try:
                        ids = [m.get("id", "?") for m in json.loads(txt).get("data", [])]
                    except Exception:
                        ids = [txt[:200]]
                    want = GEMINI_BACKUPS + [os.getenv("GEMINI_MODEL", GEMINI_MODEL)]
                    hit = [m for m in want if m in ids]
                    print(f"llm probe: gemini key{gi+1} sees {len(ids)} models; wanted-available={hit or 'NONE'}")
        except Exception as e:
            print(f"llm probe: gemini key{gi+1} error: {type(e).__name__}: {str(e)[:300]}")


async def classify(system_prompt, user_text, temperature=0.2, max_tokens=200,
                   groq_model=None):
    """Classifier helper (watchdog). Gemini first, Groq fallback.

    Returns parsed JSON dict, or None if both fail.
    """
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_text},
    ]
    try:
        content, _, provider = await chat(
            messages, temperature=temperature, max_tokens=max_tokens,
            json_mode=True, groq_model=groq_model)
        # strip code fences / prose — gpt-oss often adds chatter around JSON
        t = content.strip()
        if t.startswith("```"):
            t = t.strip("`").strip()
            if t.lower().startswith("json"):
                t = t[4:].strip()
        try:
            return json.loads(t or "{}")
        except Exception:
            m = re.search(r"\{[^{}]*\}", t, re.S)
            if m:
                try:
                    return json.loads(m.group(0))
                except Exception:
                    pass
            # last resort: keyword sniff so watchdog keeps working
            low = t.lower()
            if "moderate" in low:
                sev = "high" if any(w in low for w in ("high", "phish", "scam", "slur", "threat")) else "low"
                return {"decision": "moderate", "severity": sev, "reason": t[:120]}
            if "answer" in low:
                return {"decision": "answer", "severity": "low", "reason": t[:120]}
            return {"decision": "ignore", "severity": "low", "reason": t[:120]}
    except Exception as e:
        print(f"llm classify failed: {type(e).__name__}: {str(e)[:150]}")
        return None
