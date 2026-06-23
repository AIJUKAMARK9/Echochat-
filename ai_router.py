import hashlib, time, logging
from collections import OrderedDict
from typing import Dict, Any
from fastapi import Depends
from ai_service import OllamaProvider, safety_check, detect_technical_query
from config import settings

logger = logging.getLogger(__name__)

class AIRouter:
    def __init__(self, provider: OllamaProvider):
        self.provider = provider
        self.cache = OrderedDict()

    def _hash_key(self, text: str, user_id: str) -> str:
        key = f"{user_id}:{text.strip().lower()}"
        return hashlib.md5(key.encode()).hexdigest()

    def _add_to_cache(self, key: str, value: Any):
        if key in self.cache:
            self.cache.move_to_end(key)
        self.cache[key] = (value, time.time())
        while len(self.cache) > settings.AI_CACHE_SIZE:
            self.cache.popitem(last=False)

    def _get_from_cache(self, key: str):
        if key not in self.cache:
            return None
        val, ts = self.cache[key]
        if time.time() - ts > settings.AI_CACHE_TTL:
            del self.cache[key]
            return None
        self.cache.move_to_end(key)
        return val

    async def route_message(self, text: str, user_id: str) -> Dict[str, Any]:
        if not text.strip():
            return {"status": "error", "message": "Message empty"}
        safety = safety_check(text)
        if not safety["safe"]:
            return {"status": "warning", "message": "Unsafe topic", "reason": safety["reason"]}
        is_tech = detect_technical_query(text)
        cache_key = self._hash_key(text, user_id)
        cached = self._get_from_cache(cache_key)
        if cached:
            cached["source"] = "cache"
            return cached
        result = await self.provider.generate(text, is_tech)
        result["source"] = "llama"
        self._add_to_cache(cache_key, result)
        return result

    async def route_message_stream(self, text: str, user_id: str):
        if not text.strip():
            yield "Message empty"
            return
        safety = safety_check(text)
        if not safety["safe"]:
            yield "Unsafe topic"
            return
        is_tech = detect_technical_query(text)
        cache_key = self._hash_key(text, user_id)
        cached = self._get_from_cache(cache_key)
        if cached:
            yield cached.get("text", "")
            return
        full = []
        async for token in self.provider.generate_stream(text, is_tech):
            full.append(token)
            yield token
        self._add_to_cache(cache_key, {"text": "".join(full), "source": "llama"})

_ai_router_instance = None

def get_ai_router() -> AIRouter:
    global _ai_router_instance
    if _ai_router_instance is None:
        _ai_router_instance = AIRouter(OllamaProvider())
    return _ai_router_instance
