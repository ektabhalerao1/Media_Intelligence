from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path

from openai import OpenAI


@dataclass(frozen=True)
class LLMAnalysisResult:
    article_topic: str
    is_climate_tech: str
    brand_sentiment: str
    sentiment_reason: str
    confidence_score: int
    cached: bool


class LLMAnalyzer:
    """LLM analysis with local content-hash caching and expiry management."""

    def __init__(
        self,
        cache_dir: str = ".cache/llm_analysis",
        ttl_days: int = 10,
        model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl_days = ttl_days

        openai_model = _clean_env_value(os.getenv("OPENAI_MODEL", "gpt-4.1-mini"))
        openai_api_key = _clean_env_value(os.getenv("OPENAI_API_KEY", ""))
        openai_base_url = _clean_env_value(os.getenv("OPENAI_BASE_URL", "")) or None

        gemini_model = _clean_env_value(os.getenv("GEMINI_MODEL", "gemini-2.0-flash"))
        gemini_api_key = _clean_env_value(os.getenv("GEMINI_API_KEY", ""))
        if not gemini_api_key:
            gemini_api_key = _clean_env_value(os.getenv("GOOGLE_API_KEY", ""))

        gemini_base_url = _normalize_gemini_base_url(
            _clean_env_value(os.getenv("GEMINI_BASE_URL", ""))
            or "https://generativelanguage.googleapis.com/v1beta/openai/"
        )

        self.provider = "none"
        if api_key:
            self.api_key = api_key
            self.model = model or openai_model
            self.base_url = base_url or openai_base_url
            self.provider = "custom"
        elif openai_api_key:
            self.api_key = openai_api_key
            self.model = model or openai_model
            self.base_url = base_url or openai_base_url
            self.provider = "openai"
        elif gemini_api_key:
            self.api_key = gemini_api_key
            self.model = model or gemini_model
            self.base_url = base_url or gemini_base_url
            self.provider = "gemini"
        else:
            self.api_key = ""
            self.model = model or openai_model
            self.base_url = base_url or openai_base_url

        self.client: OpenAI | None = None
        if self.api_key:
            self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)

    def cleanup_expired_cache(self) -> None:
        """Delete cache entries older than TTL."""
        now = datetime.now(tz=UTC)
        ttl = timedelta(days=self.ttl_days)

        for file_path in self.cache_dir.glob("*.json"):
            try:
                payload = json.loads(file_path.read_text(encoding="utf-8"))
                created_at = _parse_iso_datetime(payload.get("created_at", ""))
                if created_at is None or now - created_at > ttl:
                    file_path.unlink(missing_ok=True)
            except Exception:
                file_path.unlink(missing_ok=True)

    def analyze(self, article_text: str, search_term: str) -> LLMAnalysisResult:
        """Analyze article content and return normalized structured output."""
        if not self.client:
            raise RuntimeError("No LLM API key configured. Set OPENAI_API_KEY or GEMINI_API_KEY.")

        content_hash = self._content_hash(article_text)
        term_key = search_term.strip().lower()

        cached = self._read_cache(content_hash=content_hash, term_key=term_key)
        if cached is not None:
            return LLMAnalysisResult(**cached, cached=True)

        llm_result = self._call_llm(article_text=article_text, search_term=search_term)
        normalized = _normalize_llm_payload(llm_result)

        self._write_cache(content_hash=content_hash, term_key=term_key, result=normalized)
        return LLMAnalysisResult(**normalized, cached=False)

    @staticmethod
    def _content_hash(article_text: str) -> str:
        normalized = article_text.strip().encode("utf-8", errors="ignore")
        return sha256(normalized).hexdigest()

    def _cache_path(self, content_hash: str) -> Path:
        return self.cache_dir / f"{content_hash}.json"

    def _read_cache(self, content_hash: str, term_key: str) -> dict[str, str | int] | None:
        path = self._cache_path(content_hash)
        if not path.exists():
            return None

        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            created_at = _parse_iso_datetime(payload.get("created_at", ""))
            if created_at is None:
                return None

            if datetime.now(tz=UTC) - created_at > timedelta(days=self.ttl_days):
                path.unlink(missing_ok=True)
                return None

            terms = payload.get("terms", {})
            if term_key in terms:
                return terms[term_key]
            return None
        except Exception:
            path.unlink(missing_ok=True)
            return None

    def _write_cache(self, content_hash: str, term_key: str, result: dict[str, str | int]) -> None:
        path = self._cache_path(content_hash)
        now = datetime.now(tz=UTC).isoformat()

        payload: dict[str, object] = {
            "created_at": now,
            "updated_at": now,
            "content_hash": content_hash,
            "terms": {term_key: result},
        }

        if path.exists():
            try:
                existing = json.loads(path.read_text(encoding="utf-8"))
                created_at = existing.get("created_at", now)
                terms = existing.get("terms", {})
                if isinstance(terms, dict):
                    terms[term_key] = result
                else:
                    terms = {term_key: result}

                payload = {
                    "created_at": created_at,
                    "updated_at": now,
                    "content_hash": content_hash,
                    "terms": terms,
                }
            except Exception:
                payload = {
                    "created_at": now,
                    "updated_at": now,
                    "content_hash": content_hash,
                    "terms": {term_key: result},
                }

        path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")

    def _call_llm(self, article_text: str, search_term: str) -> dict[str, object]:
        assert self.client is not None

        trimmed_text = article_text[:12000]
        prompt = (
            "Analyze only this main article text. Ignore ads/sidebars/related links. "
            f"Target entity: {search_term}. "
            "Return strict JSON with keys: article_topic, is_climate_tech, brand_sentiment, "
            "sentiment_reason, confidence_score. Constraints: article_topic 2-6 words; "
            "is_climate_tech is Yes or No; brand_sentiment is Positive, Neutral, or Negative; "
            "if Negative use 3-4 sentences in sentiment_reason, otherwise 1-2 sentences; "
            "confidence_score integer 0-100."
        )

        try:
            completion = self.client.chat.completions.create(
                model=self.model,
                response_format={"type": "json_object"},
                temperature=0.1,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a precise media analyst. Output valid JSON only.",
                    },
                    {
                        "role": "user",
                        "content": f"{prompt}\n\nARTICLE:\n{trimmed_text}",
                    },
                ],
            )
        except Exception as exc:
            raw_error = str(exc)
            is_gemini_auth = (
                self.provider == "gemini"
                and (
                    "UNAUTHENTICATED" in raw_error
                    or "ACCESS_TOKEN_TYPE_UNSUPPORTED" in raw_error
                    or "Error code: 401" in raw_error
                )
            )
            if is_gemini_auth:
                raise RuntimeError(
                    "Gemini authentication failed (401). Use a Gemini API key in GEMINI_API_KEY "
                    "(or GOOGLE_API_KEY), not an OAuth/access token, and set GEMINI_BASE_URL to "
                    "https://generativelanguage.googleapis.com/v1beta/openai/."
                ) from exc
            raise

        content = completion.choices[0].message.content or "{}"
        return json.loads(content)


