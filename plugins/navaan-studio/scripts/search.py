"""search.py  the one search interface (FR-030): query in, ranked hits out. Backed by Postgres (pg_trgm + full text) in catalog_store's schema.

Author: Navjyot Nishant
Created: 2026-10-16
Last updated: 2026-10-16
Description: screens call search(), never SQL, so another engine (Meilisearch, Typesense) can replace this file without touching them.
"""
import catalog_store as K
import translit

KINDS = ("track", "album", "playlist", "short")


def search(q, kinds=None, limit=20):
    """Hits for what the person typed, in Devanagari or Roman letters: [{kind, id, slug, title, title_roman, score}]. Exact start of the text ranks first, then similarity."""
    f = translit.fold(q)
    if len(f) < 2: return []
    kinds = [k for k in (kinds or KINDS) if k in KINDS]
    # a Devanagari query is searched by itself and by its Roman form, so either spelling finds either
    rq = translit.fold(translit.to_roman(q)) if translit._DEV.search(q) else f
    like = lambda x: x.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    a, b = like(f), like(rq)
    def go(c):
        return c.execute(
            "SELECT d.kind, d.subject_id::text AS id, COALESCE(t.slug, al.slug) AS slug, d.title_native AS title, d.title_roman, "
            "  GREATEST(word_similarity(?, d.search_text), word_similarity(?, d.search_text)) + (CASE WHEN d.search_text LIKE ? OR d.search_text LIKE ? THEN 0.5 ELSE 0 END)"
            "  + (CASE WHEN d.tsv @@ plainto_tsquery('simple', ?) THEN 0.25 ELSE 0 END) AS score "
            "FROM search_documents d LEFT JOIN tracks t ON d.kind = 'track' AND t.id = d.subject_id LEFT JOIN albums al ON d.kind = 'album' AND al.id = d.subject_id "
            "WHERE d.kind = ANY(?) AND (? <% d.search_text OR ? <% d.search_text OR d.search_text LIKE ? OR d.search_text LIKE ? OR d.tsv @@ plainto_tsquery('simple', ?)) "
            "ORDER BY score DESC, d.title_native LIMIT ?",
            (f, rq, a + "%", b + "%", f, kinds, f, rq, "%" + a + "%", "%" + b + "%", f, max(1, min(int(limit), 50)))).fetchall()
    return [{"kind": r["kind"], "id": r["id"], "slug": r["slug"], "title": r["title"], "title_roman": r["title_roman"], "score": round(float(r["score"]), 3)} for r in K._tx(go)]
