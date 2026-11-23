"""Répond à une question à partir de la doc Odoo, en citant ses sources.

    python -m odoo_assistant.rag.answer "comment définir un champ calculé ?" --version 19.0

Étapes :
1. la question est reformulée en anglais, langue de la doc et du moteur de recherche ;
2. la recherche hybride trouve les passages les plus pertinents ;
3. ils sont numérotés [1], [2]... et placés dans le prompt ;
4. le modèle rédige une réponse, dans la langue de la question, en citant ces numéros ;
5. on vérifie que chaque numéro cité correspond bien à un passage fourni.
"""
import argparse
import re
from dataclasses import dataclass, field

from langchain_core.documents import Document
from langchain_core.language_models import BaseChatModel
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from odoo_assistant import config
from odoo_assistant.rag.llm import get_llm
from odoo_assistant.rag.search import HybridSearcher

REWRITE_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "You prepare search queries for the Odoo developer documentation, which is "
     "written in English. Rewrite the user's question as one short English search "
     "query. Keep technical names (models, fields, decorators) unchanged. If the "
     "question is already in English, return it unchanged. Reply with the query only."),
    ("human", "{question}"),
])

ANSWER_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "You are an assistant for Odoo developers. Answer using ONLY the numbered "
     "sources below, which are extracts of the official Odoo documentation.\n\n"
     "Rules:\n"
     "- After each statement, cite the source it comes from with its number in "
     "square brackets, like [1] or [2][3].\n"
     "- Never cite a number that is not in the sources.\n"
     "- If the sources do not contain the answer, say so clearly and do not guess.\n"
     "- Each source states its Odoo version. Say which version your answer applies "
     "to. If sources from different versions disagree, explain the difference.\n"
     "- Copy code examples exactly as they appear in the sources.\n"
     "- Answer in the language of the question.\n\n"
     "Sources:\n{context}"),
    ("human", "{question}"),
])

NO_SOURCE_TEXT = "Aucun passage pertinent trouvé dans la documentation Odoo."


@dataclass
class Citation:
    number: int   # numéro utilisé dans la réponse : [1], [2]...
    version: str
    section: str
    url: str


@dataclass
class Answer:
    question: str
    search_query: str   # la question reformulée en anglais pour la recherche
    text: str
    citations: list[Citation] = field(default_factory=list)       # sources citées
    invalid_citations: list[int] = field(default_factory=list)    # numéros inventés
    sources: list[Document] = field(default_factory=list)         # passages fournis


def format_context(documents: list[Document]) -> str:
    """Présente les passages au modèle, numérotés à partir de 1."""
    blocks = []
    for number, doc in enumerate(documents, start=1):
        blocks.append(f"[{number}] Odoo {doc.metadata['version']}\n{doc.page_content}")
    return "\n\n".join(blocks)


def extract_citations(text: str, n_sources: int) -> tuple[list[int], list[int]]:
    """Relève les numéros cités : (valides, invalides).

    Le code est ignoré, pour ne pas confondre `records[0]` avec une citation.
    """
    prose = re.sub(r"```.*?```|`[^`\n]*`", " ", text, flags=re.DOTALL)
    numbers = sorted({int(n) for n in re.findall(r"\[(\d+)\]", prose)})
    valid = [n for n in numbers if 1 <= n <= n_sources]
    invalid = [n for n in numbers if n not in valid]
    return valid, invalid


class Answerer:
    """Chaîne RAG complète : reformulation, recherche, génération, vérification."""

    def __init__(self, searcher: HybridSearcher | None = None,
                 llm: BaseChatModel | None = None):
        llm = llm or get_llm()
        self.rewrite_chain = REWRITE_PROMPT | llm | StrOutputParser()
        self.answer_chain = ANSWER_PROMPT | llm | StrOutputParser()
        self.searcher = searcher or HybridSearcher()

    def answer(self, question: str, version: str | None = None,
               k: int = config.TOP_K) -> Answer:
        search_query = self.rewrite_chain.invoke({"question": question}).strip()
        documents = self.searcher.search(search_query, version=version, k=k)
        if not documents:
            return Answer(question, search_query, NO_SOURCE_TEXT)

        text = self.answer_chain.invoke(
            {"context": format_context(documents), "question": question}
        )
        valid, invalid = extract_citations(text, len(documents))
        citations = [
            Citation(
                number=n,
                version=documents[n - 1].metadata["version"],
                section=documents[n - 1].metadata["section"],
                url=documents[n - 1].metadata["url"],
            )
            for n in valid
        ]
        return Answer(question, search_query, text, citations, invalid, documents)


def main() -> None:
    parser = argparse.ArgumentParser(description="Question-réponse sur la doc Odoo")
    parser.add_argument("question", help="en français ou en anglais")
    parser.add_argument("--version", choices=config.VERSIONS, help="limiter à une version")
    parser.add_argument("--k", type=int, default=config.TOP_K, help="nombre de passages")
    args = parser.parse_args()

    result = Answerer().answer(args.question, args.version, args.k)
    print(f"\nRecherche : {result.search_query}")
    print(f"\n{result.text}\n")
    if result.citations:
        print("Sources :")
        for c in result.citations:
            print(f"  [{c.number}] Odoo {c.version} | {c.section}\n      {c.url}")
    else:
        print("Attention : la réponse ne cite aucune source.")
    if result.invalid_citations:
        print(f"Attention : numéros cités sans source correspondante : {result.invalid_citations}")


if __name__ == "__main__":
    main()
