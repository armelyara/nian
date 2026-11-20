# Nian

Carte mondiale en direct de l'activité des réseaux sociaux : **globe → pays → ville**.

- Le globe tourne en continu ; molette ou pincement pour zoomer, glisser pour le tourner.
- Une vignette par ville active ; clic sur un pays ou une vignette pour descendre au pays, puis à la ville.
- Recherche « lieu + sujet » (ex. `Abidjan concert`) : le globe ne garde que les résultats et se tourne vers le lieu.
- Sans recherche, des vidéos récentes sont collectées automatiquement pour une liste de villes.

## Installation

```bash
pip install nian-map
```

## Lancer

```bash
nian --youtube-key AIza...      # puis ouvrir http://localhost:8100
nian --demo                     # sans clé : données de démonstration
nian --help                     # toutes les options
```

La clé peut aussi être mise dans l'environnement ou dans un fichier `.env` du dossier courant :

```
NIAN_YOUTUBE_KEY=AIza...
```

### Clé YouTube

Google Cloud Console → activer **YouTube Data API v3** → Identifiants → **Clé API**, à restreindre à cette API.
Quota gratuit : ≈ 10 000 unités/jour ; une recherche coûte 100 unités. Nian plafonne à 90 recherches/jour
(`NIAN_YT_DAILY_SEARCHES`), dont 20 toujours réservées aux recherches des utilisateurs.

## Configuration

| Variable | Défaut | Rôle |
|---|---|---|
| `NIAN_YOUTUBE_KEY` | — | clé YouTube Data API v3 |
| `NIAN_DEFAULT_CITIES` | Abidjan, Paris, Lagos, Dakar, Montréal, Le Caire, Tokyo, Londres | villes collectées automatiquement |
| `NIAN_REFRESH_HOURS` | 6 | fréquence de la collecte automatique |
| `NIAN_YT_DAILY_SEARCHES` | 90 | plafond quotidien de recherches YouTube |
| `NIAN_DB_PATH` | `~/.nian/nian.db` | base SQLite |
| `NIAN_API_TOKEN` | — | si défini, la recherche exige l'en-tête `X-Nian-Token` |
| `NIAN_ALLOWED_HOSTS` | — | noms d'hôte autorisés en production |
| `NIAN_RETENTION_DAYS` | 30 | durée de conservation des publications |
| `NIAN_GEOCODER_UA` | nian-map | User-Agent envoyé à Nominatim (mettre un contact) |

## Production

Derrière un reverse proxy TLS (Caddy, Nginx) :

```bash
nian --host 127.0.0.1 --port 8100
```

Un seul processus : la diffusion temps réel et la limitation de débit sont en mémoire.

## Données et licences

Cartes : Natural Earth via world-atlas (domaine public). Bibliothèques incluses : d3-geo, d3-array,
topojson-client (ISC) ; polices IBM Plex (SIL OFL 1.1).
