# TP 02 — produire et vérifier les preuves d'une image

> Description de la pull request `tp/02-supply-chain` → `main`.
> Les valeurs marquées **⏱ à relever** proviennent d'une exécution réelle sur
> `main` (jobs `Java supply chain` / `Python supply chain`) : complétez-les
> depuis l'onglet *Actions* et les artefacts `*-supply-chain-evidence`.

## §0 — Inventaire des références (état `checkpoint/01-ci`)

| Référence | Occurrences | Mutable ? | Pourquoi |
|---|---:|---|---|
| `actions/checkout@v7` | 7 | **mutable** | un tag Git peut être déplacé vers un autre commit |
| `actions/setup-java@v6` | 2 | **mutable** | idem |
| `actions/setup-python@v7` | 2 | **mutable** | idem |
| `actions/upload-artifact@v7` | 5 | **mutable** | idem |
| `docker/setup-buildx-action@v4` | 2 | **mutable** | idem |
| `docker/login-action@v4` | 2 | **mutable** | idem, et reçoit le `GITHUB_TOKEN` |
| `docker/metadata-action@v6` | 2 | **mutable** | idem |
| `docker/build-push-action@v7` | 2 | **mutable** | idem, et pousse l'image |
| `FROM eclipse-temurin:21-jdk-noble` | 1 | **mutable** | le tag pointe vers un nouveau manifeste à chaque rebuild amont |
| `FROM eclipse-temurin:21-jre-noble` | 1 | **mutable** | idem |
| `FROM python:3.12-slim` | 1 | **mutable** | idem |
| Gitleaks 8.30.1 (téléchargé par `curl`) | 1 | immuable | archive vérifiée par SHA-256 avant exécution |
| Gradle 9.9.2 (wrapper) | 1 | immuable | `distributionSha256Sum` dans `gradle-wrapper.properties` |

Rien n'était immuable côté actions et images de base.

## §1 — Modèle de risques

| Élément | Scénario de substitution | Impact | Contrôle qui réduit le risque |
|---|---|---|---|
| Action GitHub | un mainteneur compromis déplace `v7` vers un commit malveillant (cas réel : `tj-actions/changed-files`, mars 2025) | code arbitraire dans le job, vol du `GITHUB_TOKEN` (ici `packages: write`, `id-token: write`), image piégée | **SHA complet de 40 caractères** + Dependabot pour les montées de version revues en PR + permissions minimales |
| Image de base | le manifeste derrière `python:3.12-slim` est remplacé (registre compromis, typosquat, simple rebuild non désiré) | build non reproductible, paquets système vulnérables ou piégés hérités | **digest `@sha256:`** dans `FROM` + Dependabot `docker` + SBOM pour savoir ce qu'on a hérité |
| Image produite | `latest` est déplacé vers une autre image après le scan Trivy | on déploie une image qui n'a été ni testée, ni scannée, ni produite par notre CI | travailler sur **`image@digest`** issu de Buildx + **signature Cosign** + **provenance** liant digest ↔ dépôt ↔ commit ↔ workflow, vérifiées avant le scan |

## §2 — Références épinglées

- 14 actions distinctes, toutes en `owner/repo@<sha40> # vX.Y.Z` (SHA résolu
  depuis le tag de release, tags annotés déréférencés).
- Images de base : `tag@sha256:<digest de l'index multi-architecture>` — le tag
  reste pour la lisibilité et pour Dependabot, le digest fait foi.
- `.github/dependabot.yml` : écosystèmes `github-actions` et `docker` (requis),
  plus `pip` et `gradle`. Les mises à jour arrivent en PR ordinaires et passent
  donc par les mêmes contrôles requis.

## §3 — Politique locale

```bash
python scripts/course.py supply-chain-policy
```

Échoue (code 1) sur une action distante sans SHA complet, une image
`docker://` sans digest, ou un `FROM` sans digest (sauf `scratch` et étapes
nommées du même Dockerfile). Intégrée à `verify` et exécutée dans la CI
(workflow `Supply-chain policy`).

Observation : en réintroduisant `actions/checkout@v7` et `FROM python:3.12-slim`,
la commande liste `java.yml:36`, `:60`, `:86` et `pricing-service/Dockerfile:1`,
puis retourne 1. SHA et digest restaurés ensuite.

## §4 — Dependency review vs Trivy

| | Dependency review | Trivy |
|---|---|---|
| Quand | sur la **PR**, avant fusion | après publication, sur l'**image finale** |
| Quoi | le **diff** des manifestes (`requirements*.txt`, `build.gradle.kts`, actions…) via le graphe de dépendances | tout le contenu de l'image : paquets OS de la base, JRE, bibliothèques installées |
| Question | « ce changement introduit-il une dépendance vulnérable (≥ `high`) ou une licence interdite ? » | « ce qui va réellement tourner contient-il des CVE connues ? » |
| Angle mort | ne voit pas les paquets système de l'image de base ni ce qui n'est pas déclaré | arrive tard, ne dit pas quel changement a introduit le problème |

Les deux sont complémentaires : l'un empêche d'**ajouter** un risque,
l'autre mesure le risque **effectivement livré** (y compris celui qui
apparaît sans changement de code, par une nouvelle CVE).

Pré-requis manuel : *Settings → Advanced Security* → activer *Dependency
graph* et *Dependabot alerts*.

## §5 — SBOM

Syft (`anchore/sbom-action`) sur `ghcr.io/<owner>/<repo>/<service>@<digest>`,
le digest venant de `steps.build.outputs.digest` (sortie Buildx), format
`spdx-json`, fichiers `car-rental-service.spdx.json` et
`pricing-service.spdx.json`, artefacts `*-sbom` conservés 7 jours.

À retrouver dans un SBOM téléchargé (⏱ à relever) :

