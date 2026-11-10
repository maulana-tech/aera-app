"""Files a person can take away: a workbook (.xlsx) and a document (.pdf).

Standard library only, like the rest of the agent service. An .xlsx is a zip of
XML parts; a PDF is a handful of numbered objects and a table of where each one
starts. Neither needs a dependency to write, so a report downloads the same on
a bare Python as it does on EC2.

    xlsx([Sheet(name, columns, rows), ...])          -> bytes
    Doc(title, ...).h2(...).md(...).table(...).render() -> bytes   (PDF)

The PDF uses the fonts every reader carries (Helvetica, Courier), so nothing is
embedded and the file stays small. Those fonts speak Windows-1252: a character
outside it is spelled out where there is an obvious spelling ("->" for an
arrow) and dropped where there is not (an emoji), never left as a box.
"""
from __future__ import annotations

import io
import json
import math
import re
import unicodedata
import zipfile
import zlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, List, Optional, Sequence, Tuple
from xml.sax.saxutils import escape

# ============================================================== the workbook

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
PDF_MIME = "application/pdf"

# Excel's own limits: a cell holds 32,767 characters, a sheet name 31.
_CELL_MAX = 32_767
_NAME_MAX = 31
# Columns whose numbers are money or quantities read better with separators.
_GROUPED = re.compile(r"idr|cost|value|amount|price|qty|quantity|stock|netamount", re.I)
_BAD_XML = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


@dataclass
class Sheet:
    name: str
    columns: List[str]
    rows: List[List[Any]] = field(default_factory=list)
    # A key/value sheet (two columns, label then value) gets no filter and a
    # wide second column; a table gets a filter on its header.
    pairs: bool = False


def sheet_names(raw: Sequence[str]) -> List[str]:
    """Names Excel accepts: no []:*?/\\, at most 31 characters, all distinct."""
    out: List[str] = []
    for name in raw:
        base = re.sub(r"\s+", " ", re.sub(r"[\[\]:*?/\\]", " ", name)).strip().strip("'") or "Sheet"
        cand, n = base[:_NAME_MAX].rstrip(), 2
        while cand.lower() in (o.lower() for o in out):
            tail = f" ({n})"
            cand, n = base[:_NAME_MAX - len(tail)].rstrip() + tail, n + 1
        out.append(cand)
    return out


def _colname(i: int) -> str:
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def _text(v: Any) -> str:
    if isinstance(v, (dict, list)):
        v = json.dumps(v, ensure_ascii=False, default=str)
    s = _BAD_XML.sub("", str(v))
    return s if len(s) <= _CELL_MAX else s[:_CELL_MAX - 1] + "…"


