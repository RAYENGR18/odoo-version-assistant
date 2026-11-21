from odoo_assistant.ingestion.rst_parser import clean_inline, parse_rst

SAMPLE = """\
:show-content:

.. _tutorials/models:

==================
Chapter 3: Models
==================

Intro with a :doc:`previous chapter <02_newapp>` link.

Object-Relational Mapping
=========================

Models extend :class:`~odoo.models.Model`. See `ORM`_ and ``_name``.

.. image:: models/table.png
   :align: center

.. warning::

   Do not use mutable global variables.

Basic fields
------------

Here is an example::

    name = fields.Char()

.. code-block:: python
   :caption: models.py

   price = fields.Float()

Security
========

Access rights.
"""


def test_sections_follow_the_headings():
    sections = parse_rst(SAMPLE)
    assert [s.title for s in sections] == [
        "Chapter 3: Models", "Object-Relational Mapping", "Basic fields", "Security",
    ]
    assert [s.level for s in sections] == [0, 1, 2, 1]


def test_path_is_a_breadcrumb():
    sections = parse_rst(SAMPLE)
    assert sections[2].path == [
        "Chapter 3: Models", "Object-Relational Mapping", "Basic fields",
    ]
    # "Security" revient au niveau 1 : "Basic fields" sort du fil d'Ariane.
    assert sections[3].path == ["Chapter 3: Models", "Security"]


def test_rst_syntax_is_cleaned():
    orm = parse_rst(SAMPLE)[1]
    assert "Models extend Model. See ORM and `_name`." in orm.text
    assert "Warning:" in orm.text
    assert "Do not use mutable global variables." in orm.text
    assert "image" not in orm.text and ":align:" not in orm.text


def test_code_is_kept_and_flagged():
    intro, orm, fields, security = parse_rst(SAMPLE)
    assert "name = fields.Char()" in fields.text
    assert "Code (python):" in fields.text
    assert "price = fields.Float()" in fields.text
    assert ":caption:" not in fields.text
    assert fields.has_code and not security.has_code


def test_inline_roles_and_links():
    assert clean_inline(":guilabel:`Save`") == "Save"
    assert clean_inline("`Odoo <https://odoo.com>`_") == "Odoo"
    # Des noms de code commençant par "_" ne sont pas des liens RST.
    assert clean_inline("use `_` and `_t`") == "use `_` and `_t`"


def test_file_without_heading_gives_no_section():
    assert parse_rst(".. toctree::\n\n   a\n   b\n") == []
