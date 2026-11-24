# TP 01 — une CI observable et bloquante

> Description de la pull request `tp/01-ci` → `main`.
> Les valeurs marquées **⏱ à relever** ne s'obtiennent qu'après une exécution
> réelle sur GitHub : complétez-les depuis l'onglet *Actions*.

## Ce que change cette PR

| Avant (`checkpoint/00-starter`) | Après |
|---|---|
| Un seul job par service : tests puis build/push | Trois jobs : `tests` et `quality` en parallèle, puis `image` (`needs`) |
| Aucune porte qualité | Checkstyle (Java) et Ruff lint + format (Python) |
| Permissions implicites du `GITHUB_TOKEN` | `contents: read` au niveau workflow, `packages: write` seulement sur `image` |
| Pas de timeout, pas de cache, pas de concurrence | `timeout-minutes` partout, cache Gradle/pip/Buildx, annulation des runs obsolètes |
| Login GHCR même sur PR | Login et push uniquement sur `push` vers `main` |
| Seul le log en cas d'échec | Rapports JUnit, Pytest, Checkstyle, Ruff, Gitleaks en artefacts (`if: always()`, 7 jours) |
| Pas de détection de secrets | Workflow `Secret detection` (Gitleaks, historique complet) |
| Reproduction locale partielle | `python scripts/course.py verify` |

## Inventaire des jobs

| Job | Risque couvert | Entrées | Sortie | Coût approximatif |
|---|---|---|---|---|
| `Java tests` | régression fonctionnelle du service de location | sources Java, Gradle wrapper, JDK 21 | statut + rapports JUnit XML/HTML | ~1 min (≈ 2 min sans cache Gradle) |
| `Java quality` | dette de style, imports morts, `if` sans accolades | sources Java, `config/checkstyle/checkstyle.xml` | statut + rapports Checkstyle XML/HTML | ~45 s |
| `Java Docker image` | Dockerfile cassé, image non constructible | contexte `apps/car-rental-service` | image (poussée seulement sur `main`) | ~1–2 min (cache Buildx gha) |
| `Python tests` | régression de tarification (ex. cotation 120 EUR) | sources Python, `requirements-dev.txt` | statut + `pytest-junit.xml` | ~30 s |
| `Python quality` | erreurs pyflakes, imports mal triés, formatage | sources Python, `pyproject.toml` | statut + `ruff-junit.xml` | ~20 s |
| `Python Docker image` | image non constructible | contexte `apps/pricing-service` | image (poussée seulement sur `main`) | ~1 min |
| `Secret detection` | fuite de secret dans n'importe quel commit | historique Git complet | statut + `gitleaks.sarif` | ~15 s |

Le pipeline initial ne contenait qu'un job `build` par service : ni rapport, ni
séparation, et un échec de test empêchait de savoir si la qualité ou l'image
étaient correctes.

## §1 — Observer un échec

Commits `test(pricing): casser temporairement…` puis `test(pricing): rétablir…`.

1. **Quel job échoue en premier ?** Sur le pipeline initial : le job unique
   `build` du workflow *Python service*, à l'étape *Tests*. Avec le nouveau
   graphe : `Python tests` ; `Python quality` reste vert en parallèle et
   `Python Docker image` est *skipped* (dépendance `needs`).
2. **Quelle ligne identifie la cause ?**
   `E  AssertionError: assert Decimal('120.00') == Decimal('125.00')` suivie de
   `FAILED tests/test_pricing.py::test_standard_two_days_costs_120`.
3. **Un rapport structuré reste-t-il disponible ?** Sur le pipeline initial :
   **non**, seul le log brut. Après cette PR : **oui**, l'artefact
   `python-test-reports` (`pytest-junit.xml`) est téléversé grâce à
   `if: always()`.
