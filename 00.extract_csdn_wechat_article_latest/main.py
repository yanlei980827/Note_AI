"""Entry point for the article to Markdown desktop app."""

import tkinter as tk

from app_gui import ArticleMarkdownApp


def main() -> None:
    root = tk.Tk()
    ArticleMarkdownApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
