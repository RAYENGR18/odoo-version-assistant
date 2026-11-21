"""Découpe le texte d'une section en chunks de taille raisonnable.

Une section courte donne un seul chunk. Une section longue est coupée entre
deux paragraphes, jamais au milieu d'une phrase, et un exemple de code reste
collé à la phrase qui l'introduit.
"""


def _blocks(text: str) -> list[str]:
    """Paragraphes du texte ; un bloc indenté (code) est rattaché au précédent."""
    blocks: list[str] = []
    for paragraph in text.split("\n\n"):
        if not paragraph.strip():
            continue
        if blocks and paragraph[0].isspace():
            blocks[-1] += "\n\n" + paragraph
        else:
            blocks.append(paragraph)
    return blocks


def _hard_split(block: str, max_chars: int) -> list[str]:
    """Coupe ligne par ligne un bloc qui dépasse à lui seul la taille maximale."""
    if len(block) <= max_chars:
        return [block]
    pieces, current = [], ""
    for line in block.split("\n"):
        while len(line) > max_chars:  # ligne géante (rare) : coupe brute
            if current:
                pieces.append(current)
                current = ""
            pieces.append(line[:max_chars])
            line = line[max_chars:]
        if current and len(current) + 1 + len(line) > max_chars:
            pieces.append(current)
            current = line
        else:
            current = f"{current}\n{line}" if current else line
    if current.strip():
        pieces.append(current)
    return pieces


def split_text(text: str, max_chars: int) -> list[str]:
    """Renvoie le texte découpé en morceaux d'au plus `max_chars` caractères."""
    if len(text) <= max_chars:
        return [text]
    chunks, current = [], ""
    for block in _blocks(text):
        for piece in _hard_split(block, max_chars):
            if current and len(current) + 2 + len(piece) > max_chars:
                chunks.append(current)
                current = piece
            else:
                current = f"{current}\n\n{piece}" if current else piece
    if current:
        chunks.append(current)
    return chunks
