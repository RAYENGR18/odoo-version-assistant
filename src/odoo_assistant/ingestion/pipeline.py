"""Pipeline d'ingestion : fichiers .rst -> chunks avec métadonnées (JSONL).

    python -m odoo_assistant.ingestion.pipeline            # ne retraite que ce qui a changé
    python -m odoo_assistant.ingestion.pipeline --force    # retraite tout

Résultat : data/processed/chunks_<version>.jsonl (un chunk par ligne) et
data/processed/manifest.json, qui mémorise l'empreinte de chaque fichier source.
Au lancement suivant, un fichier dont l'empreinte n'a pas changé n'est pas retraité.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

from odoo_assistant import config
from odoo_assistant.ingestion.chunker import split_text
from odoo_assistant.ingestion.download import current_commit
from odoo_assistant.ingestion.rst_parser import parse_rst

MANIFEST_PATH = config.PROCESSED_DIR / "manifest.json"


def slugify(title: str) -> str:
    """Ancre HTML que Sphinx génère pour un titre : "Basic Fields" -> "basic-fields"."""
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return re.sub(r"^[-0-9]+", "", slug)


def build_chunks(version: str, rst_path: Path, content_dir: Path) -> list[dict]:
    """Transforme un fichier .rst en liste de chunks, chacun avec ses métadonnées."""
    source_file = rst_path.relative_to(content_dir).as_posix()  # developer/howtos/x.rst
    doc_id = source_file.removesuffix(".rst")
    parts = doc_id.split("/")
    page_url = f"{config.DOCS_BASE_URL}/{version}/{doc_id}.html"

    sections = parse_rst(rst_path.read_text(encoding="utf-8"))
    chunks = []
    for section in sections:
        if len(section.text) < config.MIN_CHUNK_CHARS:
            continue
        anchor = slugify(section.title) if section.level > 0 else ""
        for text in split_text(section.text, config.MAX_CHUNK_CHARS):
            chunks.append({
                # Identité
                "chunk_id": f"{version}/{doc_id}#{len(chunks):03d}",
                "version": version,
                "doc_id": doc_id,  # identique d'une version à l'autre : sert à comparer
                # Classement
                "category": parts[0],
                "subcategory": parts[1] if len(parts) > 2 else "",
                # Pour les citations
                "page_title": sections[0].title,
                "section_title": section.title,
                "section_path": section.path,
                "url": f"{page_url}#{anchor}" if anchor else page_url,
                "source_file": f"content/{source_file}",
                # Contenu
                "has_code": section.has_code,
                "n_chars": len(text),
                "content_hash": hashlib.sha1(text.encode("utf-8")).hexdigest()[:16],
                "text": text,
            })
    return chunks


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def ingest_version(version: str, manifest: dict, force: bool = False) -> dict:
    """Ingère une version et renvoie un bilan (fichiers nouveaux, modifiés...)."""
    repo_dir = config.RAW_DIR / version
    content_dir = repo_dir / "content"
    if not content_dir.exists():
        raise SystemExit(
            f"Doc {version} introuvable. Lance d'abord : "
            "python -m odoo_assistant.ingestion.download"
        )
    out_path = config.PROCESSED_DIR / f"chunks_{version}.jsonl"

    # Ce qu'on savait au lancement précédent.
    old_hashes: dict[str, str] = {} if force else manifest.get(version, {}).get("files", {})
    old_chunks: dict[str, list[dict]] = {}
    if not force:
        for chunk in load_jsonl(out_path):
            old_chunks.setdefault(chunk["source_file"], []).append(chunk)

    new_hashes: dict[str, str] = {}
    all_chunks: list[dict] = []
    report = {"nouveaux": 0, "modifiés": 0, "inchangés": 0}
    for category in config.CATEGORIES:
        for rst_path in sorted((content_dir / category).rglob("*.rst")):
            source_file = "content/" + rst_path.relative_to(content_dir).as_posix()
            file_hash = hashlib.sha256(rst_path.read_bytes()).hexdigest()
            new_hashes[source_file] = file_hash
            if old_hashes.get(source_file) == file_hash:
                all_chunks.extend(old_chunks.get(source_file, []))
                report["inchangés"] += 1
                continue
            report["modifiés" if source_file in old_hashes else "nouveaux"] += 1
            all_chunks.extend(build_chunks(version, rst_path, content_dir))

    report["supprimés"] = len(set(old_hashes) - set(new_hashes))
    report["chunks"] = len(all_chunks)

    config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    write_jsonl(out_path, all_chunks)
    manifest[version] = {"commit": current_commit(repo_dir), "files": new_hashes}
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingestion de la doc Odoo")
    parser.add_argument("--force", action="store_true", help="retraiter tous les fichiers")
    args = parser.parse_args()

    manifest = {}
    if MANIFEST_PATH.exists():
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    for version in config.VERSIONS:
        report = ingest_version(version, manifest, force=args.force)
        details = ", ".join(f"{count} {label}" for label, count in report.items())
        print(f"[{version}] {details}")

    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Chunks écrits dans {config.PROCESSED_DIR}")


if __name__ == "__main__":
    main()
