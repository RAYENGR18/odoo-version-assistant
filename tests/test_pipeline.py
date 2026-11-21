import json

from odoo_assistant import config
from odoo_assistant.ingestion import pipeline

PAGE = """\
=====
Views
=====

Views define how records are displayed to the user in the interface.

List view
=========

A list view shows several records at once, one record per line.
"""


def make_docs(tmp_path, monkeypatch):
    """Fausse doc Odoo minimale dans un dossier temporaire."""
    monkeypatch.setattr(config, "RAW_DIR", tmp_path / "raw")
    monkeypatch.setattr(config, "PROCESSED_DIR", tmp_path / "processed")
    monkeypatch.setattr(config, "CATEGORIES", ["developer"])
    monkeypatch.setattr(pipeline, "current_commit", lambda repo_dir: "abc123")
    page = tmp_path / "raw" / "18.0" / "content" / "developer" / "reference" / "views.rst"
    page.parent.mkdir(parents=True)
    page.write_text(PAGE, encoding="utf-8")
    return page


def test_chunks_carry_citation_metadata(tmp_path, monkeypatch):
    page = make_docs(tmp_path, monkeypatch)
    chunks = pipeline.build_chunks("18.0", page, tmp_path / "raw" / "18.0" / "content")
    assert [c["chunk_id"] for c in chunks] == [
        "18.0/developer/reference/views#000", "18.0/developer/reference/views#001",
    ]
    second = chunks[1]
    assert second["version"] == "18.0"
    assert second["category"] == "developer" and second["subcategory"] == "reference"
    assert second["section_path"] == ["Views", "List view"]
    assert second["url"] == (
        "https://www.odoo.com/documentation/18.0/developer/reference/views.html#list-view"
    )


def test_second_run_only_reprocesses_changed_files(tmp_path, monkeypatch):
    page = make_docs(tmp_path, monkeypatch)
    manifest = {}
    first = pipeline.ingest_version("18.0", manifest)
    assert first["nouveaux"] == 1 and first["chunks"] == 2

    second = pipeline.ingest_version("18.0", manifest)
    assert second["inchangés"] == 1 and second["chunks"] == 2

    page.write_text(PAGE + "\nThis sentence was added in a later update of the page.\n",
                    encoding="utf-8")
    third = pipeline.ingest_version("18.0", manifest)
    assert third["modifiés"] == 1
    rows = [json.loads(line) for line in
            (tmp_path / "processed" / "chunks_18.0.jsonl").read_text("utf-8").splitlines()]
    assert "later update" in rows[1]["text"]
