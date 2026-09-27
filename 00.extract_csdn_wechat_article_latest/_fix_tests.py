import io

path = r"test_extractor.py"
with io.open(path, "r", encoding="utf-8", newline="") as f:
    text = f.read()

old = (
    "            target.write_text(" + "\n"
    + "                \"最后一段内容。\\n\\n---\\n\\n\""
    + "\\n*（文章末尾附注。）*\\n\", encoding=\"utf-8\")" + "\n"
)
new = (
    "            target.write_text(" + "\n"
    + "                \"最后一段内容。\\n\\n---\\n\\n*（文章末尾附注。）*\\n\","
    + " encoding=\"utf-8\")" + "\n"
)
assert old in text, "mangled string not found"
text = text.replace(old, new, 1)

with io.open(path, "w", encoding="utf-8", newline="") as f:
    f.write(text)
print("fixed")
