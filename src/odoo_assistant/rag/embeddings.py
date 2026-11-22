"""Modèle d'embedding : transforme un texte en vecteur de nombres.

Deux textes de sens proche donnent deux vecteurs proches : c'est ce qui permet
de retrouver un passage même si la question n'emploie pas les mêmes mots.
"""
from fastembed import TextEmbedding
from langchain_core.embeddings import Embeddings

from odoo_assistant import config


class LocalEmbeddings(Embeddings):
    """Branche le modèle local (fastembed) sur l'interface Embeddings de LangChain."""

    def __init__(self, model_name: str = config.EMBEDDING_MODEL):
        config.MODELS_DIR.mkdir(parents=True, exist_ok=True)
        # Le modèle (environ 70 Mo) est téléchargé au premier lancement.
        self.model = TextEmbedding(model_name, cache_dir=str(config.MODELS_DIR))

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [vector.tolist() for vector in self.model.embed(texts)]

    def embed_query(self, text: str) -> list[float]:
        return next(iter(self.model.query_embed(text))).tolist()
