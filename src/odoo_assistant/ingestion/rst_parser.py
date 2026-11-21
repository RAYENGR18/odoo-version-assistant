"""Transforme un fichier .rst de la doc Odoo en sections de texte propre.

La doc Odoo est écrite en reStructuredText (RST). Un titre y est une ligne de
texte soulignée par une ligne de symboles :

    Object-Relational Mapping
    =========================

On découpe chaque fichier à ses titres, puis on nettoie la syntaxe RST
(directives, rôles, liens) pour ne garder que du texte lisible.
"""
import re
from dataclasses import dataclass

# Ligne de soulignement d'un titre : un même symbole répété (====, ----, ~~~~).
ADORNMENT = re.compile(r"^([=\-~^\"'`#*+])\1{2,}\s*$")
# Directive RST : ".. nom:: argument" (parfois dans une cellule de liste : "* - .. nom::")
DIRECTIVE = re.compile(r"^(\s*(?:[*-] )*)\.\. ([\w:-]+)::\s*(.*)$")
# Option d'une directive (":caption: ...") ou champ de page (":orphan:")
OPTION = re.compile(r"^\s*:[\w-]+:( .*)?$")
FOOTNOTE = re.compile(r"^\s*\.\. \[[^\]]+\]\s+(.*)$")

# Directives sans texte utile : on les supprime avec leur contenu.
DROPPED = {
    "image", "figure", "toctree", "raw", "include", "todo", "cards", "card",
    "highlight", "default-domain", "currentmodule", "rst-class", "program",
}
# Encadrés : on garde le contenu, précédé d'une étiquette lisible.
LABELS = {
    "note": "Note", "tip": "Tip", "warning": "Warning", "important": "Important",
    "danger": "Danger", "caution": "Caution", "seealso": "See also",
    "example": "Example", "exercise": "Exercise",
}
CODE_DIRECTIVES = {"code-block", "code", "sourcecode"}


@dataclass
class Section:
    title: str        # titre de la section
    level: int        # 0 = titre de la page, 1 = sous-titre, etc.
    path: list[str]   # fil d'Ariane : ["Titre de page", "Section", "Sous-section"]
    text: str         # contenu nettoyé
    has_code: bool    # la section contient-elle un exemple de code ?


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip())


def _skip_block(lines: list[str], i: int, indent: int) -> int:
    """Saute le contenu d'un bloc : les lignes vides ou plus indentées que lui."""
    while i < len(lines) and (not lines[i].strip() or _indent(lines[i]) > indent):
        i += 1
    return i


def _role_text(match: re.Match) -> str:
    """:class:`~odoo.models.Model` -> Model ; :ref:`texte` -> texte"""
    text = match.group(1).strip()
    if text.startswith("~"):
        return text.split(".")[-1]
    return text.lstrip("!")


def clean_inline(text: str) -> str:
    """Retire la syntaxe RST à l'intérieur des phrases."""
    text = re.sub(r":[\w:-]+:`([^`<]+?)\s*<[^`>]+>`", r"\1", text)  # :doc:`Titre <cible>`
    text = re.sub(r":[\w:-]+:`([^`]+)`", _role_text, text)          # :guilabel:`Save`
    text = re.sub(r"(?<![`\w])`([^`<]+?)\s*<[^`>]+>`_{1,2}", r"\1", text)   # `texte <url>`_
    text = re.sub(r"(?<![`\w])`(?!\s)([^`]+?)(?<!\s)`_{1,2}(?!\w)", r"\1", text)  # `ORM`_
    text = re.sub(r"\\? ?\[#?\w*\]_", "", text)                     # renvoi de note [#x]_
    text = re.sub(r"``([^`]+)``", r"`\1`", text)                    # ``code`` -> `code`
    return text.replace("\\ ", "")


