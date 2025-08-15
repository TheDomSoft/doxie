"""Ephemeral in-memory search over ParsedDocument lists using Whoosh.

Builds a temporary index in RAM for fast fetch->index->search cycles with no
persistence. Intended for MVP search across Confluence and web docs.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Tuple

from whoosh import scoring
from whoosh.analysis import StemmingAnalyzer
from whoosh.fields import ID, NUMERIC, TEXT, Schema
from whoosh.filedb.filestore import RamStorage
from whoosh.qparser import MultifieldParser, OrGroup

from doxie.parsers.base_parser import ParsedDocument


def _doc_title(meta: Dict[str, Any], text: str) -> str:
    # Prefer explicit metadata title, else fallback to first 120 chars of text
    t = str(meta.get("title") or "").strip()
    if t:
        return t
    return (text or "").strip()[:120]


def _make_schema() -> Schema:
    analyzer = StemmingAnalyzer()
    return Schema(
        docnum=NUMERIC(stored=True, unique=True),
        title=TEXT(stored=True, analyzer=analyzer, field_boost=1.8),
        # Store content for snippet highlighting
        content=TEXT(stored=True, analyzer=analyzer),
        # Stored metadata fields used by callers to construct URLs, etc.
        url=ID(stored=True),
        source=ID(stored=True),
        space=ID(stored=True),
        page_id=ID(stored=True),
    )


def _to_index_rows(docs: List[ParsedDocument]) -> Iterable[Tuple[int, Dict[str, Any]]]:
    for i, d in enumerate(docs):
        meta = dict(d.metadata or {})
        yield i, {
            "title": _doc_title(meta, d.text or ""),
            "content": d.text or "",
            "url": str(meta.get("source_url") or meta.get("url") or ""),
            "source": str(meta.get("source") or meta.get("origin") or ""),
            "space": str(meta.get("space") or ""),
            "page_id": str(meta.get("page_id") or meta.get("id") or ""),
        }


def search_docs_ephemeral(
    docs: List[ParsedDocument], query: str, *, k: int = 5
) -> List[Dict[str, Any]]:
    """Search a list of ParsedDocument objects with an in-memory Whoosh index.

    Returns list of dicts: {score, snippet, title, url, source, space, page_id}
    """
    if not query or not str(query).strip():
        return []

    schema = _make_schema()
    storage = RamStorage()
    idx = storage.create_index(schema)

    # Index quickly
    writer = idx.writer(limitmb=32)
    for docnum, row in _to_index_rows(docs):
        writer.add_document(
            docnum=docnum,
            title=row["title"],
            content=row["content"],
            url=row["url"],
            source=row["source"],
            space=row["space"],
            page_id=row["page_id"],
        )
    writer.commit()

    # Search
    with idx.searcher(weighting=scoring.BM25F()) as searcher:
        parser = MultifieldParser(["title", "content"], schema=idx.schema, group=OrGroup)
        try:
            q = parser.parse(query)
        except Exception:
            # On parse failure, fall back to raw string as a term query
            q = parser.parse('"' + query.replace('"', " ") + '"')
        results = searcher.search(q, limit=max(1, int(k)))
        results.fragmenter.charlimit = 300
        out: List[Dict[str, Any]] = []
        for hit in results:
            try:
                snippet = hit.highlights("content", top=2) or ""
            except Exception:
                snippet = ""
            out.append(
                {
                    "score": float(hit.score or 0.0),
                    "snippet": snippet,
                    "title": hit.get("title", ""),
                    "url": hit.get("url", ""),
                    "source": hit.get("source", ""),
                    "space": hit.get("space", ""),
                    "page_id": hit.get("page_id", ""),
                }
            )
    return out
