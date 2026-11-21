"""Télécharge la documentation officielle Odoo, une copie par version.

    python -m odoo_assistant.ingestion.download

Le dépôt complet pèse plusieurs Go (images, traductions, historique). On ne
récupère donc que le dernier commit de chaque branche et que les fichiers .rst.
Relancer la commande met à jour une copie déjà présente.
"""
import subprocess
from pathlib import Path

from odoo_assistant import config

# Seuls les fichiers texte de la doc nous intéressent.
SPARSE_PATTERNS = ["/content/**/*.rst", "/content/*.rst"]


def git(*args: str, cwd: Path | None = None) -> str:
    """Lance une commande git et renvoie sa sortie ; lève une erreur si elle échoue."""
    result = subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    )
    return result.stdout.strip()


def current_commit(repo_dir: Path) -> str:
    """Identifiant du commit de la doc téléchargée (traçabilité des sources)."""
    return git("rev-parse", "HEAD", cwd=repo_dir)


def download_version(version: str) -> Path:
    """Clone (ou met à jour) la branche `version` dans data/raw/<version>."""
    target = config.RAW_DIR / version
    if (target / ".git").exists():
        print(f"[{version}] déjà présent, mise à jour...")
        git("fetch", "--depth", "1", "origin", version, cwd=target)
        git("reset", "--hard", "FETCH_HEAD", cwd=target)
    else:
        print(f"[{version}] téléchargement...")
        target.parent.mkdir(parents=True, exist_ok=True)
        git(
            "clone", "--depth", "1", "--filter=blob:none", "--no-checkout",
            "--branch", version, config.DOCS_REPO_URL, str(target),
        )
        git("sparse-checkout", "set", "--no-cone", *SPARSE_PATTERNS, cwd=target)
        git("checkout", version, cwd=target)

    n_files = sum(1 for _ in (target / "content").rglob("*.rst"))
    print(f"[{version}] {n_files} fichiers .rst, commit {current_commit(target)[:10]}")
    return target


def main() -> None:
    for version in config.VERSIONS:
        download_version(version)


if __name__ == "__main__":
    main()
