"""
Optional LLM provider layer.
Set LLM_ENABLED=true + LLM_API_KEY in environment to enable.
Compatible with OpenAI, Groq, Together AI, Ollama.
"""

from __future__ import annotations
import os
import httpx

import hashlib
import time

_LLM_FIX_CACHE: dict[str,tuple[str,float]] = {}

LLM_ENABLED  = os.getenv("LLM_ENABLED", "false").lower() == "true"
LLM_API_KEY  = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
LLM_MODEL    = os.getenv("LLM_MODEL", "gpt-4o-mini")
LLM_TIMEOUT  = int(os.getenv("LLM_TIMEOUT_SECONDS", "30"))


async def call_llm(system: str, user: str) -> str | None:
    """Return LLM text response or None if disabled/error."""
    if not LLM_ENABLED or not LLM_API_KEY:
        return None

    headers = {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
        "temperature": 0.2,
        "max_tokens": 1024,
    }

    try:
        async with httpx.AsyncClient(timeout=LLM_TIMEOUT) as client:
            r = await client.post(
                f"{LLM_BASE_URL}/chat/completions",
                headers=headers,
                json=payload,
            )
            r.raise_for_status()
            data = r.json()
            return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"[LLM] Error: {e}")
        return None

def call_llm_sync(system:str, user:str)->str | None:
    """sync version of call_llm for use in sync contexts."""
    if not LLM_ENABLED or not LLM_API_KEY:
        return None
    
    headers = {
        "Authorization":f"Bearer {LLM_API_KEY}",
        "Content-Type":"application/json",
    }

    payload = {
        "model":LLM_MODEL,
        "messages":[
            {"role":"system", "content":system},
            {"role":"user",   "content":user},
        ],
        "temperature":0.2,
        "max_tokens":1024,
    }

    try:
        with httpx.Client(timeout = LLM_TIMEOUT) as client:
            r = client.post(
                f"{LLM_BASE_URL}/chat/completions",
                headers = headers,
                json = payload, 
            )

            r.raise_for_status()
            data = r.json()
            return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"[LLM] sync Error: {e}")
        return None
    

def get_fix_for_issue(
        bug_type: str,
        description: str,
        code_context:str,
        ttl: int=3600,
)->tuple[str|None,bool]:
    """ get and llm generated fix for the detected bug,
    Returns:   - fix:str|None - the generated fix or None if not available"""

    if not is_enabled():
        return None, False
    
    # cache key from bug_type + description + code_context(first 512)
    raw_key = f"{bug_type}|{description}|{code_context[:512]}"
    cache_key = hashlib.sha256(raw_key.encode()).hexdigest()

    #check cache
    if cache_key in _LLM_FIX_CACHE:
        cached_text, expires_at = _LLM_FIX_CACHE[cache_key]

        if time.time()<expires_at:
            return cached_text, True  #cachehit
        
        del _LLM_FIX_CACHE[cache_key] #cache expired, remove

    system_prompt = (
        "You are a senior software engineer. "
        "When given a code snippet and a detected bug, return ONLY a concise, "
        "concrete fix suggestion in 1-3 sentences. No markdown, no preamble."
    )

    user_prompt = (
        f"Bug Type: {bug_type}\n"
        f"Issue: {description}\n\n"
        f"Code:\n{code_context}\n\n"
        "provide specific, production ready fix for the exact code"
    )

    response = call_llm_sync(system_prompt, user_prompt)

    if response:
        _LLM_FIX_CACHE[cache_key] = (response, time.time() + ttl)
        return response, False
    return None, False

def is_enabled() -> bool:
    return LLM_ENABLED and bool(LLM_API_KEY)
