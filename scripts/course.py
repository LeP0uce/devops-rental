#!/usr/bin/env python3
"""Commandes locales portables du cours DevOps (service Rental).

Usage : python scripts/course.py <commande>
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JAVA_DIR = ROOT / "apps" / "car-rental-service"
PYTHON_DIR = ROOT / "apps" / "pricing-service"
COMPOSE_FILE = ROOT / "compose.yaml"
WORKFLOW_DIR = ROOT / ".github"

CAR_RENTAL_URL = os.environ.get("CAR_RENTAL_URL", "http://localhost:8080")
PRICING_URL = os.environ.get("PRICING_URL", "http://localhost:8000")


class CommandFailed(Exception):
    """Une commande externe ou un contrôle a échoué."""


def gradlew() -> str:
    """gradlew.bat sous Windows (chemin absolu requis), ./gradlew ailleurs."""
    return str(JAVA_DIR / "gradlew.bat") if os.name == "nt" else "./gradlew"


def run(command: list[str], cwd: Path = ROOT) -> None:
    print(f"\n$ {' '.join(command)}   (dans {cwd.relative_to(ROOT) or '.'})", flush=True)
    result = subprocess.run(command, cwd=cwd, check=False)
    if result.returncode != 0:
        raise CommandFailed(f"échec ({result.returncode}) : {' '.join(command)}")


# --- prérequis ---------------------------------------------------------------


def prerequisites() -> None:
    missing = []
    for tool, args in (("java", ["-version"]), ("docker", ["--version"])):
        if shutil.which(tool) is None:
            missing.append(tool)
            continue
        subprocess.run([tool, *args], check=False)
    print(f"python {sys.version.split()[0]} ({sys.executable})")
    if missing:
        raise CommandFailed(f"outils manquants : {', '.join(missing)}")


# --- tests -------------------------------------------------------------------


def test_java() -> None:
    run([gradlew(), "clean", "test"], cwd=JAVA_DIR)


def test_python() -> None:
    run([sys.executable, "-m", "pytest"], cwd=PYTHON_DIR)


def test() -> None:
    test_java()
    test_python()


# --- qualité -----------------------------------------------------------------


def lint_java() -> None:
    run([gradlew(), "checkstyleMain", "checkstyleTest"], cwd=JAVA_DIR)


def lint_python() -> None:
    run([sys.executable, "-m", "ruff", "check", "app", "tests"], cwd=PYTHON_DIR)
    run([sys.executable, "-m", "ruff", "format", "--check", "app", "tests"], cwd=PYTHON_DIR)


def lint() -> None:
    lint_java()
    lint_python()


# --- politique de chaîne logicielle ------------------------------------------

USES_RE = re.compile(r"""^\s*(?:-\s*)?uses:\s*["']?([^"'\s#]+)""")
FULL_SHA_RE = re.compile(r"@[0-9a-f]{40}$")
DIGEST_RE = re.compile(r"@sha256:[0-9a-f]{64}$")
FROM_RE = re.compile(r"^\s*FROM\s+(?:--\S+\s+)*(\S+)(?:\s+AS\s+(\S+))?", re.IGNORECASE)
IGNORED_DIRS = {".git", ".venv", "build", ".gradle", "node_modules"}


def iter_files(base: Path, predicate) -> list[Path]:
    found = []
    for path in base.rglob("*"):
        if path.is_file() and not IGNORED_DIRS.intersection(path.relative_to(ROOT).parts) and predicate(path):
            found.append(path)
    return sorted(found)


def check_uses(reference: str) -> str | None:
    """Retourne un message d'erreur si la référence d'action n'est pas immuable."""
    if reference.startswith("./"):
        return None  # action locale : versionnée avec le dépôt
    if reference.startswith("docker://"):
        return None if DIGEST_RE.search(reference) else "image docker:// sans digest sha256"
    if "@" not in reference:
        return "action distante sans version"
    return None if FULL_SHA_RE.search(reference) else "action distante sans SHA complet (40 caractères)"


def check_from(image: str, stages: set[str]) -> str | None:
    """Retourne un message d'erreur si l'image de base n'est pas épinglée par digest."""
    if image.lower() == "scratch" or image in stages:
        return None  # pas de registre ou étape précédente du même Dockerfile
    return None if DIGEST_RE.search(image) else "FROM sans digest sha256"


def supply_chain_policy() -> None:
    violations: list[str] = []
    workflows = iter_files(WORKFLOW_DIR, lambda p: p.suffix in {".yml", ".yaml"})
    for path in workflows:
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            match = USES_RE.match(line)
            if match and (error := check_uses(match.group(1))):
                violations.append(f"{path.relative_to(ROOT)}:{number}: {error} : {match.group(1)}")
    dockerfiles = iter_files(ROOT, lambda p: p.name == "Dockerfile" or p.name.endswith(".Dockerfile"))
    for path in dockerfiles:
        stages: set[str] = set()
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            match = FROM_RE.match(line)
            if not match:
                continue
            image, alias = match.group(1), match.group(2)
            if error := check_from(image, stages):
                violations.append(f"{path.relative_to(ROOT)}:{number}: {error} : {image}")
            if alias:
                stages.add(alias)
    print(f"{len(workflows)} fichier(s) YAML sous .github, {len(dockerfiles)} Dockerfile(s) analysés")
    for violation in violations:
        print(f"  ✗ {violation}")
    if violations:
        raise CommandFailed(f"{len(violations)} référence(s) mutable(s)")
    print("ok  toutes les références sont immuables")


def verify() -> None:
    """Portes locales : tests, qualité puis politique de références.

    S'arrête au premier échec. Ne construit pas les images, ne lance pas
    Gitleaks et ne vérifie pas la protection de branche : ces responsabilités
    restent dans GitHub Actions.
    """
    test()
    lint()
    supply_chain_policy()


# --- docker compose ----------------------------------------------------------


def compose_up() -> None:
    run(["docker", "compose", "-f", str(COMPOSE_FILE), "up", "--build", "--detach"])


def compose_down() -> None:
    run(["docker", "compose", "-f", str(COMPOSE_FILE), "down", "--remove-orphans"])


def http_get_json(url: str) -> object:
    with urllib.request.urlopen(url, timeout=5) as response:
        if response.status != 200:
            raise CommandFailed(f"{url} a répondu {response.status}")
        return json.loads(response.read().decode("utf-8"))


def wait_for(url: str, timeout: float = 60.0) -> None:
    deadline = time.monotonic() + timeout
    while True:
        try:
            http_get_json(url)
            return
        except (urllib.error.URLError, ConnectionError, CommandFailed):
            if time.monotonic() > deadline:
                raise CommandFailed(f"{url} indisponible après {timeout:.0f} s") from None
            time.sleep(1)


def smoke() -> None:
    for base in (CAR_RENTAL_URL, PRICING_URL):
        wait_for(f"{base}/health")
        health = http_get_json(f"{base}/health")
        if health != {"status": "UP"}:
            raise CommandFailed(f"{base}/health inattendu : {health}")
        cars = http_get_json(f"{base}/cars")
        if not isinstance(cars, list) or not cars:
            raise CommandFailed(f"{base}/cars ne retourne pas de liste non vide")
        print(f"ok  {base}/health et {base}/cars")
    quote = http_get_json(f"{PRICING_URL}/quote?category=standard&days=2")
    if not isinstance(quote, dict) or quote.get("total") != 120 or quote.get("currency") != "EUR":
        raise CommandFailed(f"cotation standard 2 jours inattendue : {quote}")
    print("ok  cotation standard 2 jours = 120 EUR")


COMMANDS = {
    "prerequisites": (prerequisites, "Vérifie la présence de Python, Java et Docker"),
    "test-java": (test_java, "Exécute gradlew clean test dans le service Java"),
    "test-python": (test_python, "Exécute Pytest avec l'interpréteur Python courant"),
    "test": (test, "Lance les tests Java, puis les tests Python"),
    "lint-java": (lint_java, "Exécute Checkstyle sur le service Java"),
    "lint-python": (lint_python, "Exécute Ruff (lint et formatage) sur le service Python"),
    "lint": (lint, "Lance les contrôles qualité Java, puis Python"),
    "supply-chain-policy": (
        supply_chain_policy,
        "Échoue si une action n'est pas épinglée par SHA ou un FROM sans digest",
    ),
    "verify": (verify, "Reproduit les portes locales : tests, qualité, politique"),
    "compose-up": (compose_up, "Construit et démarre l'environnement Docker Compose"),
    "compose-down": (compose_down, "Arrête l'environnement Docker Compose"),
    "smoke": (smoke, "Vérifie les endpoints des deux services et une cotation attendue"),
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True, metavar="commande")
    for name, (_, help_text) in COMMANDS.items():
        sub.add_parser(name, help=help_text)
    args = parser.parse_args(argv)
    try:
        COMMANDS[args.command][0]()
    except CommandFailed as error:
        print(f"\nÉCHEC : {error}", file=sys.stderr)
        return 1
    print(f"\nOK : {args.command}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
