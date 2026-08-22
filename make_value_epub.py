"""Generate ValueFeatures.epub from docs/ValueFeatures.md."""
import re
import markdown
from ebooklib import epub

MD_PATH   = "docs/ValueFeatures.md"
EPUB_PATH = "docs/ValueFeatures.epub"

md_text = open(MD_PATH, encoding="utf-8").read()

chapter_re = re.compile(r'^(## .+)$', re.MULTILINE)
parts = chapter_re.split(md_text)

book = epub.EpubBook()
book.set_identifier("smart-meter-value-features-001")
book.set_title("Smart Meter Analytics — Value-Added Features by User Type")
book.set_language("en")
book.add_author("Smart Meter Home Energy")

default_css = epub.EpubItem(
    uid="style",
    file_name="style.css",
    media_type="text/css",
    content=b"""
body { font-family: Georgia, serif; margin: 1.5em; line-height: 1.6; }
h1   { font-size: 1.8em; margin-top: 1.5em; }
h2   { font-size: 1.4em; margin-top: 1.2em; border-bottom: 1px solid #ccc; padding-bottom: 0.2em; }
ul   { margin: 0.8em 0; padding-left: 1.4em; }
li   { margin: 0.4em 0; }
strong { font-weight: bold; }
""",
)
book.add_item(default_css)

chapters = []

intro_html = markdown.markdown(parts[0], extensions=["tables"])
intro_ch = epub.EpubHtml(title="Introduction", file_name="intro.xhtml", lang="en")
intro_ch.content = f"<html><body>{intro_html}</body></html>"
intro_ch.add_item(default_css)
book.add_item(intro_ch)
chapters.append(intro_ch)

section_pairs = list(zip(parts[1::2], parts[2::2]))
for i, (heading_line, body) in enumerate(section_pairs, start=1):
    title = heading_line.lstrip("#").strip()
    safe_title = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')
    file_name = f"ch{i:02d}_{safe_title[:40]}.xhtml"

    combined_md = f"{heading_line}\n{body}"
    html_body = markdown.markdown(combined_md, extensions=["tables"])

    ch = epub.EpubHtml(title=title, file_name=file_name, lang="en")
    ch.content = f"<html><body>{html_body}</body></html>"
    ch.add_item(default_css)
    book.add_item(ch)
    chapters.append(ch)

book.toc = tuple(chapters)
book.add_item(epub.EpubNcx())
book.add_item(epub.EpubNav())
book.spine = ["nav"] + chapters

epub.write_epub(EPUB_PATH, book)
print(f"Written: {EPUB_PATH}")
