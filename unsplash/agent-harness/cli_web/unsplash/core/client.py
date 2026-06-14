"""Browser-backed client for Unsplash's internal /napi/ endpoints.

unsplash.com is gated by an Anubis JS proof-of-work challenge that returns
HTTP 401 to plain HTTP clients (curl_cffi/httpx). We drive a stealth headless
browser (camoufox) to solve the challenge once on the homepage, then fetch the
JSON /napi/ endpoints within that cleared browser session.
"""

from __future__ import annotations

import atexit
import json
from urllib.parse import urlencode

from camoufox.sync_api import Camoufox

from .exceptions import (
    NetworkError,
    NotFoundError,
    RateLimitError,
    ServerError,
    UnsplashError,
)

BASE_URL = "https://unsplash.com"


class UnsplashClient:
    """Client for Unsplash's internal /napi/ REST API."""

    def __init__(self) -> None:
        self._cm = None
        self._browser = None
        self._page = None

    def _ensure_browser(self) -> None:
        """Lazily launch the browser and clear the Anubis challenge (once).

        Done lazily so the client works whether or not it's used as a context
        manager. The browser is torn down on process exit via atexit.
        """
        if self._page is not None:
            return
        try:
            self._cm = Camoufox(headless=True)
            self._browser = self._cm.__enter__()
            self._page = self._browser.new_page()
            # Solve the proof-of-work challenge on the homepage; /napi/ clears after.
            self._page.goto(f"{BASE_URL}/", wait_until="domcontentloaded", timeout=45000)
            self._page.wait_for_timeout(3000)
        except Exception as exc:
            self.close()
            raise NetworkError(f"Failed to initialize browser session: {exc}") from exc
        atexit.register(self.close)

    def __enter__(self) -> UnsplashClient:
        self._ensure_browser()
        return self

    def __exit__(self, *args) -> None:
        self.close()

    def close(self) -> None:
        if self._cm is not None:
            try:
                self._cm.__exit__(None, None, None)
            except Exception:
                pass
            finally:
                self._cm = self._browser = self._page = None

    # ── HTTP helpers ────────────────────────────────────────────

    def _navigate(self, url: str) -> tuple[int, str, dict]:
        """Fetch *url* in the browser session; return (status, body, headers)."""
        self._ensure_browser()
        try:
            resp = self._page.goto(url, wait_until="domcontentloaded", timeout=30000)
        except Exception as exc:
            raise NetworkError(f"Request failed: {exc}") from exc
        if resp is None:
            raise NetworkError(f"No response for {url}")
        return resp.status, resp.text(), resp.headers

    def _get(self, path: str, params: dict | None = None) -> dict | list:
        url = f"{BASE_URL}{path}"
        if params:
            query = urlencode({k: v for k, v in params.items() if v is not None})
            if query:
                url = f"{url}?{query}"

        status, body, headers = self._navigate(url)

        if status == 404:
            raise NotFoundError(f"Not found: {path}")
        if status == 429:
            retry = headers.get("retry-after")
            raise RateLimitError(
                "Rate limited by Unsplash",
                retry_after=float(retry) if retry else None,
            )
        if status >= 500:
            raise ServerError(f"Server error {status}", status_code=status)
        if status >= 400:
            raise UnsplashError(f"HTTP {status}: {body[:200]}")

        try:
            return json.loads(body)
        except (ValueError, TypeError) as exc:
            raise UnsplashError(f"Invalid JSON response from {path}") from exc

    # ── Search ──────────────────────────────────────────────────

    def search_photos(
        self,
        query: str,
        page: int = 1,
        per_page: int = 20,
        orientation: str | None = None,
        color: str | None = None,
        order_by: str | None = None,
    ) -> dict:
        params: dict = {"query": query, "page": page, "per_page": per_page}
        if orientation:
            params["orientation"] = orientation
        if color:
            params["color"] = color
        if order_by:
            params["order_by"] = order_by
        return self._get("/napi/search/photos", params=params)

    def search_collections(self, query: str, page: int = 1, per_page: int = 20) -> dict:
        return self._get(
            "/napi/search/collections",
            params={"query": query, "page": page, "per_page": per_page},
        )

    def search_users(self, query: str, page: int = 1, per_page: int = 20) -> dict:
        return self._get(
            "/napi/search/users",
            params={"query": query, "page": page, "per_page": per_page},
        )

    def autocomplete(self, query: str) -> dict:
        return self._get(f"/nautocomplete/{query}")

    # ── Photos ──────────────────────────────────────────────────

    def get_photo(self, id_or_slug: str) -> dict:
        return self._get(f"/napi/photos/{id_or_slug}")

    def get_photo_related(self, photo_id: str) -> dict:
        return self._get(f"/napi/photos/{photo_id}/related")

    def get_photo_statistics(self, photo_id: str) -> dict:
        return self._get(f"/napi/photos/{photo_id}/statistics")

    def get_random_photos(
        self,
        count: int = 1,
        query: str | None = None,
        topics: str | None = None,
        orientation: str | None = None,
    ) -> list:
        params: dict = {"count": count}
        if query:
            params["query"] = query
        if topics:
            params["topics"] = topics
        if orientation:
            params["orientation"] = orientation
        return self._get("/napi/photos/random", params=params)

    # ── Topics ──────────────────────────────────────────────────

    def list_topics(self, page: int = 1, per_page: int = 20, order_by: str | None = None) -> list:
        params: dict = {"page": page, "per_page": per_page}
        if order_by:
            params["order_by"] = order_by
        return self._get("/napi/topics", params=params)

    def get_topic(self, slug: str) -> dict:
        return self._get(f"/napi/topics/{slug}")

    def get_topic_photos(
        self,
        slug: str,
        page: int = 1,
        per_page: int = 20,
        order_by: str | None = None,
    ) -> list:
        params: dict = {"page": page, "per_page": per_page}
        if order_by:
            params["order_by"] = order_by
        return self._get(f"/napi/topics/{slug}/photos", params=params)

    # ── Collections ─────────────────────────────────────────────

    def get_collection(self, collection_id: int | str) -> dict:
        return self._get(f"/napi/collections/{collection_id}")

    def get_collection_photos(
        self, collection_id: int | str, page: int = 1, per_page: int = 20
    ) -> list:
        return self._get(
            f"/napi/collections/{collection_id}/photos",
            params={"page": page, "per_page": per_page},
        )

    # ── Users ───────────────────────────────────────────────────

    def get_user(self, username: str) -> dict:
        return self._get(f"/napi/users/{username}")

    def get_user_photos(
        self,
        username: str,
        page: int = 1,
        per_page: int = 20,
        order_by: str | None = None,
    ) -> list:
        params: dict = {"page": page, "per_page": per_page}
        if order_by:
            params["order_by"] = order_by
        return self._get(f"/napi/users/{username}/photos", params=params)

    def get_user_collections(self, username: str, page: int = 1, per_page: int = 20) -> list:
        return self._get(
            f"/napi/users/{username}/collections",
            params={"page": page, "per_page": per_page},
        )
