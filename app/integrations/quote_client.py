import logging

import httpx

logger = logging.getLogger(__name__)

ZENQUOTES_URL = "https://zenquotes.io/api/random"
REQUEST_TIMEOUT_SECONDS = 3.0

FALLBACK_QUOTE = {
    "quote": "The secret of getting ahead is getting started.",
    "author": "Mark Twain",
}


async def fetch_random_quote() -> dict[str, str]:
    """Fetch a motivational quote from ZenQuotes.

    Returns a `{"quote": ..., "author": ...}` dict. Falls back to a hardcoded
    quote on any network error, timeout, non-2xx response, or unexpected
    payload shape — the caller never has to handle exceptions.
    """
    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
            response = await client.get(ZENQUOTES_URL)
            response.raise_for_status()
            payload = response.json()

        # ZenQuotes returns a list like: [{"q": "...", "a": "...", "h": "..."}]
        if not isinstance(payload, list) or not payload:
            raise ValueError("Empty or malformed response from quote API")
        first = payload[0]
        quote = first.get("q")
        author = first.get("a")
        if not quote or not author:
            raise ValueError("Quote API response missing 'q' or 'a'")
        return {"quote": quote, "author": author}
    except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
        logger.warning("Quote API unavailable, using fallback: %s", exc)
        return FALLBACK_QUOTE.copy()
