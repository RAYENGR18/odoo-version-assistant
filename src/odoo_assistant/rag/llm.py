"""Accès au modèle de langage (LLM) qui rédige les réponses."""
import os

from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel

from odoo_assistant import config

# Variable d'environnement attendue par chaque fournisseur.
API_KEY_NAMES = {
    "anthropic": "ANTHROPIC_API_KEY",
    "groq": "GROQ_API_KEY",
    "openai": "OPENAI_API_KEY",
    "google_genai": "GOOGLE_API_KEY",
}


def get_llm() -> BaseChatModel:
    """Crée le modèle de langage décrit dans la configuration."""
    key_name = API_KEY_NAMES.get(config.LLM_PROVIDER)
    if key_name and not os.getenv(key_name):
        raise SystemExit(
            f"Clé API absente : ajoute la ligne {key_name}=... dans le fichier .env du projet."
        )
    # Pas de réglage de température : la documentation du modèle demande de l'omettre.
    return init_chat_model(
        config.LLM_MODEL,
        model_provider=config.LLM_PROVIDER,
        max_tokens=config.LLM_MAX_TOKENS,
    )
