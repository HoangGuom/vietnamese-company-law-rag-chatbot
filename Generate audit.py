"""
generate_audit.py

Tự động sinh legal_sources_audit.json từ legal_chunks.json.

Lưu ý quan trọng:
- File audit chỉ là báo cáo thống kê cho con người đọc.
- File audit KHÔNG tham gia vào Step 2 embedding.
- Step 2 vẫn đọc trực tiếp legal_chunks.json và lọc từng chunk bằng su_dung_cho_rag.

Chạy sau mỗi lần crawl xong:

    python generate_audit.py
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

CHUNKS_PATH = Path("legal_chunks.json")
AUDIT_PATH = Path("legal_sources_audit.json")


def configure_console_encoding() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8")


def unique_values(group: list[dict[str, Any]], key: str) -> list[Any]:
    """
    Lấy danh sách giá trị khác nhau của một field trong nhóm chunk.

    Ví dụ:
    - cùng so_hieu nhưng source_url khác nhau
    - cùng so_hieu nhưng tinh_trang_hieu_luc khác nhau

    Hàm này giúp audit không bị phụ thuộc hoàn toàn vào group[0].
    """
    values: list[Any] = []
    seen: set[str] = set()

    for chunk in group:
        value = chunk.get(key)

        if value is None or value == "":
            continue

        marker = json.dumps(value, ensure_ascii=False, sort_keys=True)

        if marker not in seen:
            seen.add(marker)
            values.append(value)

    return values


def get_first_value(group: list[dict[str, Any]], key: str, default: Any = None) -> Any:
    """
    Lấy giá trị đầu tiên không rỗng trong nhóm chunk.
    """
    for chunk in group:
        value = chunk.get(key)
        if value is not None and value != "":
            return value
    return default


def detect_rag_status(active_chunks: int, total_chunks: int) -> str:
    """
    Trạng thái RAG ở cấp văn bản.

    all:
        Tất cả chunk của văn bản này được dùng cho RAG.

    none:
        Không chunk nào của văn bản này được dùng cho RAG.

    partial:
        Chỉ một phần chunk được dùng cho RAG.
        Đây là trường hợp quan trọng để tránh hiểu nhầm.
    """
    if total_chunks == 0:
        return "none"

    if active_chunks == 0:
        return "none"

    if active_chunks == total_chunks:
        return "all"

    return "partial"


def detect_flag_consistency(active_chunks: int, total_chunks: int) -> str:
    """
    Kiểm tra trong cùng một so_hieu có bị lẫn chunk true/false không.
    """
    if total_chunks == 0:
        return "empty"

    if active_chunks == 0:
        return "all_false"

    if active_chunks == total_chunks:
        return "all_true"

    return "mixed_true_false"


def build_warnings(
    so_hieu: str,
    rag_status: str,
    tinh_trang_values: list[Any],
    ngay_het_hieu_luc_values: list[Any],
    source_url_values: list[Any],
) -> list[str]:
    warnings: list[str] = []

    if rag_status == "partial":
        warnings.append(
            "Văn bản này có cả chunk dùng cho RAG và chunk không dùng cho RAG. "
            "Không được hiểu toàn bộ văn bản là true hoặc false."
        )

    if len(tinh_trang_values) > 1:
        warnings.append(
            "Các chunk cùng số hiệu có tinh_trang_hieu_luc không đồng nhất."
        )

    if len(ngay_het_hieu_luc_values) > 1:
        warnings.append(
            "Các chunk cùng số hiệu có ngay_het_hieu_luc không đồng nhất."
        )

    if len(source_url_values) > 1:
        warnings.append(
            "Các chunk cùng số hiệu có nhiều source_url khác nhau."
        )

    return warnings


def generate_audit(
    chunks_path: Path = CHUNKS_PATH,
    audit_path: Path = AUDIT_PATH,
) -> None:
    configure_console_encoding()
    if not chunks_path.exists():
        raise FileNotFoundError(
            f"Không tìm thấy {chunks_path}. Hãy chạy selenium_crawler.py trước."
        )

    with chunks_path.open("r", encoding="utf-8") as f:
        chunks: list[dict[str, Any]] = json.load(f)

    if not isinstance(chunks, list):
        raise ValueError("legal_chunks.json phải là một JSON array.")

    # Gom nhóm theo so_hieu
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for index, chunk in enumerate(chunks):
        if not isinstance(chunk, dict):
            raise ValueError(f"Chunk ở index {index} không phải object.")

        so_hieu = chunk.get("so_hieu")
        if not so_hieu:
            raise ValueError(f"Chunk ở index {index} thiếu field so_hieu.")

        groups[str(so_hieu)].append(chunk)

    audit: list[dict[str, Any]] = []

    for so_hieu, group in groups.items():
        total_chunks = len(group)
        active_chunks = sum(
            1 for c in group
            if c.get("su_dung_cho_rag", False) is True
        )
        inactive_chunks = total_chunks - active_chunks

        rag_status = detect_rag_status(active_chunks, total_chunks)
        flag_consistency = detect_flag_consistency(active_chunks, total_chunks)

        tinh_trang_values = unique_values(group, "tinh_trang_hieu_luc")
        ngay_het_hieu_luc_values = unique_values(group, "ngay_het_hieu_luc")
        source_url_values = unique_values(group, "source_url")
        nguon_hieu_luc_values = unique_values(group, "nguon_hieu_luc")

        warnings = build_warnings(
            so_hieu=so_hieu,
            rag_status=rag_status,
            tinh_trang_values=tinh_trang_values,
            ngay_het_hieu_luc_values=ngay_het_hieu_luc_values,
            source_url_values=source_url_values,
        )

        entry = {
            # Nhận diện văn bản
            "so_hieu": so_hieu,
            "ten_van_ban": get_first_value(group, "ten_van_ban", ""),
            "loai": get_first_value(group, "loai", ""),

            # Thống kê chunk
            "chunks_active": active_chunks,
            "chunks_inactive": inactive_chunks,
            "chunks_total": total_chunks,

            # Trạng thái RAG ở cấp văn bản
            # Không dùng su_dung_cho_rag true/false ở đây nữa để tránh hiểu nhầm.
            "rag_status": rag_status,
            "has_rag_chunks": active_chunks > 0,
            "all_chunks_used_for_rag": active_chunks == total_chunks,
            "flag_consistency": flag_consistency,

            # Thông tin hiệu lực
            "hieu_luc_tu": get_first_value(group, "hieu_luc", None),
            "tinh_trang_hieu_luc": get_first_value(group, "tinh_trang_hieu_luc", ""),
            "ngay_het_hieu_luc": get_first_value(group, "ngay_het_hieu_luc", None),

            # Các giá trị duy nhất để kiểm tra nếu metadata không đồng nhất
            "tinh_trang_hieu_luc_values": tinh_trang_values,
            "ngay_het_hieu_luc_values": ngay_het_hieu_luc_values,

            # Nguồn
            "nguon_hieu_luc": get_first_value(group, "nguon_hieu_luc", ""),
            "source_url": get_first_value(group, "source_url", ""),
            "nguon_hieu_luc_values": nguon_hieu_luc_values,
            "source_url_values": source_url_values,

            # Cảnh báo audit
            "warnings": warnings,
        }

        audit.append(entry)

    # Sắp xếp:
    # all trước, partial sau, none cuối.
    status_order = {
        "all": 0,
        "partial": 1,
        "none": 2,
    }

    audit.sort(
        key=lambda x: (
            status_order.get(x["rag_status"], 99),
            x["so_hieu"],
        )
    )

    with audit_path.open("w", encoding="utf-8") as f:
        json.dump(audit, f, ensure_ascii=False, indent=2)

    # In báo cáo ra terminal
    total_documents = len(audit)
    all_docs = sum(1 for e in audit if e["rag_status"] == "all")
    partial_docs = sum(1 for e in audit if e["rag_status"] == "partial")
    none_docs = sum(1 for e in audit if e["rag_status"] == "none")

    total_active_chunks = sum(e["chunks_active"] for e in audit)
    total_inactive_chunks = sum(e["chunks_inactive"] for e in audit)
    total_chunks = sum(e["chunks_total"] for e in audit)

    print(f"\n{'=' * 72}")
    print("  legal_sources_audit.json đã được cập nhật")
    print(f"{'=' * 72}")
    print(f"  Tổng số văn bản              : {total_documents}")
    print(f"  Văn bản dùng toàn bộ RAG     : {all_docs}")
    print(f"  Văn bản dùng một phần RAG    : {partial_docs}")
    print(f"  Văn bản không dùng cho RAG   : {none_docs}")
    print(f"  Tổng chunks active           : {total_active_chunks}")
    print(f"  Tổng chunks inactive         : {total_inactive_chunks}")
    print(f"  Tổng chunks đã crawl         : {total_chunks}")
    print(f"{'=' * 72}\n")

    for entry in audit:
        if entry["rag_status"] == "all":
            status = "✅ ALL"
        elif entry["rag_status"] == "partial":
            status = "⚠️ PARTIAL"
        else:
            status = "⛔ NONE"

        het = (
            f" → hết {entry['ngay_het_hieu_luc']}"
            if entry["ngay_het_hieu_luc"]
            else ""
        )

        print(
            f"  [{status}] {entry['so_hieu']:25s} "
            f"{entry['chunks_active']:>3} active / "
            f"{entry['chunks_inactive']:>3} inactive / "
            f"{entry['chunks_total']:>3} total"
            f"{het}"
        )

        for warning in entry["warnings"]:
            print(f"      ⚠️ {warning}")

    print(f"\n✅ Đã lưu → {audit_path}")
    print(
        "\nGhi chú: File audit chỉ là báo cáo thống kê. "
        "Step 2 không đọc file này; Step 2 lọc trực tiếp từ legal_chunks.json.\n"
    )


if __name__ == "__main__":
    generate_audit()
