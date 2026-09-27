import io

path = r"article_extractor.py"
with io.open(path, "r", encoding="utf-8", newline="") as f:
    text = f.read()

old = (
    '    """Trim trailing blank lines and standalone horizontal rules so the' + "\n"
    + "    appended ``---`` separator never forms a Setext heading with the" + "\n"
    + "    existing article's last paragraph." + "\n"
    + "    text = raw.replace("
)
new = (
    '    """Trim trailing blank lines and standalone horizontal rules so the' + "\n"
    + "    appended ``---`` separator never forms a Setext heading with the" + "\n"
    + "    existing article's last paragraph.\"\"\"" + "\n"
    + "    text = raw.replace("
)
assert old in text, "docstring not found"
text = text.replace(old, new, 1)

with io.open(path, "w", encoding="utf-8", newline="") as f:
    f.write(text)
print("fixed docstring")
