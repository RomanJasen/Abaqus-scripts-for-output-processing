"""
build_pdf.py - builds ../Tutorial_Abaqus_scripts_for_output_processing.pdf from tutorial.html.

Microsoft Edge prints the HTML (headless); PyMuPDF then fills in the page numbers of the
contents, adds page numbers and PDF bookmarks.

    python build_pdf.py          (Python 3 with PyMuPDF:  pip install pymupdf)

Edit tutorial.html (text) or the PNG files in figures/ and run the script again.
"""
import os
import re
import html
import shutil
import tempfile
import subprocess

try:
    import pymupdf as fitz      # PyMuPDF >= 1.24
except ImportError:
    import fitz

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCE = os.path.join(HERE, "tutorial.html")
OUTPUT = os.path.join(os.path.dirname(HERE), "Tutorial_Abaqus_scripts_for_output_processing.pdf")
TITLE = "Abaqus scripts for output processing - Tutorial"
EDGE = (r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe")
FIRST_CONTENT_PAGE = 2          # 0 = cover, 1 = contents


def edge():
    for path in EDGE:
        if os.path.isfile(path):
            return path
    raise SystemExit("Microsoft Edge not found - set EDGE in build_pdf.py")


def print_pdf(html_path, pdf_path):
    profile = tempfile.mkdtemp(prefix="edge_pdf_")
    try:
        subprocess.run([edge(), "--headless", "--disable-gpu", "--no-pdf-header-footer",
                        "--print-to-pdf-no-header", "--user-data-dir=" + profile,
                        "--print-to-pdf=" + pdf_path, "file:///" + html_path.replace("\\", "/")],
                       check=True, timeout=300, capture_output=True)
    finally:
        shutil.rmtree(profile, ignore_errors=True)
    if not os.path.isfile(pdf_path):
        raise SystemExit("Edge did not write %s" % pdf_path)


def plain(fragment):
    """Text of an HTML fragment, without tags and white space, lower case."""
    text = html.unescape(re.sub(r"<[^>]+>", "", fragment))
    return re.sub(r"\s+", "", text).lower()


def headings(source):
    """[(id, level, text shown in the bookmarks, normalised text)] of the chapters and sections."""
    out = []
    for m in re.finditer(r'<h([12])[^>]*\sid="([^"]+)"[^>]*>(.*?)</h\1>', source, re.S):
        level, ident, inner = int(m.group(1)), m.group(2), m.group(3)
        shown = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", inner))).strip()
        out.append((ident, level, shown, plain(inner)))
    return out


def find_pages(pdf_path, heads):
    """Page index of every heading: first line set in a large font whose text is the heading."""
    doc = fitz.open(pdf_path)
    lines = []
    for pno in range(FIRST_CONTENT_PAGE, len(doc)):
        for block in doc[pno].get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                spans = line["spans"]
                if spans:
                    lines.append((pno, max(s["size"] for s in spans), plain("".join(s["text"] for s in spans))))
    pages = {}
    for ident, level, shown, text in heads:
        for pno, size, line_text in lines:
            if size >= 12.0 and line_text == text:
                pages[ident] = pno
                break
    doc.close()
    missing = [h[0] for h in heads if h[0] not in pages]
    if missing:
        raise SystemExit("headings not found in the PDF: %s" % missing)
    return pages


def fill_contents(source, pages):
    def number(m):
        ident = m.group(1)
        return m.group(0).replace('<span class="p"></span>', '<span class="p">%d</span>' % (pages[ident] + 1))
    return re.sub(r'<li[^>]*data-target="([^"]+)".*?</li>', number, source, flags=re.S)


def stamp(pdf_path, heads, pages):
    doc = fitz.open(pdf_path)
    n = len(doc)
    grey = (0.42, 0.47, 0.52)
    for pno in range(1, n):
        page = doc[pno]
        y = page.rect.height - 30
        page.insert_text((48, y), TITLE, fontsize=7.5, fontname="helv", color=grey)
        label = "%d / %d" % (pno + 1, n)
        width = fitz.get_text_length(label, fontname="helv", fontsize=8)
        page.insert_text((page.rect.width - 48 - width, y), label, fontsize=8, fontname="helv", color=grey)
    doc.set_toc([[1, "Contents", 2]] + [[level, shown, pages[ident] + 1] for ident, level, shown, _ in heads])
    doc.set_metadata({"title": TITLE, "subject": "Tutorial of the scripts in the repository "
                      "Abaqus-scripts-for-output-processing", "creator": "tutorial.html + build_pdf.py"})
    tmp = pdf_path + ".tmp"
    doc.save(tmp, garbage=3, deflate=True)
    doc.close()
    os.replace(tmp, pdf_path)
    return n


def main():
    with open(SOURCE, encoding="utf-8") as f:
        source = f.read()
    heads = headings(source)
    work = os.path.join(HERE, "_build_tmp.html")       # same folder: relative image paths stay valid
    first = os.path.join(tempfile.gettempdir(), "tutorial_pass1.pdf")
    try:
        with open(work, "w", encoding="utf-8") as f:
            f.write(source)
        print_pdf(work, first)
        pages = find_pages(first, heads)
        with open(work, "w", encoding="utf-8") as f:
            f.write(fill_contents(source, pages))
        print_pdf(work, OUTPUT)
        if find_pages(OUTPUT, heads) != pages:
            raise SystemExit("page numbers changed between the two passes - run again")
    finally:
        for path in (work, first):
            if os.path.exists(path):
                os.remove(path)
    n = stamp(OUTPUT, heads, pages)
    print("%s: %d pages, %.1f MB" % (OUTPUT, n, os.path.getsize(OUTPUT) / 1e6))


if __name__ == "__main__":
    main()
