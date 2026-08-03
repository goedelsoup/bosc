"""Stable document handles (#1887) — the Python half of the routing-key axis.

A source document is addressed by an opaque 8-character handle derived from its
``data/documents`` rel, not by its path. The as-received path stays untouched on disk and stays
on the page as the custody record; this module only mints the address.

This is a **transcription** of ``web/packages/core/src/documentId.ts``, not an independent
implementation — see that module for why the handle is derived rather than assigned and why the
hash is FNV-1a rather than SHA-256 (the short version: the Cloudflare Pages redirect cap makes a
lookup table impossible, and the same handle has to be computable in Node, the Workers runtime,
and here). Any change to one side must be made to the other in the same commit.

The two are held together by the golden vectors in
``web/packages/core/src/__fixtures__/document-id-vectors.json``, asserted from
``tests/test_site_document_id.py`` and from ``documentId.test.ts``. A drift between the runtimes
would not raise — it would silently 404 every citation — so the vectors are the guard.

Python needs this because retrieval cites documents: the MCP ``search_passages`` tool and the
``/ask`` index emit a document's address alongside its passage.
"""

from __future__ import annotations

from typing import Final

# FNV-1a, 64-bit.
_FNV_OFFSET_BASIS: Final = 0xCBF29CE484222325
_FNV_PRIME: Final = 0x100000001B3
_MASK_64: Final = 0xFFFFFFFFFFFFFFFF

# Crockford base32, lower-cased for URLs — no i/l/o/u, so a handle read aloud or re-typed from a
# filing can't collide through 1/l or 0/O. These handles end up in citations that outlive the build.
_ALPHABET: Final = "0123456789abcdefghjkmnpqrstvwxyz"

#: Handle width in characters: 8 x 5 bits = the 40 bits taken off the hash.
DOCUMENT_ID_LENGTH: Final = 8

#: Bits discarded from the 64-bit hash to leave a whole number of base32 characters.
_DISCARDED_BITS: Final = 64 - DOCUMENT_ID_LENGTH * 5

#: Curated handle pins — the escape hatch for a document that **moves** to a different rel and
#: must keep the handle it was already cited under. Must stay byte-identical to
#: ``DOCUMENT_ID_PINS`` in ``documentId.ts``; the vector fixture covers the derivation, this dict
#: is covered by ``test_pins_match_frontend``.
DOCUMENT_ID_PINS: Final[dict[str, str]] = {}


def _fnv1a64(value: str) -> int:
    """FNV-1a over the UTF-8 bytes of ``value``."""
    digest = _FNV_OFFSET_BASIS
    for byte in value.encode("utf-8"):
        digest = ((digest ^ byte) * _FNV_PRIME) & _MASK_64
    return digest


def _encode_base32(value: int) -> str:
    """Big-endian Crockford base32 of the low ``DOCUMENT_ID_LENGTH * 5`` bits of ``value``."""
    out: list[str] = []
    remaining = value
    for _ in range(DOCUMENT_ID_LENGTH):
        out.append(_ALPHABET[remaining & 31])
        remaining >>= 5
    return "".join(reversed(out))


def document_id(rel: str) -> str:
    """The stable handle for a ``data/documents`` rel.

    Takes the rel **verbatim**, exactly as it appears in the documents feed: no case folding, no
    separator normalization, no URL decoding. The rel is the as-received chain-of-custody path,
    and normalizing here would be a second, silently-diverging definition of it.
    """
    pinned = DOCUMENT_ID_PINS.get(rel)
    if pinned is not None:
        return pinned
    return _encode_base32(_fnv1a64(rel) >> _DISCARDED_BITS)


def doc_permalink(document: str) -> str:
    """The site-relative permalink for a handle (``/doc/<id>/``), carrying no site base."""
    return f"/doc/{document}/"


def doc_permalink_for_rel(rel: str) -> str:
    """``doc_permalink(document_id(rel))`` — the common one-step call."""
    return doc_permalink(document_id(rel))
