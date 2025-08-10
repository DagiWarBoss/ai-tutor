# ocr_fallback.py
# Robust OCR fallback: render PDF pages -> Tesseract hOCR -> lines -> numbered parents -> CSV-guided children -> per-parent segmentation

import re
from typing import List, Dict, Tuple, Optional
import fitz  # PyMuPDF
from PIL import Image
import pytesseract
from bs4 import BeautifulSoup

try:
    from rapidfuzz import fuzz
    HAVE_FUZZ = True
except Exception:
    HAVE_FUZZ = False

HEADING_NUMBER_RE = re.compile(r"^\s*(\d+(?:\.\d+){1,5})\b")
SPACE_RE = re.compile(r"\s+")

def set_tesseract_path(binary_path: Optional[str] = None):
    if binary_path:
        pytesseract.pytesseract.tesseract_cmd = binary_path

def _norm_spaces(s: str) -> str:
    return SPACE_RE.sub(" ", (s or "").strip())

def _norm_text(s: str) -> str:
    # normalize punctuation and case for matching
    s = _norm_spaces(s)
    s = s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    s = s.replace("–", "-").replace("—", "-").replace("·", ".")
    s = s.lower()
    return s

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
        raw = " ".join(words)
        text = _norm_spaces(raw)
        if not text:
            continue
        lines.append({"page": page_index, "x": x0, "y": y0, "x1": x1, "y1": y1, "text": text})
    lines.sort(key=lambda r: (r["page"], r["y"], r["x"]))
    return lines

def detect_numbered_parents(lines: List[Dict], left_margin_px: int = 260) -> List[Dict]:
    anchors = []
    for ln in lines:
        text = ln["text"]
        m = HEADING_NUMBER_RE.match(text)
        if not m:
            continue
        # treat only left-margin lines as headings to cut false positives
        if ln["x"] > left_margin_px:
            continue
        number = m.group(1).strip(".")
        anchors.append({"type": "numbered", "number": number, "page": ln["page"], "y": ln["y"], "text": text})
    anchors.sort(key=lambda a: (a["page"], a["y"]))
    # de-dupe by (num,page,y//2) to avoid duplicates from overlapping OCR boxes
    uniq, seen = [], set()
    for a in anchors:
        key = (a["number"], a["page"], int(a["y"] / 2))
        if key not in seen:
            seen.add(key)
            uniq.append(a)
    return uniq

