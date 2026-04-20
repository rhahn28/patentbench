"""Minimal USPTO PEDS client for ground-truth fetching.

PEDS (Patent Examination Data System) is the authoritative public source
for prosecution events. We use it as ground truth for PatentBench Paralegal
tasks because it is externally verifiable and not produced by any LLM.

Public endpoint: https://ped.uspto.gov/api/queries
Documentation:   https://developer.uspto.gov/ped

We make GET requests with a short User-Agent, retry on 429/5xx with
exponential backoff, and never log the full response body (which can be
large). Requests are capped at 1/second to respect PEDS rate limits.

This module has no side effects on import and no global state.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx

_LOG = logging.getLogger(__name__)
PEDS_BASE = "https://ped.uspto.gov/api/queries"
USER_AGENT = "PatentBench/0.2 (+https://github.com/rhahn28/patentbench)"
DEFAULT_TIMEOUT = 30.0
RATE_LIMIT_SECONDS = 1.0


class PedsError(Exception):
    """Raised for any unrecoverable PEDS interaction failure."""


@dataclass(frozen=True)
class PedsRecord:
    """A single PEDS application record with provenance metadata."""

    application_number: str
    retrieved_at: str
    payload: dict[str, Any]
    raw_value_hash: str

    def peds_source(self, field_path: str) -> dict[str, str]:
        """Return the canonical `peds_source` block for a ground-truth row."""
        return {
            "application_number": self.application_number,
            "retrieved_at": self.retrieved_at,
            "peds_field_path": field_path,
            "raw_value_hash": self.raw_value_hash,
        }


def _sha256_of_json(data: Any) -> str:
    text = json.dumps(data, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class PedsClient:
    """Thin synchronous client around the PEDS search API.

    Intentionally synchronous. Ground-truth builds are a one-shot process
    run ahead of benchmark runs; async adds complexity with no throughput
    benefit given the 1 req/s rate limit.
    """

    def __init__(
        self,
        base_url: str = PEDS_BASE,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = 3,
        rate_limit_seconds: float = RATE_LIMIT_SECONDS,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.base_url = base_url
        self.timeout = timeout
        self.max_retries = max_retries
        self.rate_limit_seconds = rate_limit_seconds
        self._last_call: float = 0.0
        self._client = httpx.Client(
            timeout=timeout,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/json",
            },
            transport=transport,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> PedsClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_call
        wait = self.rate_limit_seconds - elapsed
        if wait > 0:
            time.sleep(wait)

    def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        last_exc: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            self._throttle()
            try:
                response = self._client.post(self.base_url, json=payload)
                self._last_call = time.monotonic()
                if response.status_code == 429:
                    retry_after = float(response.headers.get("Retry-After", "5"))
                    _LOG.warning("PEDS 429; sleeping %.1fs", retry_after)
                    time.sleep(retry_after)
                    continue
                if 500 <= response.status_code < 600:
                    backoff = 2 ** (attempt - 1)
                    _LOG.warning(
                        "PEDS %d; retry %d/%d after %ds",
                        response.status_code,
                        attempt,
                        self.max_retries,
                        backoff,
                    )
                    time.sleep(backoff)
                    continue
                response.raise_for_status()
                parsed = response.json()
                if not isinstance(parsed, dict):
                    raise PedsError(
                        f"PEDS returned non-object JSON: {type(parsed).__name__}"
                    )
                return parsed
            except httpx.HTTPError as exc:
                last_exc = exc
                backoff = 2 ** (attempt - 1)
                _LOG.warning(
                    "PEDS transport error %s; retry %d/%d after %ds",
                    type(exc).__name__,
                    attempt,
                    self.max_retries,
                    backoff,
                )
                time.sleep(backoff)
        raise PedsError(
            f"PEDS request failed after {self.max_retries} retries: {last_exc}"
        )

    def fetch_application(self, application_number: str) -> PedsRecord:
        """Fetch a single application by number. Raises PedsError on miss."""
        normalized = application_number.replace("/", "").replace(",", "")
        payload = {
            "searchText": f"applId:{normalized}",
            "fl": "*",
            "df": "patentTitle",
            "mm": "100%",
            "qf": "appEarlyPubNumber applId",
            "start": 0,
            "rows": 1,
        }
        data = self._post(payload)
        docs = (
            data.get("queryResults", {})
            .get("searchResponse", {})
            .get("response", {})
            .get("docs", [])
        )
        if not docs:
            raise PedsError(
                f"PEDS returned zero docs for application {application_number!r}"
            )
        payload_doc = docs[0]
        return PedsRecord(
            application_number=normalized,
            retrieved_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            payload=payload_doc,
            raw_value_hash=_sha256_of_json(payload_doc),
        )
