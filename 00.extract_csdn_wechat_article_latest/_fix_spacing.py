import io

path = r"article_extractor.py"
with io.open(path, "r", encoding="utf-8", newline="") as f:
    text = f.read()

old = (
    "    return base.replace(\"\\n\", newline)" + "\n"
    + "def _atomic_write(path: Path, data: str) -> None:" + "\n"
)
new = (
    "    return base.replace(\"\\n\", newline)" + "\n"
    + "\n"
    + "\n"
    + "def _atomic_write(path: Path, data: str) -> None:" + "\n"
)
assert old in text, "spacing anchor not found"
text = text.replace(old, new, 1)

with io.open(path, "w", encoding="utf-8", newline="") as f:
    f.write(text)
print("spacing fixed")
