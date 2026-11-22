"""Construit l'index vectoriel (Chroma) à partir des chunks.

    python -m odoo_assistant.rag.index            # n'indexe que ce qui a changé
    python -m odoo_assistant.rag.index --reset    # repart de zéro

Calculer un vecteur est l'étape lente. On compare donc l'empreinte
(content_hash) de chaque chunk à celle déjà en base : seuls les chunks nouveaux
ou modifiés sont recalculés, et les chunks disparus sont retirés.
"""
import argparse

from langchain_chroma import Chroma

from odoo_assistant import config
from odoo_assistant.rag.documents import load_documents
from odoo_assistant.rag.embeddings import LocalEmbeddings

BATCH_SIZE = 64


def open_store() -> Chroma:
    """Ouvre (ou crée) la base vectorielle enregistrée dans data/index."""
    config.INDEX_DIR.mkdir(parents=True, exist_ok=True)
    return Chroma(
        collection_name=config.COLLECTION_NAME,
        embedding_function=LocalEmbeddings(),
        persist_directory=str(config.INDEX_DIR),
        collection_metadata={"hnsw:space": "cosine"},
    )


def build_index(reset: bool = False) -> dict:
    """Met l'index à jour et renvoie un bilan."""
    store = open_store()
    if reset:
        store.reset_collection()

    documents = [doc for version in config.VERSIONS for doc in load_documents(version)]

    # Ce que l'index contient déjà : identifiant du chunk -> empreinte du texte.
    existing = store.get(include=["metadatas"])
    indexed = {
        chunk_id: metadata["content_hash"]
        for chunk_id, metadata in zip(existing["ids"], existing["metadatas"])
    }

    wanted = {doc.id for doc in documents}
    to_add = [doc for doc in documents if indexed.get(doc.id) != doc.metadata["content_hash"]]
    to_delete = [chunk_id for chunk_id in indexed if chunk_id not in wanted]

    if to_delete:
        store.delete(ids=to_delete)
    for start in range(0, len(to_add), BATCH_SIZE):
        batch = to_add[start:start + BATCH_SIZE]
        # Un identifiant déjà présent est remplacé : pas de doublon.
        store.add_documents(batch, ids=[doc.id for doc in batch])
        print(f"  {min(start + BATCH_SIZE, len(to_add))}/{len(to_add)} chunks indexés", flush=True)

    return {
        "ajoutés ou modifiés": len(to_add),
        "inchangés": len(documents) - len(to_add),
        "supprimés": len(to_delete),
        "total dans l'index": len(documents),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Indexation des chunks dans Chroma")
    parser.add_argument("--reset", action="store_true", help="vider l'index avant")
    args = parser.parse_args()

    print("Indexation (la première fois, compte quelques minutes)...")
    report = build_index(reset=args.reset)
    print(", ".join(f"{count} {label}" for label, count in report.items()))


if __name__ == "__main__":
    main()
