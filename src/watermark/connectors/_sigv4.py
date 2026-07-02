"""AWS Signature Version 4 — the one signing primitive shared by every AWS-speaking client.

Grew up inside :mod:`watermark.site.objectstore` (the R2 transport, which re-exports it
unchanged); hoisted here so the GreenOps AWS connector (#1079) signs Cost Explorer /
Sustainability API requests with the same tested code instead of a second copy. Pure and
deterministic — no I/O, no config; the caller supplies every input (tested against the
published AWS SigV4 reference vector in ``tests/test_objectstore.py``). Still no boto3
dependency anywhere in the repo.
"""

from __future__ import annotations

import hashlib
import hmac


def _hmac(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def _signing_key(secret: str, datestamp: str, region: str, service: str) -> bytes:
    k = _hmac(("AWS4" + secret).encode("utf-8"), datestamp)
    k = _hmac(k, region)
    k = _hmac(k, service)
    return _hmac(k, "aws4_request")


def sigv4_authorization(
    *,
    method: str,
    canonical_uri: str,
    canonical_querystring: str,
    headers: dict[str, str],
    payload_hash: str,
    access_key: str,
    secret_key: str,
    amzdate: str,
    datestamp: str,
    region: str = "auto",
    service: str = "s3",
) -> str:
    """The AWS SigV4 ``Authorization`` header value for one request.

    ``headers`` are the headers to sign (must include ``host``, ``x-amz-date``, and every
    ``x-amz-*`` header sent). Pure and deterministic — tested against the published AWS
    SigV4 reference vector.
    """
    canonical = sorted((k.lower(), v.strip()) for k, v in headers.items())
    canonical_headers = "".join(f"{k}:{v}\n" for k, v in canonical)
    signed_headers = ";".join(k for k, _ in canonical)
    canonical_request = "\n".join(
        [
            method,
            canonical_uri,
            canonical_querystring,
            canonical_headers,
            signed_headers,
            payload_hash,
        ]
    )
    cr_hash = hashlib.sha256(canonical_request.encode("utf-8")).hexdigest()
    scope = f"{datestamp}/{region}/{service}/aws4_request"
    string_to_sign = "\n".join(["AWS4-HMAC-SHA256", amzdate, scope, cr_hash])
    signature = hmac.new(
        _signing_key(secret_key, datestamp, region, service),
        string_to_sign.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return (
        f"AWS4-HMAC-SHA256 Credential={access_key}/{scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )
