from langchain_core.documents import Document

from odoo_assistant.rag.documents import to_document
from odoo_assistant.rag.search import KeywordIndex, rrf_fusion, tokenize


def test_tokenize_keeps_technical_names():
    assert tokenize("Set `_name` on ir.cron!") == ["set", "_name", "on", "ir", "cron"]


def test_rrf_rewards_agreement_between_engines():
    dense = ["a", "b", "c"]
    keyword = ["c", "a", "d"]
    # "a" est 1er et 2e, "c" est 3e et 1er : ils passent devant "b" et "d".
    assert rrf_fusion([dense, keyword])[:2] == ["a", "c"]
    assert set(rrf_fusion([dense, keyword])) == {"a", "b", "c", "d"}


def test_keyword_index_finds_exact_terms():
    documents = [
        Document(page_content="Scheduled actions are defined with ir.cron records."),
        Document(page_content="Computed fields use the api.depends decorator."),
        Document(page_content="Access rights are stored in ir.model.access."),
    ]
    index = KeywordIndex(documents)
    assert index.search("cron scheduled", n=1)[0] is documents[0]
    assert index.search("zzz unknown word", n=3) == []


def test_document_text_starts_with_breadcrumb():
    chunk = {
        "chunk_id": "18.0/developer/reference/views#001", "version": "18.0",
        "doc_id": "developer/reference/views", "category": "developer",
        "subcategory": "reference", "page_title": "Views", "section_title": "List view",
        "section_path": ["Views", "List view"], "url": "https://example.org/views.html",
        "source_file": "content/developer/reference/views.rst", "has_code": False,
        "n_chars": 30, "content_hash": "abc", "text": "A list view shows records.",
    }
    doc = to_document(chunk)
    assert doc.page_content == "Views > List view\n\nA list view shows records."
    assert doc.id == "18.0/developer/reference/views#001"
    assert doc.metadata["version"] == "18.0" and doc.metadata["section"] == "Views > List view"
