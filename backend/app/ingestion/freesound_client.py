from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

import httpx

from app.config import get_settings


FREESOUND_BASE_URL = "https://freesound.org/apiv2"


@dataclass
class FreesoundClient:
    """
    Minimal Freesound API client using token authentication.

    Authentication follows the token-based scheme described in the
    Freesound documentation:
    https://freesound.org/docs/api/authentication.html#token-authentication
    """

    api_token: str
    timeout: float = 10.0

    @classmethod
    def from_settings(cls) -> "FreesoundClient":
        settings = get_settings()
        return cls(api_token=settings.freesound_api_token)

    def _get_headers(self) -> Dict[str, str]:
        return {"Authorization": f"Token {self.api_token}"}

    def _client(self) -> httpx.Client:
        return httpx.Client(
            base_url=FREESOUND_BASE_URL,
            headers=self._get_headers(),
            timeout=self.timeout,
        )

    def search_text(
        self,
        query: str,
        *,
        page: int = 1,
        page_size: int = 50,
        fields: Optional[Iterable[str]] = None,
    ) -> Dict[str, Any]:
        """
        Perform a text search.

        Wraps GET /apiv2/search/text/ with basic pagination and field selection.
        """
        params: Dict[str, Any] = {
            "query": query,
            "page": page,
            "page_size": page_size,
        }
        if fields:
            params["fields"] = ",".join(fields)

        with self._client() as client:
            resp = client.get("/search/text/", params=params)
            resp.raise_for_status()
            return resp.json()

    def get_sound(self, sound_id: int, *, fields: Optional[Iterable[str]] = None) -> Dict[str, Any]:
        """
        Retrieve full metadata for a sound by id.

        Wraps GET /apiv2/sounds/{id}/.
        """
        params: Dict[str, Any] = {}
        if fields:
            params["fields"] = ",".join(fields)

        with self._client() as client:
            resp = client.get(f"/sounds/{sound_id}/", params=params)
            resp.raise_for_status()
            return resp.json()

    def paged_search(
        self,
        query: str,
        *,
        page_size: int = 50,
        max_pages: Optional[int] = None,
        fields: Optional[Iterable[str]] = None,
    ) -> Iterable[Dict[str, Any]]:
        """
        Convenience generator over search pages.

        Yields each page's JSON response in order until there are no results
        or max_pages is reached.
        """
        page = 1
        pages_yielded = 0

        while True:
            if max_pages is not None and pages_yielded >= max_pages:
                break

            data = self.search_text(
                query=query,
                page=page,
                page_size=page_size,
                fields=fields,
            )
            yield data

            results: List[Any] = data.get("results") or []
            if not results or not data.get("next"):
                break

            page += 1
            pages_yielded += 1

