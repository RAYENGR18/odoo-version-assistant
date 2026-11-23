from langchain_core.documents import Document
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from odoo_assistant.rag.answer import Answerer, extract_citations, format_context


def make_doc(version: str, section: str, text: str) -> Document:
    return Document(
        page_content=f"{section}\n\n{text}",
        metadata={"version": version, "section": section,
                  "url": f"https://example.org/{version}/{section.lower()}.html"},
    )


DOCS = [
    make_doc("19.0", "Computed fields", "Use the compute attribute."),
    make_doc("19.0", "Onchange", "Use the api.onchange decorator."),
]


class FakeSearcher:
    """Remplace la recherche : renvoie toujours les mêmes passages."""

    def __init__(self, documents):
        self.documents = documents
        self.last_query = None

    def search(self, query, version=None, k=5):
        self.last_query = query
        return self.documents[:k]


def fake_llm(*responses: str) -> FakeListChatModel:
    """Faux modèle : rend ces réponses dans l'ordre (reformulation, puis réponse)."""
    return FakeListChatModel(responses=list(responses))


def test_context_numbers_sources_and_shows_version():
    context = format_context(DOCS)
    assert context.startswith("[1] Odoo 19.0\nComputed fields")
    assert "[2] Odoo 19.0\nOnchange" in context


def test_citations_are_split_into_valid_and_invalid():
    assert extract_citations("Use compute [1]. See also [2][7].", n_sources=2) == ([1, 2], [7])


def test_brackets_inside_code_are_not_citations():
    text = "Take the first record with `records[0]` [1].\n```python\nx = values[3]\n```"
    assert extract_citations(text, n_sources=2) == ([1], [])


def test_search_uses_the_english_rewrite_of_the_question():
    searcher = FakeSearcher(DOCS)
    llm = fake_llm("define a computed field", "Utilisez l'attribut compute [1].")
    result = Answerer(searcher=searcher, llm=llm).answer("Comment définir un champ calculé ?")
    assert searcher.last_query == "define a computed field"
    assert result.search_query == "define a computed field"
    assert result.question == "Comment définir un champ calculé ?"
    assert result.text == "Utilisez l'attribut compute [1]."


def test_answer_links_each_citation_to_its_source():
    llm = fake_llm("computed field", "Set the compute attribute [1]. Unrelated claim [4].")
    result = Answerer(searcher=FakeSearcher(DOCS), llm=llm).answer("How?", version="19.0")
    assert [c.number for c in result.citations] == [1]
    assert result.citations[0].url == "https://example.org/19.0/computed fields.html"
    assert result.invalid_citations == [4]
    assert len(result.sources) == 2


def test_no_passage_means_no_answer_is_generated():
    llm = fake_llm("some query", "should not be used")
    result = Answerer(searcher=FakeSearcher([]), llm=llm).answer("How?")
    assert result.citations == [] and "Aucun passage" in result.text
