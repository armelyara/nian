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

## Recherche réelle (YouTube Data API)

La barre de recherche (mots-clés + lieu) interroge `GET /api/geospatial/search`,
qui appelle l'API **YouTube Data API v3**. Le lieu est géocodé (Nominatim/OSM)
pour positionner les résultats sur le globe et la carte de ville.

### Mettre la clé Google
1. Google Cloud Console → crée (ou choisis) un projet.
2. **APIs & Services → Library → active "YouTube Data API v3"**.
3. **APIs & Services → Credentials → Create credentials → API key** → copie la clé.
4. (Recommandé) Restreins la clé : *API restrictions* → "YouTube Data API v3".
5. Lance le serveur avec la clé dans l'environnement :
   ```
   export NIAN_YOUTUBE_KEY="AIza...ta_cle"
   uvicorn server:app --port 8100 --reload
   ```
   (ou ajoute l'export à ton ~/.zshrc pour qu'il persiste).

### Quota
Gratuit : ~10 000 unités/jour. Un `search.list` coûte 100 unités → ~100 recherches/jour.