def best_child_matches_in_window(
    window_lines: List[Dict],
    csv_children: List[Tuple[str, str]],
    left_margin_px: int = 300,
    fuzzy_threshold: int = 85
) -> List[Dict]:
    # Build candidates from left-aligned lines
    cands = []
    for ln in window_lines:
        if ln["x"] <= left_margin_px:
            cands.append(ln)

    results = []
    for child_num, child_title in csv_children:
        if not child_num or not child_title:
            continue
        target = _norm_text(child_title)
        best = None
        best_score = -1
        for ln in cands:
            cand_text_norm = _norm_text(ln["text"])
            if HAVE_FUZZ:
                score = fuzz.partial_ratio(target, cand_text_norm)
            else:
                # fallback: crude substring/containment scoring
                score = 100 if target in cand_text_norm else (90 if cand_text_norm.startswith(target[: max(5, len(target)//2)]) else 0)
            if score > best_score:
                best_score = score
                best = ln
        if best and best_score >= fuzzy_threshold:
            results.append({"type": "csv_child", "number": child_num.strip("."), "page": best["page"], "y": best["y"], "text": best["text"], "score": best_score})
    results.sort(key=lambda a: (a["page"], a["y"]))
    # de-dupe by (child_num,page,y//2)
    uniq, seen = [], set()
    for a in results:
        key = (a["number"], a["page"], int(a["y"] / 2))
        if key not in seen:
            seen.add(key)
            uniq.append(a)
    return uniq

def segment_window(lines_sorted: List[Dict], start_anchor: Dict, end_anchor: Optional[Dict], inner_anchors: List[Dict]) -> Dict[str, str]:
    # Build segments inside [start,end) for the anchors: start_anchor children or start itself
    # Compose the anchor list: inner children in order
    anchors = inner_anchors[:]
    anchors.sort(key=lambda a: (a["page"], a["y"]))
    # If no inner anchors, just return the parent segment
    segments = {}
    def in_range(ln, s, e):
        after = (ln["page"] > s["page"]) or (ln["page"] == s["page"] and ln["y"] > s["y"])
        before = True
        if e:
            before = (ln["page"] < e["page"]) or (ln["page"] == e["page"] and ln["y"] < e["y"])
        return after and before

    # If there are children, segment for each child
    if anchors:
        for i, a in enumerate(anchors):
            start = a
            end = anchors[i + 1] if i + 1 < len(anchors) else end_anchor
            chunks = []
            for ln in lines_sorted:
                if not in_range(ln, start, end):
                    continue
                # Skip heading lines (child and the next anchor lines)
                if (ln["page"] == start["page"] and abs(ln["y"] - start["y"]) < 3):
                    continue
                if end and (ln["page"] == end["page"] and abs(ln["y"] - end["y"]) < 3):
                    continue
                chunks.append(ln["text"])
            merged = _norm_spaces("\n".join(chunks))
            if merged:
                segments[a["number"]] = merged
    else:
        # No children: produce just the parent segment
        chunks = []
        for ln in lines_sorted:
            if not in_range(ln, start_anchor, end_anchor):
                continue
            if (ln["page"] == start_anchor["page"] and abs(ln["y"] - start_anchor["y"]) < 3):
                continue
            if end_anchor and (ln["page"] == end_anchor["page"] and abs(ln["y"] - end_anchor["y"]) < 3):
                continue
            chunks.append(ln["text"])
        merged = _norm_spaces("\n".join(chunks))
        if merged:
            segments[start_anchor["number"]] = merged
    return segments

def ocr_extract_topics(
    pdf_path: str,
    csv_children_map: Optional[Dict[str, List[Tuple[str, str]]]] = None,
    tesseract_bin: Optional[str] = None,
    lang: str = "eng",
    zoom: float = 4.0,
    fuzzy_threshold: int = 85
) -> Dict[str, str]:
    set_tesseract_path(tesseract_bin)
    images = render_pages_with_pymupdf(pdf_path, zoom=zoom)

    all_lines: List[Dict] = []
    for page_index, img in images:
        try:
            hocr = ocr_page_hocr(img, lang=lang)
            lines = hocr_to_lines(hocr, page_index)
            all_lines.extend(lines)
        except Exception:
            # If a single page fails OCR, keep going.
            continue

    if not all_lines:
        return {}

    parents = detect_numbered_parents(all_lines)
    if not parents:
        return {}

    # Sort once for range scans
    lines_sorted = sorted(all_lines, key=lambda r: (r["page"], r["y"], r["x"]))

    segments: Dict[str, str] = {}

    for i, parent in enumerate(parents):
        end_parent = parents[i + 1] if i + 1 < len(parents) else None

        # Build window lines for this parent range
        window_lines = []
        for ln in lines_sorted:
            after = (ln["page"] > parent["page"]) or (ln["page"] == parent["page"] and ln["y"] > parent["y"])
            before = True
            if end_parent:
                before = (ln["page"] < end_parent["page"]) or (ln["page"] == end_parent["page"] and ln["y"] < end_parent["y"])
            if after and before:
                window_lines.append(ln)

        # Children detection for this parent only
        child_specs = csv_children_map.get(parent["number"], []) if csv_children_map else []
        child_anchors = []
        if child_specs:
            child_anchors = best_child_matches_in_window(
                window_lines,
                csv_children=child_specs,
                left_margin_px=300,
                fuzzy_threshold=fuzzy_threshold
            )

        # Segment inside this window
        segs = segment_window(lines_sorted, parent, end_parent, child_anchors)
        segments.update(segs)

    return segments
