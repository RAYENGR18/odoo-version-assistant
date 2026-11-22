"""Réglages du projet, regroupés à un seul endroit."""
from pathlib import Path

# --- Dossiers -----------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"              # doc Odoo brute (.rst), une copie par version
PROCESSED_DIR = DATA_DIR / "processed"  # chunks prêts pour l'indexation (.jsonl)
INDEX_DIR = DATA_DIR / "index"          # base vectorielle Chroma
MODELS_DIR = DATA_DIR / "models"        # modèle d'embedding téléchargé

# --- Source des documents -----------------------------------------------------
DOCS_REPO_URL = "https://github.com/odoo/documentation.git"
DOCS_BASE_URL = "https://www.odoo.com/documentation"

# Les deux versions comparées. Chaque version est une branche du dépôt.
VERSIONS = ["18.0", "19.0"]

# Parties de la doc indexées (dossiers sous content/).
# On vise les développeurs : "applications" (doc utilisateur) est volontairement exclu.
CATEGORIES = ["developer", "administration"]

# --- Découpage ----------------------------------------------------------------
MAX_CHUNK_CHARS = 1800  # taille maximale d'un chunk (environ 450 tokens)
MIN_CHUNK_CHARS = 40    # en dessous, la section est vide ou sans intérêt

# --- Recherche ----------------------------------------------------------------
# Petit modèle d'embedding qui tourne sur le processeur, sans GPU ni clé API.
# Il est entraîné sur l'anglais, comme la doc Odoo.
EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
COLLECTION_NAME = "odoo_docs"
TOP_K = 5         # nombre de chunks renvoyés
CANDIDATES = 20   # nombre de candidats demandés à chaque moteur avant la fusion
RRF_K = 60        # constante de la fusion RRF (valeur standard)
