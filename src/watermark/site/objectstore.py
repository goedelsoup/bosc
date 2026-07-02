"""Upload the source-document corpus into the R2 object store (epic #274, B3 / #279).

The bytes behind the ``/api/doc`` Pages Function (B2 / #278): ``bosc objectstore sync``
walks ``data/documents/**`` and PUTs each file into a Cloudflare R2 bucket
(S3-compatible), keyed by its ``data/documents`` rel. It is:

* **incremental** — skips an object whose remote size + ETag already match (so reruns
  upload nothing and only hash a file whose size already matches);
* **LFS-aware** — refuses to upload an unresolved Git-LFS pointer (a 130-byte stub) and
  reports it so the operator runs ``git lfs pull``;
* **type-stamping** — sets each object's ``Content-Type`` + ``media_type``/``render_class``
  metadata (from A1 / #275) so B2 serves the right type without re-sniffing.

The transport is a tiny SigV4-signed :mod:`httpx` client (no boto3 dependency); all the
upload-*decision* logic is pure and unit-tested against a fake store. Chain of custody:
this only reads source bytes — it never alters one.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol
from urllib.parse import quote

import httpx

from watermark.config import Settings
from watermark.connectors._sigv4 import sigv4_authorization
from watermark.logging import get_logger
from watermark.site.documents import build_documents

log = get_logger(__name__)

# sha256 of the empty string (the payload hash for a bodyless HEAD request).
_EMPTY_SHA256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
# Over HTTPS, S3/R2 accept an unhashed payload — avoids hashing a 137 MB body twice.
_UNSIGNED_PAYLOAD = "UNSIGNED-PAYLOAD"


class ObjectStoreUnconfiguredError(RuntimeError):
    """Raised when the R2 credentials/endpoint aren't set (WATERMARK_DOCUMENTS_OBJECT_STORE_*)."""


# --- the work list (pure) -----------------------------------------------------
@dataclass(frozen=True)
class SyncItem:
    """One source file queued for the object store; ``rel`` is also the R2 object key."""

    rel: str  # data/documents-relative path (the chain-of-custody name) == the R2 key
    path: Path
    size: int
    media_type: str
    render_class: str
    available: bool  # False == an unresolved Git-LFS pointer (don't upload the stub)


def corpus_items(documents_dir: Path, *, collection: str | None = None) -> list[SyncItem]:
    """Every catalogued source file as a :class:`SyncItem`, reusing the documents catalog.

    ``collection`` scopes to one ``data/documents/<slug>`` for a lighter dev loop; the
    default is the full corpus (the dev-full decision in epic #274).
    """
    result = build_documents(documents_dir)
    items: list[SyncItem] = []
    for coll in result.collections:
        if collection is not None and coll.slug != collection:
            continue
        for e in coll.entries:
            items.append(
                SyncItem(
                    rel=e.rel,
                    path=documents_dir / e.rel,
                    size=e.size_bytes,
                    media_type=e.media_type,
                    render_class=e.render_class,
                    available=e.available,
                )
            )
    return items


# --- store protocol + sync plan ----------------------------------------------
@dataclass(frozen=True)
class RemoteHead:
    """What a HEAD reveals about an existing object."""

    size: int
    etag: str  # the ETag, quotes stripped (== the body MD5 for a single-part PUT)


class ObjectStore(Protocol):
    """The minimal store surface the sync logic needs (HEAD to compare, PUT to upload)."""

    def head(self, key: str) -> RemoteHead | None: ...
    def put(
        self, key: str, body: bytes, *, content_type: str, metadata: dict[str, str]
    ) -> None: ...


@dataclass
class SyncPlan:
    """What a sync would do: upload these, skip those (already current / LFS pointer)."""

    upload: list[SyncItem] = field(default_factory=list)
    unchanged: list[SyncItem] = field(default_factory=list)
    lfs_skipped: list[SyncItem] = field(default_factory=list)

    @property
    def upload_bytes(self) -> int:
        return sum(i.size for i in self.upload)


def md5_hex(path: Path) -> str:
    """Streaming MD5 of a file (matches an R2 single-part-PUT ETag)."""
    digest = hashlib.md5()  # matches the S3 ETag (not a security hash)
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def plan_sync(
    items: list[SyncItem],
    store: ObjectStore,
    *,
    hasher: Callable[[Path], str] = md5_hex,
) -> SyncPlan:
    """Decide what to upload: skip LFS pointers, skip objects whose size + ETag match.

    The local hash is computed only when a remote object of the *same size* already
    exists (Python short-circuits ``and``), so a no-change rerun never hashes a file
    whose size already differs — and an empty bucket never hashes at all.
    """
    plan = SyncPlan()
    for it in items:
        if not it.available:
            plan.lfs_skipped.append(it)
            continue
        head = store.head(it.rel)
        if head is not None and head.size == it.size and head.etag == hasher(it.path):
            plan.unchanged.append(it)
            continue
        plan.upload.append(it)
    return plan