def clean_rst(lines: list[str]) -> str:
    """Nettoie le corps d'une section, ligne par ligne."""
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        indent = _indent(line)
        directive = DIRECTIVE.match(line)

        if directive:
            name, argument = directive.group(2), directive.group(3).strip()
            prefix = directive.group(1)
            indent = len(prefix)  # position du ".." : son contenu est plus indenté
            i += 1
            if name in DROPPED:
                i = _skip_block(lines, i, indent)
                continue
            # Les options de la directive (":caption:", ":emphasize-lines:"...) sont inutiles.
            while i < len(lines) and OPTION.match(lines[i]) and _indent(lines[i]) > indent:
                i += 1
            if name in CODE_DIRECTIVES:
                out.append(prefix + (f"Code ({argument}):" if argument else "Code:"))
            elif name in LABELS:
                out.append(prefix + f"{LABELS[name]}: {argument}".rstrip())
            elif argument:
                out.append(prefix + argument)
            continue

        if stripped == ".." or stripped.startswith(".. "):
            footnote = FOOTNOTE.match(line)
            if footnote:  # note de bas de page : on garde son texte
                out.append(footnote.group(1))
                i += 1
            else:         # étiquette ".. _nom:", substitution ou commentaire
                i = _skip_block(lines, i + 1, indent)
            continue

        if indent == 0 and OPTION.match(line):  # champ de page (":orphan:")
            i += 1
            continue

        # "Voici un exemple::" annonce un bloc de code : on garde un seul ":".
        out.append(re.sub(r"::\s*$", ":", line.rstrip()))
        i += 1

    text = clean_inline("\n".join(out))
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip("\n").rstrip()


def _announces_code(line: str) -> bool:
    """Vrai pour ".. code-block:: python" ou pour une phrase finissant par "::"."""
    directive = DIRECTIVE.match(line)
    if directive:
        return directive.group(2) in CODE_DIRECTIVES
    return line.rstrip().endswith("::")


def _find_headings(lines: list[str]) -> list[tuple[int, int, str, tuple[str, bool]]]:
    """Repère les titres : (ligne de début, ligne de fin, titre, style).

    Le style (symbole, avec ou sans ligne au-dessus) sert à déduire le niveau :
    en RST, le premier style rencontré est le niveau 0, le deuxième le niveau 1...
    """
    headings = []
    i = 0
    while i < len(lines) - 1:
        line, nxt = lines[i], lines[i + 1]
        over = ADORNMENT.match(line)
        # Forme "ligne au-dessus + titre + ligne en dessous"
        if over and i + 2 < len(lines) and nxt.strip() and not ADORNMENT.match(nxt):
            under = ADORNMENT.match(lines[i + 2])
            if under and under.group(1) == over.group(1):
                headings.append((i, i + 3, nxt.strip(), (over.group(1), True)))
                i += 3
                continue
        # Forme "titre + ligne en dessous"
        under = ADORNMENT.match(nxt)
        is_text = line.strip() and not line[0].isspace() and not over
        if under and is_text and not line.startswith(".. "):
            if len(nxt.rstrip()) >= len(line.rstrip()):
                headings.append((i, i + 2, line.strip(), (under.group(1), False)))
                i += 2
                continue
        i += 1
    return headings


def parse_rst(source: str) -> list[Section]:
    """Découpe un document RST en sections, dans l'ordre du fichier."""
    lines = source.splitlines()
    headings = _find_headings(lines)
    styles: list[tuple[str, bool]] = []
    path: list[str] = []
    sections = []
    for k, (_, body_start, raw_title, style) in enumerate(headings):
        if style not in styles:
            styles.append(style)
        level = styles.index(style)
        body_end = headings[k + 1][0] if k + 1 < len(headings) else len(lines)
        body = lines[body_start:body_end]
        title = clean_inline(raw_title)
        path = path[:level] + [title]
        has_code = any(_announces_code(line) for line in body)
        sections.append(Section(title, level, list(path), clean_rst(body), has_code))
    return sections
