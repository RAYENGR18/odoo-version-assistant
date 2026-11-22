"""Recherche hybride dans la doc Odoo, avec filtre par version.

    python -m odoo_assistant.rag.search "how to define a computed field" --version 19.0

Deux moteurs cherchent en parallèle :
- le moteur sémantique (vecteurs, Chroma) retrouve les passages de même sens ;
- le moteur par mots-clés (BM25) retrouve les passages qui contiennent les mots
  exacts, utile pour les noms techniques comme `ir.cron` ou `@api.depends`.
Leurs deux classements sont ensuite fusionnés (RRF).
"""
import argparse
import re

from langchain_core.documents import Document
from rank_bm25 import BM25Okapi

from odoo_assistant import config
from odoo_assistant.rag.documents import load_documents
from odoo_assistant.rag.index import open_store

MODES = ("hybrid", "dense", "bm25")


def tokenize(text: str) -> list[str]:
    """Découpe un texte en mots pour BM25 ; garde `_` (ex. `_name`, `ir_cron`)."""
    return re.findall(r"[a-z0-9_]+", text.lower())


def rrf_fusion(rankings: list[list[str]], k: int = config.RRF_K) -> list[str]:
    """Fusionne plusieurs classements d'identifiants (Reciprocal Rank Fusion).

    Chaque moteur donne 1 / (k + rang) points à ses résultats. Un passage bien
    classé par les deux moteurs passe devant un passage vu par un seul.
    """
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, chunk_id in enumerate(ranking, start=1):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank)
    return sorted(scores, key=scores.get, reverse=True)


class KeywordIndex:
    """Index BM25 d'une liste de documents (construit en mémoire, très rapide)."""

    def __init__(self, documents: list[Document]):
        self.documents = documents
        self.bm25 = BM25Okapi([tokenize(doc.page_content) for doc in documents])

    def search(self, query: str, n: int) -> list[Document]:
        scores = self.bm25.get_scores(tokenize(query))
        best = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:n]
        return [self.documents[i] for i in best if scores[i] > 0]


class HybridSearcher:
    """Point d'entrée de la recherche : charge les index une fois, puis répond."""

    def __init__(self):
        self.store = open_store()
        by_version = {version: load_documents(version) for version in config.VERSIONS}
        all_documents = [doc for docs in by_version.values() for doc in docs]
        # Un index BM25 par version, plus un pour "toutes versions" (clé None).
        self.keyword = {v: KeywordIndex(docs) for v, docs in by_version.items()}
        self.keyword[None] = KeywordIndex(all_documents)

    def dense_search(self, query: str, version: str | None, n: int) -> list[Document]:
        where = {"version": version} if version else None
        return self.store.similarity_search(query, k=n, filter=where)

    def keyword_search(self, query: str, version: str | None, n: int) -> list[Document]:
        return self.keyword[version].search(query, n)

    def search(self, query: str, version: str | None = None,
               k: int = config.TOP_K, mode: str = "hybrid") -> list[Document]:
        """Renvoie les k meilleurs passages. `version=None` cherche dans toutes."""
        if version is not None and version not in config.VERSIONS:
            raise ValueError(f"Version inconnue : {version} (disponibles : {config.VERSIONS})")
        if mode not in MODES:
            raise ValueError(f"Mode inconnu : {mode} (disponibles : {MODES})")

        if mode == "dense":
            return self.dense_search(query, version, k)
        if mode == "bm25":
            return self.keyword_search(query, version, k)

        dense = self.dense_search(query, version, config.CANDIDATES)
        keyword = self.keyword_search(query, version, config.CANDIDATES)
        found = {doc.metadata["chunk_id"]: doc for doc in dense + keyword}
        ranking = rrf_fusion([
            [doc.metadata["chunk_id"] for doc in dense],
            [doc.metadata["chunk_id"] for doc in keyword],
        ])
        return [found[chunk_id] for chunk_id in ranking[:k]]


def main() -> None:
    parser = argparse.ArgumentParser(description="Recherche dans la doc Odoo")
    parser.add_argument("query", help="la question, en anglais")
    parser.add_argument("--version", choices=config.VERSIONS, help="limiter à une version")
    parser.add_argument("--k", type=int, default=config.TOP_K, help="nombre de résultats")
    parser.add_argument("--mode", choices=MODES, default="hybrid")
    args = parser.parse_args()

    results = HybridSearcher().search(args.query, args.version, args.k, args.mode)
    for rank, doc in enumerate(results, start=1):
        meta = doc.metadata
        extract = " ".join(doc.page_content.split("\n\n", 1)[-1].split())[:200]
        print(f"\n{rank}. [{meta['version']}] {meta['section']}")
        print(f"   {meta['url']}")
        print(f"   {extract}...")


if __name__ == "__main__":
    main()
