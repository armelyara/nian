# Nian

Standalone live map (tactical globe) in vanilla JS + Three.js (CDN),
served by FastAPI. Designed to feed entities into Indice via the
`indice:add-entity` CustomEvent.

## Run
```
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn server:app --port 8100 --reload
# open http://localhost:8100
```

## Data contract
Feed item JSON: `{ id, source, city, lat, lon, category, text, ts }`.
- Initial batch: `GET /api/geospatial/snapshot`
- Live stream (SSE): `GET /api/geospatial/stream`
- Front merges via `updateFeeds(items)`; config in `window.INDICE_GEO_CONFIG`.

Swap `_demo_item()` in `server.py` for a real public-feed collector later.