4. **Temps de retour :** ⏱ à relever (ordre de grandeur attendu : ~1 min
   jusqu'à l'échec de `Python tests`, contre ~2 min pour le job monolithique
   qui installait tout avant d'échouer).

## §2 — Portes qualité

- **Checkstyle 14.4.0** (`apps/car-rental-service/config/checkstyle/checkstyle.xml`) :
  `UnusedImports`, `NeedBraces`, `EmptyStatement`, `LineLength` (120), plus
  `AvoidStarImport`, `RedundantImport`, `EmptyBlock`, `OneStatementPerLine`…
  Sévérité `error` et `maxWarnings = 0` : toute violation casse le build.
  Une violation réelle (ligne de 123 caractères dans un test) a été **corrigée**,
  pas désactivée. Une exception locale reste possible via
  `@SuppressWarnings("checkstyle:<règle>")` + commentaire de justification
  (filtre `SuppressWarningsFilter`).
- **Ruff 0.17.6** : familles `E`, `F`, `I` (minimum) + `B` (bugbear) et `UP`
  (pyupgrade), `ruff format --check`. Correction de l'ordre des imports de
  `app/main.py`. Aucune règle désactivée.

## §3 — Graphe CI

```text
Python tests ────┐                      Java tests ────┐
                 ├──> Python Docker image              ├──> Java Docker image
Python quality ──┘                      Java quality ──┘

Secret detection (workflow indépendant)
```

- `timeout-minutes` sur chaque job ;
- `permissions: contents: read` au niveau workflow ; `packages: write`
  uniquement sur le job image ;
- `concurrency` par workflow et par PR, `cancel-in-progress` sur PR seulement
  (sur `main`, chaque commit doit produire son image) ;
- caches : `setup-java` (`cache: gradle`), `setup-python` (`cache: pip`),
  Buildx `type=gha` ;
- aucune publication depuis une PR : `docker/login-action` et `push:` sont
  conditionnés à `github.event_name == 'push' && github.ref == 'refs/heads/main'`.
  En plus, sur une PR venant d'un fork, le `GITHUB_TOKEN` est en lecture seule.

**Pourquoi pas de filtre `paths` sur `pull_request` ?** Un contrôle requis par
la protection de branche doit *rapporter un statut*. Si `python.yml` ne se
déclenche que sur `apps/pricing-service/**`, une PR qui ne modifie que le
service Java ne produit jamais `Python tests` : GitHub l'affiche « Expected —
Waiting for status to be reported » et la PR est **bloquée pour toujours**.
Inversement, si on retire ce check des contrôles requis pour éviter le blocage,
une PR qui casse le service Python par un fichier partagé (ex. `compose.yaml`)
passerait sans test. Solutions possibles : pas de filtre (choix retenu, coût
faible ici), ou un job « garde » toujours exécuté qui calcule les chemins
modifiés et saute les étapes coûteuses tout en rapportant un statut vert.

## §4 — Preuves

| Artefact | Contenu | Job |
|---|---|---|
| `java-test-reports` | `build/test-results/test/*.xml`, rapport HTML | Java tests |
| `java-checkstyle-reports` | `main.xml`, `test.xml`, HTML | Java quality |
| `python-test-reports` | `pytest-junit.xml` | Python tests |
| `python-ruff-reports` | `ruff-junit.xml` | Python quality |
| `gitleaks-report` | `gitleaks.sarif` | Secret detection |

Tous en `if: always()` et `retention-days: 7`. Vérification sur un échec :
⏱ à relever (provoquer un échec, ouvrir l'onglet *Summary* de l'exécution,
section *Artifacts*, télécharger `python-test-reports`).

## §5 — Secrets

Workflow `secret-detection.yml` : `fetch-depth: 0`, Gitleaks 8.30.1 dont le
binaire est vérifié par SHA-256, `--redact` pour ne jamais réafficher la
valeur, rapport SARIF en artefact. Exécuté sur PR, sur `main` et chaque
semaine (de nouvelles règles peuvent révéler d'anciens secrets).

Aucun vrai secret n'a été introduit. Le test avec la valeur factice de
l'enseignant se fait sur une branche jetable, supprimée ensuite.

| Action | Ce que ça règle | Ce que ça ne règle pas |
|---|---|---|
| **Supprimer la ligne fautive** | le secret n'est plus dans la version courante | il reste dans l'historique, les forks, les clones, les caches CI : **il est toujours compromis** |
| **Révoquer le secret** | le secret volé devient inutilisable — **c'est l'action prioritaire et la seule indispensable** | Gitleaks continue de le signaler dans l'historique (à documenter via `.gitleaksignore` après révocation) |
| **Réécrire l'historique** (`git filter-repo`, force-push) | le secret disparaît des futurs clones | casse les clones existants, ne nettoie ni les forks ni les copies déjà faites ; ne remplace jamais la révocation |

Ordre correct : révoquer et remplacer → supprimer la ligne → réécrire
l'historique seulement si la politique l'exige.

## §6 — Reproduction locale

```bash
python scripts/course.py verify
```

`verify` = `test-java`, `test-python`, `lint-java`, `lint-python`. Arrêt au
premier échec avec code `1` (vérifié en ajoutant un `import os` inutilisé).
Ne couvre pas : construction d'images, Gitleaks, publication des rapports,
protection de branche.

## §7 — Protection de `main` (après validation enseignant)

*Settings → Rules → Rulesets → New branch ruleset*, cible `main` :
« Require a pull request », « Require status checks to pass » avec :

- `Java tests`, `Java quality`, `Java Docker image`
- `Python tests`, `Python quality`, `Python Docker image`
- `Secret detection`

Vérification : une PR rouge (assertion cassée) affiche le bouton *Merge*
désactivé ; une fois verte, la fusion est possible. ⏱ à relever.

## Pour aller plus loin (pistes)

- Références d'actions à épingler par SHA au checkpoint suivant : **toutes**
  (`actions/checkout`, `setup-java`, `setup-python`, `upload-artifact`,
  `docker/setup-buildx-action`, `login-action`, `metadata-action`,
  `build-push-action`), en priorité celles qui reçoivent des secrets ou des
  droits d'écriture (`docker/login-action`, `docker/build-push-action`).
  Les images de base `eclipse-temurin` et `python` doivent aussi recevoir un
  digest.
