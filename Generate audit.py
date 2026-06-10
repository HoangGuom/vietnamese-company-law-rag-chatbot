"""
generate_audit.py
Tự động sinh legal_sources_audit.json từ legal_chunks.json.
Chạy sau mỗi lần crawl xong để audit luôn khớp với dữ liệu thực tế.

    python generate_audit.py
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

CHUNKS_PATH = Path("legal_chunks.json")
AUDIT_PATH  = Path("legal_sources_audit.json")


def generate_audit(chunks_path: Path = CHUNKS_PATH, audit_path: Path = AUDIT_PATH) -> None:
    if not chunks_path.exists():
        raise FileNotFoundError(f"Không tìm thấy {chunks_path}. Hãy chạy selenium_crawler.py trước.")

    with chunks_path.open("r", encoding="utf-8") as f:
        chunks: list[dict] = json.load(f)

    # Gom nhóm theo so_hieu
    groups: dict[str, list[dict]] = defaultdict(list)
    for chunk in chunks:
        groups[chunk["so_hieu"]].append(chunk)

    audit: list[dict] = []
    for so_hieu, group in groups.items():
        # Lấy metadata từ chunk đầu tiên (tất cả cùng so_hieu thì cùng metadata)
        first = group[0]

        # Đếm chunks active (su_dung_cho_rag=True)
        active_chunks = sum(1 for c in group if c.get("su_dung_cho_rag", False))
        total_chunks  = len(group)

        entry = {
            "so_hieu":             so_hieu,
            "ten_van_ban":         first.get("ten_van_ban", ""),
            "loai":                first.get("loai", ""),
            "chunks_active":       active_chunks,   # số chunks thực sự đưa vào RAG
            "chunks_total":        total_chunks,    # tổng số chunks đã crawl
            "su_dung_cho_rag":     active_chunks > 0,
            "hieu_luc_tu":         first.get("hieu_luc", None),
            "tinh_trang_hieu_luc": first.get("tinh_trang_hieu_luc", ""),
            "ngay_het_hieu_luc":   first.get("ngay_het_hieu_luc", None),
            "nguon_hieu_luc":      first.get("nguon_hieu_luc", ""),
            "source_url":          first.get("source_url", ""),
        }
        audit.append(entry)

    # Sắp xếp: active trước, sau đó theo so_hieu
    audit.sort(key=lambda x: (not x["su_dung_cho_rag"], x["so_hieu"]))

    with audit_path.open("w", encoding="utf-8") as f:
        json.dump(audit, f, ensure_ascii=False, indent=2)

    # In báo cáo ra terminal
    print(f"\n{'='*60}")
    print(f"  legal_sources_audit.json đã được cập nhật")
    print(f"{'='*60}")
    print(f"  Tổng số văn bản : {len(audit)}")
    print(f"  Đang dùng RAG   : {sum(1 for e in audit if e['su_dung_cho_rag'])}")
    print(f"  Không dùng RAG  : {sum(1 for e in audit if not e['su_dung_cho_rag'])}")
    print(f"  Tổng chunks RAG : {sum(e['chunks_active'] for e in audit)}")
    print(f"{'='*60}\n")

    for entry in audit:
        status = "✅ RAG" if entry["su_dung_cho_rag"] else "⛔ bỏ"
        het     = f" → hết {entry['ngay_het_hieu_luc']}" if entry["ngay_het_hieu_luc"] else ""
        print(
            f"  [{status}] {entry['so_hieu']:25s} "
            f"{entry['chunks_active']:>3} chunks active / {entry['chunks_total']:>3} total"
            f"{het}"
        )

    print(f"\n✅ Đã lưu → {audit_path}\n")


if __name__ == "__main__":
    generate_audit()