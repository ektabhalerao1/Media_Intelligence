from __future__ import annotations

import re

import requests
import trafilatura
from bs4 import BeautifulSoup


DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


class AccessGateError(RuntimeError):
    """Raised when a page appears to require email/signup before article access."""


EMAIL_GATE_PATTERNS = [
    r"enter\s+email\s+to\s+continue",
    r"enter\s+your\s+email\s+to\s+continue",
    r"provide\s+your\s+email",
    r"email\s+required\s+to\s+continue",
    r"sign\s*up\s+to\s+continue",
    r"register\s+to\s+continue",
    r"subscribe\s+to\s+continue",
]


def fetch_html(url: str, timeout: int = 20, retries: int = 1) -> str:
    """Fetch page HTML with one retry on network/HTTP failures."""
    last_error: Exception | None = None

    for _ in range(retries + 1):
        try:
            response = requests.get(url, timeout=timeout, headers=DEFAULT_HEADERS)
            response.raise_for_status()
            return response.text
        except requests.RequestException as exc:
            last_error = exc

    raise RuntimeError(f"Request failed after retry: {last_error}")


def extract_article_text(html: str, url: str) -> str:
    """Extract readable article text using Trafilatura, then BeautifulSoup fallback."""
    extracted = trafilatura.extract(
        html,
        url=url,
        output_format="txt",
        include_comments=False,
        include_tables=False,
    )

    if extracted and extracted.strip():
        return _normalize_text(extracted)

    return extract_text_with_bs4(html)


def detect_access_gate(html: str) -> str | None:
    """Return access-gate name when content is blocked behind email/signup wall."""
    lowered = html.lower()
    for pattern in EMAIL_GATE_PATTERNS:
        if re.search(pattern, lowered):
            return "Access Gate: Email Required"

    soup = BeautifulSoup(html, "lxml")
    has_email_input = soup.find("input", attrs={"type": re.compile("email", re.IGNORECASE)}) is not None
    page_text = soup.get_text(separator=" ", strip=True).lower()
    has_continue_prompt = bool(
        re.search(r"(continue|read|access).{0,40}(email|sign\s*up|register|subscribe)", page_text)
    )

    if has_email_input and has_continue_prompt:
        return "Access Gate: Email Required"

    return None


def extract_text_with_bs4(html: str) -> str:
    """Fallback text extraction using BeautifulSoup and basic cleanup."""
    soup = BeautifulSoup(html, "lxml")

    for tag in soup(["script", "style", "noscript", "header", "footer", "nav", "aside"]):
        tag.decompose()

    text = soup.get_text(separator="\n")
    return _normalize_text(text)


def split_paragraphs(text: str) -> list[str]:
    """Split normalized text into paragraphs."""
    parts = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
    if parts:
        return parts

    return [line.strip() for line in text.splitlines() if line.strip()]


def _normalize_text(text: str) -> str:
    """Normalize line endings and whitespace while preserving paragraph breaks."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\n\s+", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
