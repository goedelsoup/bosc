"""POI geocoding connectors.

Free/public-domain geocoders that turn a place reference into a point, reusing the
shared connector cache (``bosc.connectors.cached_get``) against the POI cache root —
the same neutral layer ``civic``/``economics`` use. Pure sync
``fn(..., settings) -> pydantic``; the network call stays inside the ``fetch`` callable.
"""
