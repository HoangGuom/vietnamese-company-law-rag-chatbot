"""Ingest detailed TT68 form DOCX files into legal_chunks.json.

The official PDF attached to 68/2025/TT-BTC is image-based, so text extraction is
not reliable enough for legal RAG. This script uses editable DOCX form files
downloaded from dangkykinhdoanh.gov.vn and creates one or more exact text chunks
per available form.
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
import zipfile
from collections import defaultdict
from copy import deepcopy
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse
from xml.etree import ElementTree as ET


CHUNKS_PATH = Path("legal_chunks.json")
DOC_LINKS_PATH = Path("downloads/dkkd_doc_links.json")
DOCX_DIR = Path("downloads/tt68_forms_docx")
MAX_CHUNK_CHARS = 6000

TT68_BASE = {
    "ten_van_ban": "Thông tư 68/2025/TT-BTC biểu mẫu đăng ký doanh nghiệp, đăng ký hộ kinh doanh",
    "so_hieu": "68/2025/TT-BTC",
    "loai": "thong_tu",
    "hieu_luc": "01/07/2025",
    "tinh_trang_hieu_luc": "con_hieu_luc",
    "ngay_het_hieu_luc": None,
    "nguon_hieu_luc": "https://vanban.chinhphu.vn/?docid=214411&pageid=27160",
    "su_dung_cho_rag": True,
}


def configure_console_encoding() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8")


def strip_accents(text: str) -> str:
    return "".join(
        char
        for char in unicodedata.normalize("NFD", text)
        if unicodedata.category(char) != "Mn"
    ).lower()


def read_docx_text(path: Path) -> str:
    namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    with zipfile.ZipFile(path) as archive:
        xml = archive.read("word/document.xml")
    root = ET.fromstring(xml)

    paragraphs: list[str] = []
    for paragraph in root.findall(".//w:p", namespace):
        parts: list[str] = []
        for node in paragraph.iter():
            tag = node.tag.rsplit("}", 1)[-1]
            if tag == "t" and node.text:
                parts.append(node.text)
            elif tag == "tab":
                parts.append("\t")
            elif tag == "br":
                parts.append("\n")
        text = "".join(parts).strip()
        if text:
            paragraphs.append(re.sub(r"[ \t]+", " ", text))
    return "\n".join(paragraphs)


def infer_form_number(file_name: str, text: str) -> int | None:
    normalized_name = strip_accents(file_name)
    normalized_text = strip_accents(text[:3000])
    for pattern in (
        r"mau-so-(\d+)",
        r"mau-(\d+)",
        r"mau_so_(\d+)",
        r"mau\s+so\s+(\d+)",
        r"mau\s+[ivx]+-(\d+)",
    ):
        match = re.search(pattern, normalized_name)
        if match:
            return int(match.group(1))
    for pattern in (r"mau\s+so\s+(\d+)", r"mau\s+[ivx]+-(\d+)"):
        match = re.search(pattern, normalized_text)
        if match:
            return int(match.group(1))
    return None


def infer_appendix(file_name: str, text: str) -> str | None:
    normalized_name = strip_accents(file_name)
    normalized_text = strip_accents(text[:3000])
    if "phu-luc-iii" in normalized_name or re.search(r"mau\s+iii-", normalized_text):
        return "III"
    if "phu-luc-ii" in normalized_name or re.search(r"mau\s+ii-", normalized_text):
        return "II"
    if "phu-luc-i" in normalized_name:
        return "I"
    if "ho-kinh-doanh" in normalized_name or "ho kinh doanh" in normalized_text:
        return "II"
    return None


def source_url_by_file_name() -> dict[str, str]:
    if not DOC_LINKS_PATH.exists():
        return {}
    payload = json.loads(DOC_LINKS_PATH.read_text(encoding="utf-8"))
    result: dict[str, str] = {}
    for item in payload:
        url = str(item.get("url") or "")
        file_name = unquote(urlparse(url).path.rsplit("/", 1)[-1])
        result[file_name] = url
    return result


def split_long_text(text: str, max_chars: int = MAX_CHUNK_CHARS) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    paragraphs = [paragraph.strip() for paragraph in text.splitlines() if paragraph.strip()]
    parts: list[str] = []
    current = ""
    for paragraph in paragraphs:
        candidate = f"{current}\n{paragraph}".strip() if current else paragraph
        if len(candidate) > max_chars:
            if current:
                parts.append(current)
            current = paragraph
        else:
            current = candidate
    if current:
        parts.append(current)
    return parts


def choose_available_forms() -> tuple[list[dict[str, Any]], dict[str, list[int]]]:
    by_form: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    source_urls = source_url_by_file_name()

    for path in sorted(DOCX_DIR.glob("*.docx")):
        text = read_docx_text(path)
        form_number = infer_form_number(path.name, text)
        appendix = infer_appendix(path.name, text)
        if not form_number or appendix not in {"I", "II"}:
            continue

        normalized = strip_accents(f"{path.name}\n{text[:500]}")
        normalized_name = strip_accents(path.name)
        is_tt68_candidate = (
            "2025" in path.name
            or "doanh nghiep" in normalized
            or "ho kinh doanh" in normalized
            or (
                appendix == "I"
                and "phu-luc-i" in normalized_name
                and "phu-luc-ii" not in normalized_name
                and "phu-luc-iii" not in normalized_name
            )
        )
        if appendix == "II" and "ho kinh doanh" not in normalized and "2025" not in path.name:
            is_tt68_candidate = False
        if not is_tt68_candidate:
            continue

        by_form[(appendix, form_number)].append(
            {
                "appendix": appendix,
                "form_number": form_number,
                "file": str(path),
                "file_name": path.name,
                "source_url": source_urls.get(path.name),
                "text": text,
                "char_count": len(text),
            }
        )

    chosen: list[dict[str, Any]] = []
    for forms in by_form.values():
        forms.sort(
            key=lambda item: (
                "2025" in item["file_name"],
                item["char_count"],
                item["file_name"],
            ),
            reverse=True,
        )
        chosen.append(forms[0] | {"alternatives": len(forms)})

    coverage = {
        "missing_appendix_i": [idx for idx in range(1, 81) if ("I", idx) not in by_form],
        "missing_appendix_ii": [idx for idx in range(1, 29) if ("II", idx) not in by_form],
    }
    chosen.sort(key=lambda item: (item["appendix"], item["form_number"]))
    return chosen, coverage


def title_from_form_text(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    title_lines: list[str] = []
    for line in lines[1:8]:
        normalized = strip_accents(line)
        if any(skip in normalized for skip in ("cong hoa", "doc lap", "hanh phuc", "ngay", "so:")):
            continue
        title_lines.append(line)
        if len(title_lines) == 2:
            break
    return " - ".join(title_lines) if title_lines else "Biểu mẫu"


def build_form_chunks(forms: list[dict[str, Any]]) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    for form in forms:
        appendix_label = f"Phụ lục {form['appendix']}"
        form_label = f"Mẫu số {form['form_number']}"
        parent_id = f"68_2025_tt_btc_phu_luc_{form['appendix'].lower()}_mau_{form['form_number']:02d}"
        title = title_from_form_text(form["text"])
        header = f"{appendix_label}, {form_label}. {title}"
        text_parts = split_long_text(form["text"])
        for part_index, body in enumerate(text_parts, 1):
            total_parts = len(text_parts)
            chunk_id = parent_id if total_parts == 1 else f"{parent_id}_part_{part_index:02d}"
            part_label = "" if total_parts == 1 else f"\n[Phần {part_index}/{total_parts}]"
            full_text = f"{header}{part_label}\n{body}"
            chunk = deepcopy(TT68_BASE)
            chunk.update(
                {
                    "chunk_id": chunk_id,
                    "chuong": appendix_label,
                    "ten_chuong": "BIỂU MẪU SỬ DỤNG TRONG ĐĂNG KÝ DOANH NGHIỆP"
                    if form["appendix"] == "I"
                    else "BIỂU MẪU SỬ DỤNG TRONG ĐĂNG KÝ HỘ KINH DOANH",
                    "so_dieu": form_label,
                    "ten_dieu": title,
                    "noi_dung": full_text,
                    "nguon": "docx",
                    "source_url": form["source_url"],
                    "source_file": str(Path(form["file"]).resolve()),
                    "parent_chunk_id": parent_id,
                    "part_index": part_index,
                    "part_total": total_parts,
                    "char_count": len(full_text),
                }
            )
            chunks.append(chunk)
    return chunks


def main() -> None:
    configure_console_encoding()
    if not CHUNKS_PATH.exists():
        raise SystemExit(f"Không tìm thấy {CHUNKS_PATH}")
    if not DOCX_DIR.exists():
        raise SystemExit(f"Không tìm thấy {DOCX_DIR}")

    existing_chunks = json.loads(CHUNKS_PATH.read_text(encoding="utf-8"))
    forms, coverage = choose_available_forms()
    form_chunks = build_form_chunks(forms)

    # Keep the three legal-article chunks from TT68, replace previous appendix list chunks.
    kept_chunks = [
        chunk
        for chunk in existing_chunks
        if chunk.get("so_hieu") != "68/2025/TT-BTC"
        or str(chunk.get("so_dieu")) in {"Điều 1", "Điều 2", "Điều 3"}
    ]
    merged = kept_chunks + form_chunks
    CHUNKS_PATH.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")

    audit_path = Path("downloads/tt68_forms_coverage.json")
    audit_path.write_text(
        json.dumps(
            {
                "available_forms": [
                    {
                        key: value
                        for key, value in form.items()
                        if key not in {"text"}
                    }
                    for form in forms
                ],
                **coverage,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"Đã thêm {len(form_chunks)} chunks biểu mẫu TT68 từ {len(forms)} mẫu DOCX.")
    print(f"Thiếu Phụ lục I: {coverage['missing_appendix_i']}")
    print(f"Thiếu Phụ lục II: {coverage['missing_appendix_ii']}")
    print(f"Đã ghi coverage audit: {audit_path}")


if __name__ == "__main__":
    main()
