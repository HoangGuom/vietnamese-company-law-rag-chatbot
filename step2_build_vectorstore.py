"""Build a local vector store from legal_chunks.json.

The vector store is built with dense embeddings via sentence-transformers.
"""

from __future__ import annotations

import argparse
import json
from importlib import import_module
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_EMBEDDING_MODEL = "intfloat/multilingual-e5-small"


@dataclass
class VectorRecord:
    chunk_id: str
    text: str
    metadata: dict[str, Any]
    vector: list[float]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a local vector store from legal_chunks.json")
    parser.add_argument("--input", default="legal_chunks.json", help="Path to the chunks JSON file")
    parser.add_argument(
        "--output",
        default=str(Path("vectorstore") / "legal_vectorstore.json"),
        help="Path to the generated vector store JSON",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_EMBEDDING_MODEL,
        help="SentenceTransformer model name",
    )
    parser.add_argument("--batch-size", type=int, default=32, help="Embedding batch size")
    parser.add_argument(
        "--include-inactive",
        action="store_true",
        help="Include chunks marked su_dung_cho_rag=false. By default only current RAG sources are embedded.",
    )
    args = parser.parse_args()
    if args.batch_size <= 0:
        parser.error("--batch-size must be greater than 0")
    return args


def load_chunks(path: Path, include_inactive: bool = False) -> tuple[list[dict[str, Any]], int]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    if not isinstance(data, list):
        raise ValueError("legal_chunks.json must contain a JSON array")

    chunk_ids: list[str] = []
    for index, item in enumerate(data):
        if not isinstance(item, dict):
            raise ValueError(f"Chunk at index {index} is not an object")
        if "noi_dung" not in item:
            raise ValueError(f"Chunk at index {index} is missing noi_dung")
        if "chunk_id" not in item:
            raise ValueError(f"Chunk at index {index} is missing chunk_id")
        chunk_ids.append(str(item["chunk_id"]))

    duplicates = [chunk_id for chunk_id, count in Counter(chunk_ids).items() if count > 1]
    if duplicates:
        preview = ", ".join(duplicates[:10])
        raise ValueError(f"Duplicate chunk_id values found: {preview}")

    if include_inactive:
        return data, 0

    active_chunks = [chunk for chunk in data if chunk.get("su_dung_cho_rag", True)]
    return active_chunks, len(data) - len(active_chunks)


def metadata_for(chunk: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in chunk.items() if key != "noi_dung"}


def build_vectors(
    chunks: list[dict[str, Any]],
    model_name: str,
    batch_size: int,
) -> tuple[list[VectorRecord], dict[str, Any]]:
    try:
        SentenceTransformer = import_module("sentence_transformers").SentenceTransformer
    except ImportError as exc:
        raise RuntimeError(
            "Missing dependency: sentence-transformers. Install it before building the vector store."
        ) from exc

    model = SentenceTransformer(model_name)
    raw_texts = [str(chunk["noi_dung"]) for chunk in chunks]
    texts = [f"passage: {text}" for text in raw_texts] if "e5" in model_name.lower() else raw_texts
    embeddings = model.encode(
        texts,
        batch_size=batch_size,
        normalize_embeddings=True,
        show_progress_bar=True,
    )

    records: list[VectorRecord] = []
    for chunk, text, vector in zip(chunks, raw_texts, embeddings, strict=True):
        records.append(
            VectorRecord(
                chunk_id=str(chunk["chunk_id"]),
                text=text,
                metadata=metadata_for(chunk),
                vector=[float(value) for value in vector],
            )
        )

    dimension = len(records[0].vector) if records else 0
    manifest = {
        "schema_version": 2,
        "text_field": "noi_dung",
        "total_documents": len(chunks),
        "documents_with_text": sum(1 for text in raw_texts if text.strip()),
        "vector_type": "dense_embedding",
        "embedding_model": model_name,
        "embedding_dimension": dimension,
        "normalized": True,
        "document_prefix": "passage: " if "e5" in model_name.lower() else "",
    }
    return records, manifest


def save_vectorstore(records: list[VectorRecord], manifest: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "manifest": manifest,
        "documents": [
            {
                "chunk_id": record.chunk_id,
                "noi_dung": record.text,
                "metadata": record.metadata,
                "vector": record.vector,
            }
            for record in records
        ],
    }

    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)

    chunks, skipped_inactive = load_chunks(input_path, args.include_inactive)
    try:
        records, manifest = build_vectors(chunks, args.model, args.batch_size)
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc
    save_vectorstore(records, manifest, output_path)

    print(f"Loaded {len(chunks)} chunks from {input_path}")
    if skipped_inactive:
        print(f"Skipped {skipped_inactive} inactive/historical chunks")
    print(f"Vector type: {manifest['vector_type']}")
    print(f"Embedding model: {manifest['embedding_model']}")
    print(f"Embedding dimension: {manifest['embedding_dimension']}")
    print(f"Saved to {output_path}")
    print("Text field used for vectorization: noi_dung")
    print("Metadata preserved: all fields except noi_dung")


if __name__ == "__main__":
    main()
