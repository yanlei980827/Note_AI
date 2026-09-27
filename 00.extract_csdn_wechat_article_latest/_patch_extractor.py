import io

path = r"article_extractor.py"
with io.open(path, "r", encoding="utf-8", newline="") as f:
    text = f.read()

newline = "\r\n" if "\r\n" in text else "\n"

# 1) Add the tail-normalization helper after _newline_to
helper = (
    "def _normalize_append_tail(raw: str, newline: str) -> str:" + newline
    + '    """Trim trailing blank lines and standalone horizontal rules so the' + newline
    + "    appended ``---`` separator never forms a Setext heading with the" + newline
    + "    existing article's last paragraph.""" + newline
    + "    text = raw.replace(\"\\r\\n\", \"\\n\").replace(\"\\r\", \"\\n\")" + newline
    + "    lines = text.split(\"\\n\")" + newline
    + "    while lines and not lines[-1].strip():" + newline
    + "        lines.pop()" + newline
    + "    while (" + newline
    + "        lines" + newline
    + "        and lines[-1].strip() == \"---\"" + newline
    + "        and (len(lines) == 1 or not lines[-2].strip())" + newline
    + "    ):" + newline
    + "        lines.pop()" + newline
    + "    while lines and not lines[-1].strip():" + newline
    + "        lines.pop()" + newline
    + "    base = \"\\n\".join(lines)" + newline
    + "    if newline == \"\\n\":" + newline
    + "        return base" + newline
    + "    return base.replace(\"\\n\", newline)" + newline
    + newline
)
anchor = "def _atomic_write(path: Path, data: str) -> None:" + newline
assert anchor in text, "anchor for helper not found"
text = text.replace(anchor, helper + anchor, 1)

# 2) Use the helper in write_markdown_file append branch
old_append = (
    "        raw = target.read_text(encoding=\"utf-8\", newline=\"\")" + newline
    + "        newline = \"\\r\\n\" if \"\\r\\n\" in raw else \"\\n\"" + newline
    + "        base = raw.rstrip(\"\\r\\n\")" + newline
)
new_append = (
    "        raw = target.read_text(encoding=\"utf-8\", newline=\"\")" + newline
    + "        newline = \"\\r\\n\" if \"\\r\\n\" in raw else \"\\n\"" + newline
    + "        base = _normalize_append_tail(raw, newline)" + newline
)
assert old_append in text, "append branch not found"
text = text.replace(old_append, new_append, 1)

with io.open(path, "w", encoding="utf-8", newline="") as f:
    f.write(text)

print("patched article_extractor.py:", "_normalize_append_tail" in text)
