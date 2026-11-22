"""Charge les chunks produits par l'ingestion sous forme de Documents LangChain."""
import json

from langchain_core.documents import Document

from odoo_assistant import config

# Métadonnées gardées dans l'index (Chroma n'accepte que des valeurs simples).
METADATA_KEYS = [
    "chunk_id", "version", "doc_id", "category", "subcategory",
    "page_title", "section_title", "url", "has_code", "content_hash",
]


def to_document(chunk: dict) -> Document:
    """Un chunk devient un Document : un texte + ses métadonnées.

    On place le fil d'Ariane ("Page > Section") au début du texte : le moteur de
    recherche sait ainsi de quoi parle le passage, même s'il est court.
    """
    breadcrumb = " > ".join(chunk["section_path"])
    metadata = {key: chunk[key] for key in METADATA_KEYS}
    metadata["section"] = breadcrumb
    return Document(
        id=chunk["chunk_id"],
        page_content=f"{breadcrumb}\n\n{chunk['text']}",
        metadata=metadata,
    )


def load_documents(version: str) -> list[Document]:
    """Tous les chunks d'une version."""
    path = config.PROCESSED_DIR / f"chunks_{version}.jsonl"
    if not path.exists():
        raise SystemExit(
            f"{path.name} introuvable. Lance d'abord : "
            "python -m odoo_assistant.ingestion.pipeline"
        )
    with path.open(encoding="utf-8") as f:
        return [to_document(json.loads(line)) for line in f if line.strip()]
