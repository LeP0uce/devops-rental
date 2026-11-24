# Service Rental — dépôt du cours DevOps

Deux services conteneurisés :

| Service | Langage | Port | Endpoints |
|---|---|---|---|
| `apps/car-rental-service` | Java 21 (Gradle, JDK HttpServer) | 8080 | `/health`, `/cars`, `/cars/{id}` |
| `apps/pricing-service` | Python 3.12 (FastAPI) | 8000 | `/health`, `/cars`, `/quote?category=&days=` |

## Démarrage

```bash
python -m venv .venv
.venv/bin/pip install -r apps/pricing-service/requirements-dev.txt
.venv/bin/python scripts/course.py test
```

Toutes les commandes locales passent par `scripts/course.py` :

```bash
python scripts/course.py --help
```

## Parcours Git

| Référence | Contenu |
|---|---|
| `checkpoint/00-starter` | Point de départ du TP 01 |
| `tp/01-ci` → `checkpoint/01-ci` | CI observable et bloquante |
| `tp/02-supply-chain` → `checkpoint/02-supply-chain` | Preuves de la chaîne logicielle |
