import asyncio, re, json, logging
from typing import Dict, Any, Optional, AsyncGenerator
import aiohttp
from config import settings

logger = logging.getLogger(__name__)

TECH_KEYWORDS = {
    "code", "python", "javascript", "function", "class", "debug", "error", "sql",
    "api", "json", "algorithm", "compile", "runtime", "exception", "deploy",
    "server", "database", "git", "docker", "kubernetes", "chart", "graph",
    "statistics", "stats", "analysis", "data", "%", "percent"
}

BLOCKED_WORDS = {
    "terror", "bomb", "murder", "phishing", "malware",
    "ransomware", "credit card scam"
}

def detect_technical_query(text: str) -> bool:
    words = set(re.findall(r"\b\w+\b", text.lower()))
    return bool(words & TECH_KEYWORDS)

def safety_check(text: str) -> Dict[str, Any]:
    lower = text.lower()
    for word in BLOCKED_WORDS:
        if word in lower:
            return {"safe": False, "reason": word}
    return {"safe": True, "reason": "clean"}

def trim_text(text: str, max_len=700) -> str:
    text = text.strip()
    if len(text) <= max_len:
        return text
    return text[:500] + "..." + text[-100:]

class OllamaProvider:
    def __init__(self):
        self.url = settings.OLLAMA_URL
        self.model = settings.OLLAMA_MODEL

    async def generate(self, text: str, is_tech: bool = False) -> Dict[str, Any]:
        text = trim_text(text)
        system_msg = (
            "You are EchoChat Tech AI. If text contains numbers/stats, respond with JSON with 'text' and 'chart_data'. Max 4 sentences."
        ) if is_tech else (
            "You are EchoChat AI. Be helpful, friendly, concise. Max 4 sentences."
        )
        payload = {
            "model": self.model,
            "messages": [{"role": "system", "content": system_msg}, {"role": "user", "content": text}],
            "temperature": 0.2,
            "stream": False
        }
        try:
            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(self.url, json=payload) as resp:
                    if resp.status != 200:
                        return {"model": "ollama", "text": "[AI temporarily unavailable]"}
                    data = await resp.json()
                    content = data["choices"][0]["message"]["content"]
                    if is_tech:
                        chart_data = self._extract_json(content)
                        if chart_data:
                            return {"model": "ollama", "text": chart_data.get("text", content), "chart_data": chart_data.get("chart_data")}
                    return {"model": "ollama", "text": content}
        except asyncio.TimeoutError:
            return {"model": "ollama", "text": "[AI took too long]"}
        except Exception as e:
            logger.error(f"Ollama error: {e}")
            return {"model": "ollama", "text": "[AI error]"}

    async def generate_stream(self, text: str, is_tech: bool = False) -> AsyncGenerator[str, None]:
        text = trim_text(text)
        system_msg = "Tech AI with JSON if stats." if is_tech else "Friendly AI, concise."
        payload = {
            "model": self.model,
            "messages": [{"role": "system", "content": system_msg}, {"role": "user", "content": text}],
            "temperature": 0.2,
            "stream": True
        }
        try:
            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(self.url, json=payload) as resp:
                    if resp.status != 200:
                        yield "[AI error]"
                        return
                    async for line in resp.content:
                        line = line.decode().strip()
                        if not line or not line.startswith("data: "):
                            continue
                        line = line[6:]
                        if line == "[DONE]":
                            break
                        try:
                            chunk = json.loads(line)
                            token = chunk["choices"][0]["delta"].get("content", "")
                            if token:
                                yield token
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            logger.error(f"Stream error: {e}")
            yield "[AI error]"

    @staticmethod
    def _extract_json(content: str) -> Optional[Dict[str, Any]]:
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass
        match = re.search(r'```(?:json)?\s*({.*?})\s*```', content, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
        match = re.search(r'\{.*\}', content, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        return None
