from odoo_assistant.ingestion.chunker import split_text


def test_short_text_is_one_chunk():
    assert split_text("Short section.", max_chars=100) == ["Short section."]


def test_long_text_is_cut_between_paragraphs():
    paragraphs = [f"Paragraph {n} " + "x" * 50 for n in range(6)]
    chunks = split_text("\n\n".join(paragraphs), max_chars=150)
    assert len(chunks) == 3
    assert all(len(chunk) <= 150 for chunk in chunks)
    # Rien n'est perdu ni coupé au milieu d'un paragraphe.
    assert "\n\n".join(chunks) == "\n\n".join(paragraphs)


def test_code_stays_with_its_introduction():
    text = "A" * 80 + "\n\nHere is an example:\n\n    x = 1\n\n" + "B" * 80
    chunks = split_text(text, max_chars=100)
    assert "Here is an example:\n\n    x = 1" in chunks[1]


def test_oversized_block_is_cut_by_lines():
    block = "\n".join(f"line {n:03d}" for n in range(50))
    chunks = split_text(block, max_chars=100)
    assert all(len(chunk) <= 100 for chunk in chunks)
    assert "\n".join(chunks) == block