def _clean_env_value(value: str) -> str:
    """Trim whitespace and surrounding quotes from env values."""
    cleaned = (value or "").strip()
    if len(cleaned) >= 2 and cleaned[0] == cleaned[-1] and cleaned[0] in {'"', "'"}:
        cleaned = cleaned[1:-1].strip()
    return cleaned


def _normalize_gemini_base_url(base_url: str) -> str:
    """Normalize Gemini OpenAI-compatible base URL to avoid endpoint mismatches."""
    normalized = base_url.rstrip("/")

    if "generativelanguage.googleapis.com" in normalized and "/openai" not in normalized:
        normalized = f"{normalized}/openai"

    return f"{normalized}/"


def _parse_iso_datetime(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value)
    except Exception:
        return None


def _normalize_llm_payload(payload: dict[str, object]) -> dict[str, str | int]:
    topic_raw = str(payload.get("article_topic", "")).strip()
    topic_words = topic_raw.split()
    if len(topic_words) < 2:
        topic = "General Topic"
    else:
        topic = " ".join(topic_words[:6])

    climate_raw = str(payload.get("is_climate_tech", "")).strip().lower()
    is_climate_tech = "Yes" if climate_raw == "yes" else "No"

    sentiment_raw = str(payload.get("brand_sentiment", "")).strip().lower()
    sentiment_map = {
        "positive": "Positive",
        "neutral": "Neutral",
        "negative": "Negative",
    }
    brand_sentiment = sentiment_map.get(sentiment_raw, "Neutral")

    sentiment_reason = str(payload.get("sentiment_reason", "")).strip()
    if not sentiment_reason:
        sentiment_reason = "No reason provided by model."

    confidence_raw = payload.get("confidence_score", 0)
    try:
        confidence_score = int(float(str(confidence_raw)))
    except Exception:
        confidence_score = 0
    confidence_score = max(0, min(100, confidence_score))

    return {
        "article_topic": topic,
        "is_climate_tech": is_climate_tech,
        "brand_sentiment": brand_sentiment,
        "sentiment_reason": sentiment_reason,
        "confidence_score": confidence_score,
    }