@dataclass
class SyncResult:
    uploaded: int
    unchanged: int
    lfs_skipped: int
    uploaded_bytes: int


def run_sync(
    items: list[SyncItem],
    store: ObjectStore,
    *,
    dry_run: bool = False,
    on_upload: Callable[[SyncItem], None] | None = None,
    hasher: Callable[[Path], str] = md5_hex,
) -> tuple[SyncPlan, SyncResult]:
    """Plan, then (unless ``dry_run``) upload the changed files, stamping type metadata."""
    plan = plan_sync(items, store, hasher=hasher)
    uploaded = 0
    uploaded_bytes = 0
    if not dry_run:
        for it in plan.upload:
            store.put(
                it.rel,
                it.path.read_bytes(),
                content_type=it.media_type,
                metadata={"media_type": it.media_type, "render_class": it.render_class},
            )
            uploaded += 1
            uploaded_bytes += it.size
            if on_upload is not None:
                on_upload(it)
    return plan, SyncResult(
        uploaded=uploaded,
        unchanged=len(plan.unchanged),
        lfs_skipped=len(plan.lfs_skipped),
        uploaded_bytes=uploaded_bytes,
    )


# --- SigV4-signed R2 transport ------------------------------------------------
# The signer itself is neutral machinery, hoisted to watermark.connectors._sigv4 (#1079)
# and re-exported here for the existing objectstore callers/tests.


class R2Store:
    """A minimal SigV4-signed S3 client for one R2 bucket — HEAD + PUT only."""

    def __init__(
        self,
        *,
        account_id: str,
        bucket: str,
        access_key_id: str,
        secret_access_key: str,
        endpoint: str = "",
        region: str = "auto",
        client: httpx.Client | None = None,
    ) -> None:
        if not (access_key_id and secret_access_key and (endpoint or account_id)):
            raise ObjectStoreUnconfiguredError(
                "R2 object store is not configured — set WATERMARK_DOCUMENTS_OBJECT_STORE_* "
                "(account id + S3 access key id/secret). See docs/object-store.md."
            )
        self._endpoint = (endpoint or f"https://{account_id}.r2.cloudflarestorage.com").rstrip("/")
        self._bucket = bucket
        self._host = httpx.URL(self._endpoint).host
        self._access_key = access_key_id
        self._secret = secret_access_key
        self._region = region
        self._client = client or httpx.Client(timeout=300.0)

    def _key_path(self, key: str) -> str:
        return quote(key, safe="/")

    def _url(self, key: str) -> str:
        return f"{self._endpoint}/{self._bucket}/{self._key_path(key)}"

    def _auth_headers(
        self, method: str, key: str, payload_hash: str, extra: dict[str, str]
    ) -> dict[str, str]:
        now = datetime.now(UTC)
        amzdate = now.strftime("%Y%m%dT%H%M%SZ")
        headers = {
            "host": self._host,
            "x-amz-content-sha256": payload_hash,
            "x-amz-date": amzdate,
            **extra,
        }
        auth = sigv4_authorization(
            method=method,
            canonical_uri=f"/{self._bucket}/{self._key_path(key)}",
            canonical_querystring="",
            headers=headers,
            payload_hash=payload_hash,
            access_key=self._access_key,
            secret_key=self._secret,
            amzdate=amzdate,
            datestamp=amzdate[:8],
            region=self._region,
        )
        return {**headers, "authorization": auth}

    def head(self, key: str) -> RemoteHead | None:
        headers = self._auth_headers("HEAD", key, _EMPTY_SHA256, {})
        resp = self._client.request("HEAD", self._url(key), headers=headers)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return RemoteHead(
            size=int(resp.headers.get("content-length", "0")),
            etag=resp.headers.get("etag", "").strip('"'),
        )

    def put(self, key: str, body: bytes, *, content_type: str, metadata: dict[str, str]) -> None:
        extra = {"content-type": content_type}
        # S3 user metadata: x-amz-meta-* headers; underscores → hyphens for proxy safety.
        for k, v in metadata.items():
            extra[f"x-amz-meta-{k.replace('_', '-')}"] = v
        headers = self._auth_headers("PUT", key, _UNSIGNED_PAYLOAD, extra)
        resp = self._client.request("PUT", self._url(key), headers=headers, content=body)
        resp.raise_for_status()


def store_from_settings(settings: Settings, *, target: str) -> R2Store:
    """Build the R2 client for ``--target {local,remote}`` (dev vs prod bucket)."""
    bucket = (
        settings.documents_object_store_bucket
        if target == "remote"
        else settings.documents_object_store_dev_bucket
    )
    return R2Store(
        account_id=settings.documents_object_store_account_id,
        bucket=bucket,
        access_key_id=settings.documents_object_store_access_key_id,
        secret_access_key=settings.documents_object_store_secret_access_key,
        endpoint=settings.documents_object_store_endpoint,
    )