def _number(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _cell(ref: str, v: Any, style: int) -> str:
    if v is None or v == "":
        return ""
    s = f' s="{style}"' if style else ""
    if isinstance(v, bool):
        return f'<c r="{ref}" t="b"{s}><v>{int(v)}</v></c>'
    if _number(v):
        return f'<c r="{ref}"{s}><v>{v}</v></c>'
    return (f'<c r="{ref}" t="inlineStr"{s}><is><t xml:space="preserve">'
            f'{escape(_text(v))}</t></is></c>')


# Styles, by index into cellXfs below.
_HEAD, _GROUP, _WRAP, _LABEL = 1, 2, 3, 4

_STYLES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><sz val="11"/><name val="Calibri"/></font></fonts>
<fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FFEFEFEF"/><bgColor indexed="64"/></patternFill></fill></fills>
<borders count="2"><border><left/><right/><top/><bottom/><diagonal/></border><border><left/><right/><top/><bottom style="thin"><color rgb="FFBFBFBF"/></bottom><diagonal/></border></borders>
<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
<cellXfs count="5">
<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>
<xf numFmtId="0" fontId="1" fillId="2" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1"/>
<xf numFmtId="3" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>
<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0" applyAlignment="1"><alignment wrapText="1" vertical="top"/></xf>
<xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1" applyAlignment="1"><alignment vertical="top"/></xf>
</cellXfs>
<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
</styleSheet>"""


def _sheet_xml(sh: Sheet) -> str:
    ncol = max(1, len(sh.columns))
    # Width from the longest value in the column, within reason; a column of
    # long prose wraps instead of running off the screen.
    widths, wrap = [], []
    for i in range(ncol):
        vals = [sh.columns[i] if i < len(sh.columns) else ""]
        vals += [r[i] for r in sh.rows[:500] if i < len(r) and r[i] is not None]
        lens = [max((len(x) for x in _text(v).split("\n")), default=0) for v in vals]
        longest = max(lens, default=8)
        wide = longest > 80 or (sh.pairs and i == 1)
        wrap.append(wide)
        widths.append(90 if wide else max(8, min(60, longest + 2)))
    grouped = [bool(_GROUPED.search(c or "")) for c in sh.columns] + [False] * ncol

    rows = []
    head = "".join(_cell(f"{_colname(i)}1", c, _LABEL if sh.pairs else _HEAD)
                   for i, c in enumerate(sh.columns))
    rows.append(f'<row r="1">{head}</row>')
    for r, row in enumerate(sh.rows, start=2):
        cells = []
        for i, v in enumerate(row[:ncol]):
            style = (_LABEL if sh.pairs and i == 0 else _GROUP if _number(v) and grouped[i]
                     else _WRAP if wrap[i] and isinstance(v, str) else 0)
            cells.append(_cell(f"{_colname(i)}{r}", v, style))
        rows.append(f'<row r="{r}">{"".join(cells)}</row>')

    last = f"{_colname(ncol - 1)}{len(sh.rows) + 1}"
    cols = "".join(f'<col min="{i + 1}" max="{i + 1}" width="{w}" customWidth="1"/>'
                   for i, w in enumerate(widths))
    pane = ('<pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/>'
            '<selection pane="bottomLeft" activeCell="A2" sqref="A2"/>') if not sh.pairs else ""
    filt = f'<autoFilter ref="A1:{last}"/>' if not sh.pairs and sh.rows else ""
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            f'<sheetViews><sheetView workbookViewId="0">{pane}</sheetView></sheetViews>'
            '<sheetFormatPr defaultRowHeight="15"/>'
            f'<cols>{cols}</cols><sheetData>{"".join(rows)}</sheetData>{filt}</worksheet>')


def xlsx(sheets: Sequence[Sheet], title: str = "AERA") -> bytes:
    """A workbook with one sheet per table, header frozen and filterable."""
    sheets = list(sheets) or [Sheet("Empty", ["Note"], [["Nothing to export."]])]
    names = sheet_names([s.name for s in sheets])
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    wb_sheets = "".join(f'<sheet name="{escape(n, {chr(34): "&quot;"})}" sheetId="{i + 1}" r:id="rId{i + 1}"/>'
                        for i, n in enumerate(names))
    defined = "".join(
        f'<definedName name="_xlnm._FilterDatabase" localSheetId="{i}" hidden="1">'
        f"'{escape(n.replace(chr(39), chr(39) * 2))}'!$A$1:${_colname(max(1, len(s.columns)) - 1)}${len(s.rows) + 1}"
        "</definedName>"
        for i, (n, s) in enumerate(zip(names, sheets)) if not s.pairs and s.rows)
    workbook = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                f'<sheets>{wb_sheets}</sheets>'
                + (f"<definedNames>{defined}</definedNames>" if defined else "") + "</workbook>")
    wb_rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
               '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
               + "".join(f'<Relationship Id="rId{i + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i + 1}.xml"/>'
                         for i in range(len(sheets)))
               + f'<Relationship Id="rId{len(sheets) + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
               "</Relationships>")
    types = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
             '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
             '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
             '<Default Extension="xml" ContentType="application/xml"/>'
             '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
             '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
             '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
             + "".join(f'<Override PartName="/xl/worksheets/sheet{i + 1}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
                       for i in range(len(sheets)))
             + "</Types>")
    rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>'
            "</Relationships>")
    core = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
            'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" '
            'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
            f"<dc:title>{escape(title)}</dc:title><dc:creator>AERA</dc:creator>"
            f'<dcterms:created xsi:type="dcterms:W3CDTF">{now}</dcterms:created>'
            "</cp:coreProperties>")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", types)
        z.writestr("_rels/.rels", rels)
        z.writestr("docProps/core.xml", core)
        z.writestr("xl/workbook.xml", workbook)
        z.writestr("xl/_rels/workbook.xml.rels", wb_rels)
        z.writestr("xl/styles.xml", _STYLES)
        for i, sh in enumerate(sheets):
            z.writestr(f"xl/worksheets/sheet{i + 1}.xml", _sheet_xml(sh))
    return buf.getvalue()


# ============================================================== the document

# Advance widths (1/1000 em) for character codes 32..126, from the fonts' AFM.
_HELV = [278, 278, 355, 556, 556, 889, 667, 191, 333, 333, 389, 584, 278, 333, 278, 278,
         556, 556, 556, 556, 556, 556, 556, 556, 556, 556, 278, 278, 584, 584, 584, 556,
         1015, 667, 667, 722, 722, 667, 611, 778, 722, 278, 500, 667, 556, 833, 722, 778,
         667, 778, 722, 667, 611, 722, 667, 944, 667, 667, 611, 278, 278, 278, 469, 556,
         333, 556, 556, 500, 556, 556, 278, 556, 556, 222, 222, 500, 222, 833, 556, 556,
         556, 556, 333, 500, 278, 556, 500, 722, 500, 500, 500, 334, 260, 334, 584]
_HELV_B = [278, 333, 474, 556, 556, 889, 722, 238, 333, 333, 389, 584, 278, 333, 278, 278,
           556, 556, 556, 556, 556, 556, 556, 556, 556, 556, 333, 333, 584, 584, 584, 611,
           975, 722, 722, 722, 722, 667, 611, 778, 722, 278, 556, 722, 611, 833, 722, 778,
           667, 778, 722, 667, 611, 722, 667, 944, 667, 667, 611, 333, 278, 333, 584, 556,
           333, 556, 611, 556, 611, 556, 333, 611, 611, 278, 278, 556, 278, 889, 611, 611,
           611, 611, 389, 556, 333, 611, 556, 778, 556, 556, 500, 389, 280, 389, 584]
# The Windows-1252 characters above 126 that a report actually uses.
_HIGH = {0x95: 350, 0x96: 556, 0x97: 1000, 0x85: 1000, 0xB7: 278, 0xD7: 584, 0x91: 222,
         0x92: 222, 0x93: 333, 0x94: 333, 0xA0: 278, 0xB0: 400, 0x80: 556}

# Font keys: R regular, B bold, I oblique, M mono.
_FONTS = {"R": "Helvetica", "B": "Helvetica-Bold", "I": "Helvetica-Oblique", "M": "Courier"}
_SPELL = {"→": "->", "←": "<-", "⇒": "=>", "↔": "<->", "≥": ">=", "≤": "<=", "≈": "~",
          "≠": "!=", "✓": "", "✔": "", "✅": "", "❌": "", "✗": "x", "⚠": "!", " ": " ",
          "​": "", "−": "-", "‑": "-", "→": "->", "●": "•"}


def pdf_text(s: Any) -> str:
    """The string as Windows-1252 can carry it."""
    out = []
    for ch in str(s):
        ch = _SPELL.get(ch, ch)
        if not ch:
            continue
        try:
            ch.encode("cp1252")
            out.append(ch)
            continue
        except UnicodeEncodeError:
            pass
        if unicodedata.category(ch[0]) in ("So", "Sk", "Cs", "Co", "Cn", "Mn", "Cf"):
            continue                                   # an emoji or a mark: drop it
        plain = unicodedata.normalize("NFKD", ch).encode("cp1252", "ignore").decode("cp1252")
        out.append(plain or "?")
    return "".join(out)


def text_width(s: str, font: str, size: float) -> float:
    if font == "M":
        return len(s) * 600 * size / 1000
    table = _HELV_B if font == "B" else _HELV
    w = 0
    for ch in s:
        c = ord(ch) if ord(ch) < 256 else 63
        if 32 <= c <= 126:
            w += table[c - 32]
        else:
            try:
                c = ch.encode("cp1252")[0]
            except UnicodeEncodeError:
                c = 63
            w += _HIGH.get(c, 556)
    return w * size / 1000


def _pdf_str(s: str) -> bytes:
    raw = s.encode("cp1252", "replace")
    out = bytearray(b"(")
    for b in raw:
        if b in (0x28, 0x29, 0x5C):
            out += b"\\" + bytes([b])
        elif b < 32 or b > 126:
            out += b"\\%03o" % b
        else:
            out.append(b)
    return bytes(out + b")")


# ---------------------------------------------------------------- inline runs

Run = Tuple[str, str]          # (text, font key)

_INLINE = re.compile(r"(\*\*[^*]+?\*\*|__[^_]+?__|`[^`]+`|\[[^\]]+\]\([^)]+\)|(?<![\w*])\*[^*\s][^*]*?\*(?!\w))")


def inline(text: str, base: str = "R") -> List[Run]:
    """Markdown emphasis as font changes: **bold**, *italic*, `code`, [link](url)."""
    runs: List[Run] = []
    for part in _INLINE.split(text):
        if not part:
            continue
        if part.startswith(("**", "__")) and len(part) > 4:
            runs.append((part[2:-2], "B"))
        elif part.startswith("`"):
            runs.append((part[1:-1], "M"))
        elif part.startswith("["):
            runs.append((part[1:part.index("]")], base))
        elif part.startswith("*") and part.endswith("*") and len(part) > 2:
            runs.append((part[1:-1], "I" if base == "R" else base))
        else:
            runs.append((part.replace("**", ""), base))
    return [(pdf_text(t), f) for t, f in runs]


def wrap(runs: List[Run], width: float, size: float) -> List[List[Tuple[str, str, float]]]:
    """Runs broken into lines no wider than `width`: each line a list of
    (text, font, x offset). A word longer than a line is cut."""
    lines: List[List[Tuple[str, str, float]]] = [[]]
    x = 0.0
    for text, font in runs:
        for piece in text.split("\n") if "\n" in text else [text]:
            if piece is not text and lines[-1]:
                lines.append([])
                x = 0.0
            for tok in re.findall(r"\S+|\s+", piece):
                w = text_width(tok, font, size)
                if tok.isspace():
                    if x > 0:
                        lines[-1].append((" ", font, x))
                        x += text_width(" ", font, size)
                    continue
                if x + w > width and x > 0:
                    while lines[-1] and lines[-1][-1][0] == " ":
                        lines[-1].pop()
                    lines.append([])
                    x = 0.0
                while w > width and len(tok) > 1:         # one word wider than the line
                    cut = len(tok)
                    while cut > 1 and text_width(tok[:cut], font, size) > width:
                        cut -= 1
                    lines[-1].append((tok[:cut], font, 0.0))
                    lines.append([])
                    tok = tok[cut:]
                    w = text_width(tok, font, size)
                lines[-1].append((tok, font, x))
                x += w
    return [ln for ln in lines] if any(lines) else [[]]


# ---------------------------------------------------------------- the layout

A4 = (595.28, 841.89)
MARGIN = 50.0
INK = "0.1 0.1 0.12"
MUTED = "0.42 0.42 0.46"
RULE = "0.82 0.82 0.85"
SHADE = "0.95 0.95 0.96"


class Doc:
    """A document laid out top to bottom onto A4 pages. Each method adds a
    block and returns the Doc, so a report reads as one chain."""

    def __init__(self, title: str, kicker: str = "AERA", subtitle: str = "", footer: str = ""):
        self.title, self.kicker, self.subtitle = title, kicker, subtitle
        self.footer = footer or title
        self.w, self.h = A4
        self.inner = self.w - 2 * MARGIN
        self.pages: List[List[bytes]] = []
        self.y = 0.0
        self._new_page()
        self._cover()

    # ---- drawing primitives
    def _new_page(self) -> None:
        self.pages.append([])
        self.y = self.h - MARGIN

    def _op(self, s: str) -> None:
        self.pages[-1].append(s.encode("latin-1"))

    def _text(self, x: float, y: float, s: str, font: str = "R", size: float = 10,
              color: str = INK) -> None:
        if not s:
            return
        self.pages[-1].append(
            f"BT {color} rg /F{list(_FONTS).index(font) + 1} {size:.2f} Tf {x:.2f} {y:.2f} Td ".encode()
            + _pdf_str(s) + b" Tj ET")

    def _line(self, x1: float, y1: float, x2: float, y2: float, color: str = RULE, w: float = 0.6) -> None:
        self._op(f"{color} RG {w:.2f} w {x1:.2f} {y1:.2f} m {x2:.2f} {y2:.2f} l S")

    def _rect(self, x: float, y: float, w: float, h: float, color: str = SHADE) -> None:
        self._op(f"{color} rg {x:.2f} {y:.2f} {w:.2f} {h:.2f} re f")

    def _room(self, need: float) -> None:
        if self.y - need < MARGIN + 14:
            self._new_page()

    def _lines(self, lines, x: float, size: float, leading: float, color: str = INK) -> None:
        for ln in lines:
            self._room(leading)
            self.y -= leading
            for text, font, dx in ln:
                self._text(x + dx, self.y + (leading - size) * 0.5, text, font, size, color)

    def _cover(self) -> None:
        self._text(MARGIN, self.y - 8, pdf_text(self.kicker.upper()), "B", 7.5, MUTED)
        self.y -= 16
        self._lines(wrap([(pdf_text(self.title), "B")], self.inner, 18), MARGIN, 18, 23)
        if self.subtitle:
            self.y -= 2
            self._lines(wrap(inline(self.subtitle), self.inner, 10), MARGIN, 10, 14, MUTED)
        self.y -= 10
        self._line(MARGIN, self.y, MARGIN + self.inner, self.y, INK, 1.2)
        self.y -= 14

    # ---- blocks
    def space(self, h: float = 8) -> "Doc":
        self.y -= h
        return self

    def h2(self, text: str) -> "Doc":
        self._room(48)                         # never strand a heading at a page foot
        self.y -= 10
        self._lines(wrap([(pdf_text(text), "B")], self.inner, 12.5), MARGIN, 12.5, 16)
        self.y -= 3
        self._line(MARGIN, self.y, MARGIN + self.inner, self.y)
        self.y -= 8
        return self

    def h3(self, text: str) -> "Doc":
        self._room(34)
        self.y -= 4
        self._lines(wrap(inline(text, "B"), self.inner, 10.5), MARGIN, 10.5, 14)
        self.y -= 3
        return self

    def p(self, text: str, size: float = 9.5, muted: bool = False, indent: float = 0) -> "Doc":
        self._lines(wrap(inline(text), self.inner - indent, size), MARGIN + indent, size,
                    size * 1.42, MUTED if muted else INK)
        self.y -= size * 0.55
        return self

    def mono(self, text: str, size: float = 8) -> "Doc":
        for raw in text.split("\n"):
            self._lines(wrap([(pdf_text(raw), "M")], self.inner - 8, size), MARGIN + 8, size, size * 1.35)
        self.y -= 4
        return self

    def bullets(self, items: Sequence[str], ordered: bool = False, size: float = 9.5) -> "Doc":
        for i, item in enumerate(items, start=1):
            mark = f"{i}." if ordered else "•"
            lines = wrap(inline(item), self.inner - 16, size)
            self._room(size * 1.42)
            self._text(MARGIN + 3, self.y - size * 1.42 + (size * 0.42) * 0.5, mark, "R", size, MUTED)
            self._lines(lines, MARGIN + 16, size, size * 1.42)
            self.y -= 1.5
        self.y -= size * 0.4
        return self

    def note(self, text: str, size: float = 9) -> "Doc":
        lines = wrap(inline(text), self.inner - 16, size)
        lead = size * 1.42
        self._room(lead * min(len(lines), 3) + 8)
        top = self.y
        self.y -= 4
        self._lines(lines, MARGIN + 12, size, lead, MUTED)
        self.y -= 4
        if self.y < top:                        # same page: draw the bar beside it
            self._rect(MARGIN, self.y, 2.2, top - self.y, "0.75 0.75 0.78")
        self.y -= 6
        return self

    def rule(self) -> "Doc":
        self._room(12)
        self.y -= 5
        self._line(MARGIN, self.y, MARGIN + self.inner, self.y)
        self.y -= 7
        return self

    def facts(self, pairs: Sequence[Tuple[str, Any]], cols: int = 3) -> "Doc":
        """Label over value, in a grid: the head of a report."""
        colw = self.inner / cols
        for at in range(0, len(pairs), cols):
            row = pairs[at:at + cols]
            wrapped = [wrap(inline(str(v if v not in (None, "") else "-")), colw - 12, 9.5) for _, v in row]
            h = 12 + max(len(w) for w in wrapped) * 13 + 8
            self._room(h)
            top = self.y
            for i, ((label, _), lines) in enumerate(zip(row, wrapped)):
                x = MARGIN + i * colw
                self._text(x, top - 9, pdf_text(label), "R", 7.5, MUTED)
                self.y = top - 12
                self._lines(lines, x, 9.5, 13)
            self.y = top - h
        self.y -= 2
        return self

    def table(self, columns: Sequence[str], rows: Sequence[Sequence[Any]],
              align: Optional[Sequence[str]] = None, widths: Optional[Sequence[float]] = None,
              size: float = 8, max_lines: int = 14) -> "Doc":
        """A table that wraps its cells, shades its header and repeats it on
        every page it runs onto. `widths` are relative weights; without them
        each column gets room by how much it holds."""
        n = len(columns)
        if not n:
            return self
        align = list(align or ["l"] * n)
        pad = 4.0
        cells = [[pdf_text("" if v is None else v) for v in r] + [""] * (n - len(r)) for r in rows]
        if widths:
            total = sum(widths)
            cw = [self.inner * w / total for w in widths]
        else:
            natural = []
            for i in range(n):
                sample = [columns[i]] + [r[i] for r in cells[:200]]
                natural.append(min(max(text_width(s, "B" if j == 0 else "R", size) for j, s in enumerate(sample))
                                   + 2 * pad, self.inner * 0.6))
            cw = _fit(natural, self.inner, floor=min(42.0, self.inner / n))
        # No header is cut mid-word: a column is at least as wide as its
        # longest header word, the room taken from columns with some to spare.
        need = [max((text_width(w, "B", size) for w in pdf_text(c).split()), default=0) + 2 * pad
                for c in columns]
        short = sum(max(0.0, nd - w) for nd, w in zip(need, cw))
        spare = sum(max(0.0, w - nd) for nd, w in zip(need, cw))
        if short and spare > short:
            cw = [nd if w < nd else w - (w - nd) * short / spare for nd, w in zip(need, cw)]
        lead = size * 1.32

        def draw_head() -> None:
            hl = [wrap([(pdf_text(c), "B")], w - 2 * pad, size) for c, w in zip(columns, cw)]
            h = max(len(x) for x in hl) * lead + 2 * pad
            self._room(h + lead + 2 * pad)
            self._rect(MARGIN, self.y - h, self.inner, h)
            x = MARGIN
            for lines, w, a in zip(hl, cw, align):
                self._cell(lines, x, w, pad, size, lead, a)
                x += w
            self.y -= h
            self._line(MARGIN, self.y, MARGIN + self.inner, self.y, "0.65 0.65 0.68")

        draw_head()
        for r in cells:
            wrapped = []
            for v, w in zip(r, cw):
                lines = wrap([(v, "R")], w - 2 * pad, size)
                if len(lines) > max_lines:
                    lines = lines[:max_lines]
                    lines[-1] = lines[-1] + [("…", "R", max((dx + text_width(t, f, size) for t, f, dx in lines[-1]), default=0))]
                wrapped.append(lines)
            h = max(len(x) for x in wrapped) * lead + 2 * pad
            if self.y - h < MARGIN + 14:
                self._new_page()
                draw_head()
            x = MARGIN
            for lines, w, a in zip(wrapped, cw, align):
                self._cell(lines, x, w, pad, size, lead, a)
                x += w
            self.y -= h
            self._line(MARGIN, self.y, MARGIN + self.inner, self.y)
        self.y -= 10
        return self

    def _cell(self, lines, x: float, w: float, pad: float, size: float, lead: float, a: str) -> None:
        y = self.y - pad
        for ln in lines:
            y -= lead
            span = max((dx + text_width(t, f, size) for t, f, dx in ln), default=0)
            shift = (w - 2 * pad - span) if a == "r" else 0
            for t, f, dx in ln:
                self._text(x + pad + shift + dx, y + (lead - size) * 0.6, t, f, size)

    def md(self, text: str) -> "Doc":
        """Markdown as a model writes it: headings, paragraphs, lists, tables,
        quotes, rules and fenced code. Emphasis becomes bold or italic."""
        lines = (text or "").replace("\r", "").split("\n")
        i, para = 0, []

        def flush() -> None:
            if para:
                self.p(" ".join(s.strip() for s in para))
                para.clear()

        while i < len(lines):
            ln = lines[i]
            s = ln.strip()
            if not s:
                flush()
                i += 1
                continue
            if s.startswith("```"):
                flush()
                block = []
                i += 1
                while i < len(lines) and not lines[i].strip().startswith("```"):
                    block.append(lines[i])
                    i += 1
                self.mono("\n".join(block))
                i += 1
                continue
            m = re.match(r"^(#{1,6})\s+(.*)$", s)
            if m:
                flush()
                (self.h2 if len(m.group(1)) <= 2 else self.h3)(m.group(2).strip("# "))
                i += 1
                continue
            if re.match(r"^(-{3,}|\*{3,}|_{3,})$", s):
                flush()
                self.rule()
                i += 1
                continue
            if s.startswith("|") and i + 1 < len(lines) and re.match(r"^\|?\s*:?-{2,}", lines[i + 1].strip()):
                flush()
                head = _cells(s)
                spec = _cells(lines[i + 1].strip())
                body = []
                i += 2
                while i < len(lines) and lines[i].strip().startswith("|"):
                    body.append(_cells(lines[i].strip()))
                    i += 1
                al = ["r" if c.endswith(":") and not c.startswith(":") else "l" for c in spec]
                self.table([_plain(h) for h in head], [[_plain(c) for c in r] for r in body],
                           align=al + ["l"] * (len(head) - len(al)))
                continue
            if s.startswith(">"):
                flush()
                quote = []
                while i < len(lines) and lines[i].strip().startswith(">"):
                    quote.append(lines[i].strip().lstrip("> ").strip())
                    i += 1
                self.note(" ".join(quote))
                continue
            m = re.match(r"^([-*+]|\d+[.)])\s+(.*)$", s)
            if m:
                flush()
                ordered = m.group(1)[0].isdigit()
                items: List[str] = []
                while i < len(lines):
                    mm = re.match(r"^\s*([-*+]|\d+[.)])\s+(.*)$", lines[i])
                    if mm:
                        items.append(mm.group(2))
                    elif lines[i].startswith(("  ", "\t")) and lines[i].strip() and items:
                        items[-1] += " " + lines[i].strip()
                    else:
                        break
                    i += 1
                self.bullets(items, ordered=ordered)
                continue
            para.append(s)
            i += 1
        flush()
        return self

    # ---- output
    def render(self) -> bytes:
        """The PDF: catalog, page tree, four fonts, then each page and its
        content, with the footer drawn now that the page count is known."""
        total = len(self.pages)
        for n, ops in enumerate(self.pages, start=1):
            self.pages[n - 1] = ops
            foot_y = MARGIN - 22
            ops.append(f"{RULE} RG 0.5 w {MARGIN:.2f} {foot_y + 11:.2f} m {self.w - MARGIN:.2f} {foot_y + 11:.2f} l S".encode())
            left = pdf_text(self.footer)
            while text_width(left, "R", 7.5) > self.inner - 90 and len(left) > 4:
                left = left[:-2]
            ops.append(f"BT {MUTED} rg /F1 7.5 Tf {MARGIN:.2f} {foot_y:.2f} Td ".encode() + _pdf_str(left) + b" Tj ET")
            label = f"Page {n} of {total}"
            ops.append(f"BT {MUTED} rg /F1 7.5 Tf {self.w - MARGIN - text_width(label, 'R', 7.5):.2f} {foot_y:.2f} Td ".encode()
                       + _pdf_str(label) + b" Tj ET")

        objs: List[bytes] = []

        def add(body: bytes) -> int:
            objs.append(body)
            return len(objs)

        catalog = add(b"")                     # filled in once the page tree exists
        tree = add(b"")
        fonts = [add(f"<< /Type /Font /Subtype /Type1 /BaseFont /{name} /Encoding /WinAnsiEncoding >>".encode())
                 for name in _FONTS.values()]
        res = "<< /Font << " + " ".join(f"/F{i + 1} {f} 0 R" for i, f in enumerate(fonts)) + " >> >>"
        kids = []
        for ops in self.pages:
            data = zlib.compress(b"\n".join(ops))
            content = add(b"<< /Length %d /Filter /FlateDecode >>\nstream\n" % len(data) + data + b"\nendstream")
            kids.append(add(f"<< /Type /Page /Parent {tree} 0 R /MediaBox [0 0 {self.w:.2f} {self.h:.2f}] "
                            f"/Resources {res} /Contents {content} 0 R >>".encode()))
        objs[catalog - 1] = f"<< /Type /Catalog /Pages {tree} 0 R >>".encode()
        objs[tree - 1] = (f"<< /Type /Pages /Kids [{' '.join(f'{k} 0 R' for k in kids)}] "
                          f"/Count {len(kids)} >>").encode()
        stamp = datetime.now(timezone.utc).strftime("D:%Y%m%d%H%M%SZ")
        info = add(b"<< /Title " + _pdf_str(pdf_text(self.title)) + b" /Producer (AERA) /Creator (AERA)"
                   + f" /CreationDate ({stamp}) >>".encode())

        out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        offsets = []
        for i, body in enumerate(objs, start=1):
            offsets.append(len(out))
            out += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"
        xref = len(out)
        out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
        out += b"".join(f"{o:010d} 00000 n \n".encode() for o in offsets)
        out += (f"trailer\n<< /Size {len(objs) + 1} /Root {catalog} 0 R /Info {info} 0 R >>\n"
                f"startxref\n{xref}\n%%EOF\n").encode()
        return bytes(out)


def _fit(natural: List[float], avail: float, floor: float) -> List[float]:
    """Column widths that fill `avail`: narrow columns keep what they need, the
    wide ones share what is left in proportion to how much they hold."""
    total = sum(natural)
    if total <= avail:
        return [w + (avail - total) * w / total for w in natural]
    widths = [max(floor, w) for w in natural]
    fixed: set = set()
    while True:
        free = [i for i in range(len(widths)) if i not in fixed]
        room = avail - sum(widths[i] for i in fixed)
        share = room / max(1, len(free))
        small = [i for i in free if natural[i] <= share]
        if not small:
            want = sum(max(floor, natural[i]) for i in free)
            for i in free:
                widths[i] = max(floor, room * max(floor, natural[i]) / want)
            break
        for i in small:
            widths[i] = max(floor, natural[i])
            fixed.add(i)
    scale = avail / sum(widths)
    return [w * scale for w in widths]


def _cells(line: str) -> List[str]:
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip() for c in re.split(r"(?<!\\)\|", s)]


def _plain(s: str) -> str:
    """A table cell without its markdown: emphasis and code marks removed."""
    s = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", s)
    return re.sub(r"\*\*|__|`|(?<!\w)\*(?!\s)|(?<!\s)\*(?!\w)", "", s).replace("\\|", "|").strip()


def md_tables(text: str) -> List[Tuple[str, List[str], List[List[str]]]]:
    """Every GFM table in a markdown text, as (heading above it, columns, rows),
    so a table a model wrote can go to a spreadsheet as a table."""
    out = []
    lines = (text or "").replace("\r", "").split("\n")
    heading = ""
    i = 0
    while i < len(lines):
        s = lines[i].strip()
        m = re.match(r"^#{1,6}\s+(.*)$", s) or re.match(r"^\*\*(.+?)\*\*:?$", s)
        if m:
            heading = _plain(m.group(1))
        if s.startswith("|") and i + 1 < len(lines) and re.match(r"^\|?\s*:?-{2,}", lines[i + 1].strip()):
            head = [_plain(c) for c in _cells(s)]
            body = []
            i += 2
            while i < len(lines) and lines[i].strip().startswith("|"):
                body.append([_plain(c) for c in _cells(lines[i].strip())])
                i += 1
            out.append((heading, head, body))
            continue
        i += 1
    return out


# ================================================================ self-check

def demo() -> None:
    import xml.etree.ElementTree as ET

    # The workbook: every part well-formed XML, names legal and distinct, numbers numeric.
    book = xlsx([
        Sheet("Summary", ["Field", "Value"], [["Title", "Order ord_1"], ["Cost USD", 15]], pairs=True),
        Sheet("get_material_stock: calls/[all]", ["Material", "Plant", "Qty"],
              [["M-4471", "SBY1", 172.8], ["M-4471", "KRW1", 84], ["A & B <c>", None, True]]),
        Sheet("get_material_stock: calls/[all]", ["x"], [[1]]),
    ], title="demo")
    with zipfile.ZipFile(io.BytesIO(book)) as z:
        for name in z.namelist():
            if name.endswith((".xml", ".rels")):
                ET.fromstring(z.read(name))
        wb = ET.fromstring(z.read("xl/workbook.xml"))
        ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
        names = [s.get("name") for s in wb.find("m:sheets", ns)]
        sheet2 = z.read("xl/worksheets/sheet2.xml").decode()
    assert names == ["Summary", "get_material_stock calls all", "get_material_stock calls al (2)"], names
    assert all(len(n) <= 31 for n in names)
    assert '<v>172.8</v>' in sheet2 and "A &amp; B &lt;c&gt;" in sheet2 and 't="b"' in sheet2
    assert 'autoFilter ref="A1:C4"' in sheet2 and 'state="frozen"' in sheet2

    # The document: a valid PDF whose cross-reference table points at every object.
    d = Doc("Market brief: coffee in Vietnam → 5 pages ✅", subtitle="order ord_1 · **delivered**")
    d.facts([("Kind", "port_closure"), ("Started", "2026-10-24 10:18"), ("Status", "done"),
             ("Cost", "Rp 1,435")])
    d.h2("Decision").md("**What happened:** a paid order.\n\n- one\n- two *soft*\n\n| A | B |\n|---|--:|\n| x | 1 |\n\n> caveat\n\n---\n### Next")
    d.table(["#", "Step", "Text"], [[i, "Data check", "word " * 40] for i in range(80)], align=["r", "l", "l"])
    pdf = d.render()
    assert pdf.startswith(b"%PDF-1.4") and pdf.rstrip().endswith(b"%%EOF")
    start = int(pdf.rsplit(b"startxref", 1)[1].split()[0])
    assert pdf[start:start + 4] == b"xref"
    count = int(pdf[start:].split(b"\n")[1].split()[1])
    for i, line in enumerate(pdf[start:].split(b"\n")[3:3 + count - 1], start=1):
        off = int(line.split()[0])
        assert pdf[off:off + len(f"{i} 0 obj")] == f"{i} 0 obj".encode(), f"object {i} is not where the xref says"
    pages = len(d.pages)
    assert pages >= 3, "eighty wrapped rows run over several pages"
    assert pdf_text("a → b ✅ ≥ 1 · é") == "a -> b  >= 1 · é"
    assert md_tables("## Stock\n| M | Qty |\n|---|---|\n| **M-1** | 5 |")[0] == ("Stock", ["M", "Qty"], [["M-1", "5"]])
    print(f"export ok, xlsx {len(book):,} bytes · 3 sheets, names made legal ✓ · "
          f"pdf {len(pdf):,} bytes · {pages} pages, xref sound ✓ · markdown tables lifted ✓")


if __name__ == "__main__":
    demo()
