# Semantic RAG Design

## Goal

Replace fragile Chinese bigram-only retrieval with local semantic retrieval so equivalent recruitment questions match the same knowledge entry, while unrelated questions remain below the reliability threshold.

## Design

- SQLite remains the source of truth for knowledge CRUD.
- FastEmbed runs `BAAI/bge-small-zh-v1.5` from `data/models/fastembed`.
- LanceDB stores derived vectors in `data/lancedb`; it can be rebuilt from SQLite.
- `KnowledgeStore.search()` combines the existing lexical score with cosine similarity. Exact lexical matches retain priority; semantic similarity handles paraphrases.
- Model initialization is lazy. If optional dependencies or model files are unavailable, search falls back to the existing lexical implementation and the application still starts.
- `.venv`, `star`, model cache, and LanceDB data stay local and are ignored by Git.

## Verification

- `还有招人吗` retrieves the entry describing an open position.
- An unrelated query does not retrieve recruitment knowledge.
- Disabled entries are never returned.
- Search still works when the semantic backend is unavailable.
