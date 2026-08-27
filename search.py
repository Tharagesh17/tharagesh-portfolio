"""Free web search via DuckDuckGo lite (no API key, replaces paid Tavily).

Reuses the working scraper from the LeadHunter project. Returns a single
newline-joined string of top results, truncated for LLM context.
Sanitized so downstream LLM calls don't choke on URL query-string chars (e.g. '&').
"""
import re, requests

_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}


def _sanitize(text: str) -> str:
    # Strip URL query strings (the '?'...'&' part) which break some LLM endpoints.
    text = re.sub(r"(https?://\S+?)\?\S*", r"\1", text)
    # Drop common HTML entities.
    text = text.replace("&amp;", "&").replace("&quot;", '"').replace("&#39;", "'").replace("&lt;", "<").replace("&gt;", ">")
    # Collapse whitespace.
    text = re.sub(r"\s+", " ", text).strip()
    return text


def duckduckgo(query: str, limit: int = 6, max_chars: int = 4000) -> str:
    try:
        r = requests.post(
            "https://html.duckduckgo.com/html/",
            data={"q": query}, timeout=20, headers=_HEADERS,
        )
        results = re.findall(
            r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>.*?class="result__snippet"[^>]*>(.*?)</a>',
            r.text, re.S,
        )
        out = []
        for href, title, snippet in results[:limit]:
            m = re.search(r"uddg=([^&]+)", href)
            url = requests.utils.unquote(m.group(1)) if m else href
            title = re.sub("<[^>]+>", "", title)
            snippet = re.sub("<[^>]+>", "", snippet)
            out.append(f"Source: {url}\nTitle: {title}\nSnippet: {snippet}")
        text = _sanitize("\n\n".join(out))
        return text[:max_chars] if text else "(No search results found.)"
    except Exception as e:
        return f"(Search failed: {e})"
