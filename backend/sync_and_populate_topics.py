# ocr_fallback.py
# Drop-in OCR helpers: render PDF pages -> Tesseract hOCR -> lines -> heading anchors -> segments
# Requires: pytesseract, pillow, pymupdf, beautifulsoup4, lxml

import re
from typing import List, Dict, Tuple, Optional
import fitz  # PyMuPDF
from PIL import Image
import pytesseract
from bs4 import BeautifulSoup

HEADING_NUMBER_RE = re.compile(r"^\s*(\d+(?:\.\d+){1,5})\b")
SPACE_RE = re.compile(r"\s+")


def set_tesseract_path(binary_path: Optional[str] = None):
    if binary_path:
        pytesseract.pytesseract.tesseract_cmd = binary_path


def _normalize(s: str) -> str:
    return SPACE_RE.sub(" ", (s or "").strip())


def render_pages_with_pymupdf(pdf_path: str, zoom: float = 4.0) -> List[Tuple[int, Image.Image]]:
    doc = fitz.open(pdf_path)
    images = []
    for i in range(len(doc)):
        page = doc.load_page(i)
        mat = fitz.Matrix(zoom, zoom)  # 72dpi * zoom => 288dpi at zoom=4.0
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        images.append((i, img))
    doc.close()
    return images


def ocr_page_hocr(pil_image: Image.Image, lang: str = "eng") -> str:
    out = pytesseract.image_to_pdf_or_hocr(pil_image, extension="hocr", lang=lang)
    return out.decode("utf-8", errors="ignore") if isinstance(out, (bytes, bytearray)) else str(out)


def hocr_to_lines(hocr_html: str, page_index: int) -> List[Dict]:
    soup = BeautifulSoup(hocr_html, "lxml")
    lines = []
    for line in soup.find_all(class_="ocr_line"):
        title = line.get("title", "")
        m = re.search(r"bbox (\d+) (\d+) (\d+) (\d+)", title)
        if not m:
            continue
        x0, y0, x1, y1 = map(int, m.groups())
        words = [w.get_text(strip=True) for w in line.find_all(class_="ocrx_word")]
        text = _normalize(" ".join(words))
        if not text:
            continue
        lines.append({"page": page_index, "x": x0, "y": y0, "x1": x1, "y1": y1, "text": text})
    lines.sort(key=lambda r: (r["page"], r["y"], r["x"]))
    return lines


def detect_headings_ocr(
    lines: List[Dict],
    csv_children: Optional[List[Tuple[str, str]]] = None,
    left_margin_px: int = 250
) -> List[Dict]:
    anchors = []
    # Numbered headings
    for ln in lines:
        text = ln["text"]
        m = HEADING_NUMBER_RE.match(text)
        if m:
            number = m.group(1).strip(".")
            anchors.append({"type": "numbered", "number": number, "page": ln["page"], "y": ln["y"], "text": text})
    # CSV-guided child subheads (match title substrings)
    if csv_children:
        norm = lambda s: _normalize(s).lower()
        child_norms = [(num, norm(title or "")) for num, title in csv_children if num]
        for t_num, t_title_norm in child_norms:
            if not t_title_norm:
                continue
            for ln in lines:
                if ln["x"] <= left_margin_px:
                    lt = norm(ln["text"])
                    if t_title_norm and t_title_norm in lt:
                        anchors.append({"type": "csv_child", "number": t_num.strip("."), "page": ln["page"], "y": ln["y"], "text": ln["text"]})
    # Sort and dedupe
    anchors.sort(key=lambda a: (a["page"], a["y"]))
    uniq, seen = [], set()
    for a in anchors:
        key = (a["number"], a["page"], int(a["y"] / 2))
        if key not in seen:
            seen.add(key)
            uniq.append(a)
    return uniq


def segment_by_anchors_ocr(lines: List[Dict], anchors: List[Dict]) -> Dict[str, str]:
    if not anchors:
        return {}
    segments: Dict[str, str] = {}
    lines_sorted = sorted(lines, key=lambda r: (r["page"], r["y"], r["x"]))
    for i, a in enumerate(anchors):
        start = a
        end = anchors[i + 1] if i + 1 < len(anchors) else None
        chunks = []
        for ln in lines_sorted:
            after = (ln["page"] > start["page"]) or (ln["page"] == start["page"] and ln["y"] > start["y"])
            before = True
            if end:
                before = (ln["page"] < end["page"]) or (ln["page"] == end["page"] and ln["y"] < end["y"])
            if after and before:
                # skip any anchor line itself
                if ln["page"] == start["page"] and abs(ln["y"] - start["y"]) < 3 and ln["text"] == start["text"]:
                    continue
                if end and ln["page"] == end["page"] and abs(ln["y"] - end["y"]) < 3 and ln["text"] == end["text"]:
                    continue
                chunks.append(ln["text"])
        merged = _normalize("\n".join(chunks))
        segments[a["number"]] = merged
    return segments


def ocr_extract_topics(
    pdf_path: str,
    csv_children_map: Optional[Dict[str, List[Tuple[str, str]]]] = None,
    tesseract_bin: Optional[str] = None,
    lang: str = "eng",
    zoom: float = 4.0,
) -> Dict[str, str]:
    set_tesseract_path(tesseract_bin)
    images = render_pages_with_pymupdf(pdf_path, zoom=zoom)
    all_lines: List[Dict] = []
    for page_index, img in images:
        hocr = ocr_page_hocr(img, lang=lang)
        lines = hocr_to_lines(hocr, page_index)
        all_lines.extend(lines)

    # Global anchors (numbered)
    global_anchors = detect_headings_ocr(all_lines, csv_children=None)

    # If CSV map is provided, enrich anchors with children titles inside each parent's window
    if csv_children_map:
        enriched: List[Dict] = []
        # Build quick index of anchors by page/y
        for idx, anc in enumerate(global_anchors):
            parent_num = anc["number"]
            enriched.append(anc)
            # find end window
            end_anc = global_anchors[idx + 1] if idx + 1 < len(global_anchors) else None
            children = csv_children_map.get(parent_num, [])
            if not children:
                continue
            # collect lines inside window
            window_lines = []
            for ln in all_lines:
                after = (ln["page"] > anc["page"]) or (ln["page"] == anc["page"] and ln["y"] > anc["y"])
                before = True
                if end_anc:
                    before = (ln["page"] < end_anc["page"]) or (ln["page"] == end_anc["page"] and ln["y"] < end_anc["y"])
                if after and before:
                    window_lines.append(ln)
            # detect child anchors in window
            child_anchors = detect_headings_ocr(window_lines, csv_children=children)
            enriched.extend(child_anchors)
        # sort & dedupe again
        enriched.sort(key=lambda a: (a["page"], a["y"]))
        final_anchors, seen = [], set()
        for a in enriched:
            key = (a["number"], a["page"], int(a["y"] / 2))
            if key not in seen:
                seen.add(key)
                final_anchors.append(a)
        anchors = final_anchors
    else:
        anchors = global_anchors

    segments = segment_by_anchors_ocr(all_lines, anchors)
    return segments
