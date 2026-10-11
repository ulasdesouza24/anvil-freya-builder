"""Text from the bank's documents, for the builder's Read tool (it reads text and PDF, not Word or Excel).

    python lib/doc_text.py <folder>     # writes <file>.txt next to each .docx, .xlsx, .pptx, .html

Standard library only. A file that cannot be read is skipped: the builder still sees the original.
"""
import html, pathlib, re, sys, zipfile


def _xml_text(data, para_tag):
    data = data.decode("utf-8", "replace")
    data = re.sub(rf"</{para_tag}>", "\n", data)
    data = re.sub(r"<w:tab/>|<a:tab/>", "\t", data)
    return html.unescape(re.sub(r"<[^>]+>", "", data))


def docx(path):
    with zipfile.ZipFile(path) as z:
        parts = [n for n in z.namelist() if re.match(r"word/(document|header\d*|footer\d*|footnotes)\.xml$", n)]
        return "\n".join(_xml_text(z.read(n), "w:p") for n in sorted(parts, key=lambda n: n != "word/document.xml"))


def pptx(path):
    with zipfile.ZipFile(path) as z:
        slides = sorted((n for n in z.namelist() if re.match(r"ppt/slides/slide\d+\.xml$", n)), key=lambda n: int(re.findall(r"\d+", n)[-1]))
        return "\n\n".join(f"--- slide {i + 1} ---\n" + _xml_text(z.read(n), "a:p") for i, n in enumerate(slides))


def xlsx(path):
    with zipfile.ZipFile(path) as z:
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            for si in re.findall(r"<si>(.*?)</si>", z.read("xl/sharedStrings.xml").decode("utf-8", "replace"), re.S):
                shared.append(html.unescape("".join(re.findall(r"<t[^>]*>(.*?)</t>", si, re.S))))
        out = []
        for n in sorted(x for x in z.namelist() if re.match(r"xl/worksheets/sheet\d+\.xml$", x)):
            out.append(f"--- {n.split('/')[-1]} ---")
            for row in re.findall(r"<row[^>]*>(.*?)</row>", z.read(n).decode("utf-8", "replace"), re.S):
                cells = []
                for attrs, body in re.findall(r"<c([^>]*)>(.*?)</c>", row, re.S):
                    v = re.search(r"<v>(.*?)</v>", body, re.S)
                    t = re.search(r"<t[^>]*>(.*?)</t>", body, re.S)
                    if 't="s"' in attrs and v:
                        cells.append(shared[int(v.group(1))])
                    elif t:
                        cells.append(html.unescape(t.group(1)))
                    elif v:
                        cells.append(v.group(1))
                out.append("\t".join(cells))
        return "\n".join(out)


def html_file(path):
    t = pathlib.Path(path).read_text("utf-8", "replace")
    t = re.sub(r"(?is)<(script|style).*?</\1>", "", t)
    t = re.sub(r"(?i)<br\s*/?>|</p>|</tr>|</li>|</h\d>", "\n", t)
    return html.unescape(re.sub(r"<[^>]+>", " ", t))


READERS = {".docx": docx, ".xlsx": xlsx, ".pptx": pptx, ".html": html_file, ".htm": html_file}


def convert_tree(folder):
    done = []
    for p in sorted(pathlib.Path(folder).rglob("*")):
        f = READERS.get(p.suffix.lower())
        if not f or not p.is_file() or "__MACOSX" in p.parts:
            continue
        try:
            text = f(p)
        except Exception:
            continue
        out = p.with_name(p.name + ".txt")
        out.write_text(text, "utf-8")
        done.append(str(out))
    return done


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    print("\n".join(convert_tree(sys.argv[1])))