```bash
jq -r '.packages[] | "\(.name) \(.versionInfo)"' pricing-service.spdx.json | grep -E '^(libc6|openssl|fastapi|uvicorn) '
```

- paquet système attendu : `libc6` ou `openssl` (Debian, image `python:3.12-slim`) ;
- bibliothèque applicative attendue : `fastapi 0.165.0` ou `uvicorn 0.54.0`.

## §6 — Signature et attestations

Job `Java supply chain` / `Python supply chain`, `needs: image`, condition
`push` sur `main`. Permissions du job (et seulement de lui) :

| Permission | Usage |
|---|---|
| `contents: read` | minimum |
| `packages: write` | pousser la signature et les attestations dans GHCR |
| `id-token: write` | jeton OIDC → certificat Sigstore éphémère (*keyless*) |
| `attestations: write` | enregistrer les attestations dans l'API GitHub |
| `artifact-metadata: write` | *storage record* créé par `actions/attest` |

1. `sigstore/cosign-installer` ;
2. `cosign sign --yes image@digest` — aucune clé privée, aucun secret ;
3. `actions/attest` sans prédicat → provenance SLSA v1 ;
4. `actions/attest` avec `sbom-path` → attestation SBOM SPDX.

## §7 — Vérification puis scan

```bash
cosign verify \
  --certificate-identity "https://github.com/${{ github.workflow_ref }}" \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com \
  "$IMAGE@$DIGEST"

gh attestation verify "oci://$IMAGE@$DIGEST" --repo "$GITHUB_REPOSITORY" \
  --signer-workflow "$GITHUB_REPOSITORY/.github/workflows/java.yml" \
  --predicate-type https://slsa.dev/provenance/v1

gh attestation verify "oci://$IMAGE@$DIGEST" --repo "$GITHUB_REPOSITORY" \
  --predicate-type https://spdx.dev/Document/v2.3
```

L'identité est exacte (pas de `--certificate-identity-regexp`) : seule une
signature produite par **ce** workflow sur **`refs/heads/main`** est acceptée.
`--signer-workflow` et `--predicate-type` bornent `gh attestation verify`
(piste « aller plus loin » n° 2). Trivy scanne ensuite `image@digest` — le
même que celui vérifié — et non `latest`. Seuil : `HIGH,CRITICAL` avec
correctif disponible (`ignore-unfixed`) → échec du job.

Pour vérifier depuis un poste :

```bash
cosign verify \
  --certificate-identity "https://github.com/<owner>/<repo>/.github/workflows/python.yml@refs/heads/main" \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com \
  ghcr.io/<owner>/<repo>/pricing-service@sha256:<digest>
gh attestation verify oci://ghcr.io/<owner>/<repo>/pricing-service@sha256:<digest> --repo <owner>/<repo>
```

## §8 — Lecture des preuves

Exécutions de référence sur `main`, commit `8c577a1` :
[Java service](https://github.com/LeP0uce/devops-rental/actions/runs/45404437071) ·
[Python service](https://github.com/LeP0uce/devops-rental/actions/runs/45404442985).

| Preuve | `car-rental-service` | `pricing-service` |
|---|---|---|
| Digest vérifié | `sha256:facac1b5498f317943d8891fcb2b50e6a468a1eebeb448427b307468598daafe` | `sha256:7543d41a6f898d5e0534800dbce3e358787393b38a802b46b402efe28ad3ae35` |
| Identité du certificat Cosign | `https://github.com/LeP0uce/devops-rental/.github/workflows/java.yml@refs/heads/main` | `https://github.com/LeP0uce/devops-rental/.github/workflows/python.yml@refs/heads/main` |
| Émetteur OIDC | `https://token.actions.githubusercontent.com` | idem |
| Dépôt (provenance) | `https://github.com/LeP0uce/devops-rental` | idem |
| Commit (provenance) | `8c577a169dd59285e0ff596a2193563f54af5942` = `github.sha` du run | idem |
| Ref (provenance) | `refs/heads/main` | idem |
| SBOM — paquets | 140 | 110 |
| SBOM — paquet système | `libc6 2.39-0ubuntu8.12`, `openssl 3.0.13-0ubuntu3.16` (Ubuntu 24.04) | `libc6 2.41-12+deb13u5`, `openssl 3.5.9-1~deb13u1` (Debian 13) |
| SBOM — composant applicatif | `car-rental-service` (jar de l'application) | `fastapi 0.165.0`, `uvicorn 0.54.0` |
| Rapport Trivy (HIGH/CRITICAL corrigeables) | 0 vulnérabilité — artefact `car-rental-service-supply-chain-evidence` | 0 vulnérabilité — artefact `pricing-service-supply-chain-evidence` |

Le commit de la provenance est bien celui qui a déclenché le run, et le digest
signé, attesté, vérifié et scanné est le même à chaque étape.

Remarque : ces exécutions ont été lancées par `workflow_dispatch` sur `main`.
Les `push` du dépôt fraîchement créé n'ont déclenché aucun run, d'où
l'autorisation de la republication manuelle depuis `main` (jamais depuis une PR).

## Limites connues

- Les attestations GitHub sur un dépôt **privé** exigent GitHub Enterprise
  Cloud : le dépôt doit être public pour ce TP.
- Le premier push crée les paquets GHCR ; s'ils sont privés, `cosign verify`
  depuis un poste exige `docker login ghcr.io`.
- Le binaire Gitleaks est vérifié par checksum mais n'est pas couvert par
  `supply-chain-policy` (qui ne regarde que `uses:` et `FROM`).
- Les dépendances Python et Gradle sont épinglées par version, pas par hash
  (piste « aller plus loin » n° 4 : `pip install --require-hashes`,
  verrouillage Gradle `--write-locks` + vérification de dépendances).
