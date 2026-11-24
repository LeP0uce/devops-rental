#!/usr/bin/env python3
"""Commandes locales portables du cours DevOps (service Rental).

Usage : python scripts/course.py <commande>
"""

from __future__ import annotations

import argparse
import json
import os
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
