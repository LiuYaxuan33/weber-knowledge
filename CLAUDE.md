# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## About

This is a personal research collection of materials related to **Max Weber** (马克斯·韦伯, 1864–1920), the German sociologist, historian, and political economist.

## Contents

- **`三联-韦伯作品集.epub`** — Weber's collected works, 生活·读书·新知三联书店 edition
- **`上人社-韦伯作品集.epub`** — Weber's collected works, 上海人民出版社 edition (ISBN 9787563345267)
- **`马克斯·韦伯 - 2018 - 民族国家与经济政策：修订译本.epub`** — *The Nation State and Economic Policy*, 生活·读书·新知三联书店 (ISBN 9787108062185)
- **`马克斯·韦伯 - 2022 - 社会科学方法论文集.epub`** — Collected essays on social science methodology, 上海人民出版社 (ISBN 9787208179035)
- **`迪尔克·克斯勒 - 2004 - 马克斯·韦伯的生平、著述及影响/`** — Dirk Käsler's *Max Weber: Eine Einführung in Leben, Werk und Wirkung* (Chinese translation by 郭锋, published by 法律出版社, 2000). Full text in Markdown + extracted figures (JPEGs at repo root)

## Python environment

All Python work uses the **`base`** conda environment. No activation needed if already in `base`; otherwise:

```bash
conda activate base
```

Key packages: `ebooklib`, `beautifulsoup4` (bs4), `lxml`, `chromadb`, `sentence-transformers`, `openai`, `python-dotenv`.

## RAG Knowledge Base (`weber-rag/`)

Two-stage hierarchical retrieval system for querying Weber's works.

### Quick reference

```bash
# First-time setup
pip install -r weber-rag/requirements.txt
cp weber-rag/.env.template weber-rag/.env   # edit DEEPSEEK_API_KEY
cd weber-rag && python ingest.py            # first run: downloads bge-m3 (~2GB)

# Daily use
python ingest.py                    # incremental: only new sources
python ingest.py --stats            # show what's ingested
python ingest.py --add SRC          # re-ingest one source (upsert)
python ingest.py --delete SRC       # remove one source (no re-embed needed)
python ingest.py --force            # nuke everything and rebuild
python ingest.py --repair           # fix old data lacking source_name

# Query
python query.py "韦伯如何定义'理想类型'？"
python query.py -i                      # interactive mode (supports follow-ups)
python query.py -c "韦伯著述" "新教伦理"    # filter by category
python query.py --list-categories       # show categories and index stats
python query.py --top-sections 6 --top-chunks 10 "..."  # override retrieval depth

# Interactive mode: /new to reset conversation, quit to exit
```

### Important operational notes

- **Publisher names use FULL names** (not abbreviations):
  - `生活·读书·新知三联书店` (not "三联" — ambiguous with 上海三联)
  - `上海人民出版社` (not "上人社")
  - `法律出版社` (Käsler biography publisher)
- **bge-m3 model**: ~2GB, downloads to `D:\huggingface_cache\`. `HF_HUB_OFFLINE=1` is set automatically in `embeddings.py` — no manual env var needed for ingest or query.
- **GPU VRAM**: RTX 4060 Laptop 8GB. `EMBEDDING_BATCH_SIZE=3` is the max safe value (~7.3GB used). Default (32) OOMs. Monitor with `nvidia-smi`.
- **Incremental ingest**: `get_ingested_sources()` checks `source_name` metadata. If missing (old data), falls back to matching `edition` against `SOURCES` config. Run `--repair` once after first ingest with new code to populate `source_name`.
- **--delete**: Remove a single source without touching others: `python ingest.py --delete SRC`. No need to `--force` nuke the whole DB.
- **Source ordering**: SOURCES in `config.py` are ordered small→large so quick wins finish first. Keep this order when adding new books.
- **EPUB parser**: `loaders/epub.py` splits TOC entries sharing the same HTML file by detecting sibling section boundaries. If texts appear duplicated or too large, check `_build_file_index` / `_extract_section_text`.

### Architecture

- **Embedding**: `BAAI/bge-m3` (local, ~2GB, 1024-dim). Can switch to OpenAI's `text-embedding-3-small` or `BAAI/bge-small-zh-v1.5` in `config.py`. Embedding dimension is read from the model at runtime (not hardcoded).
- **LLM**: DeepSeek chat API. Configure `DEEPSEEK_API_KEY` in `.env`.
- **Vector DB**: ChromaDB with two collections — `weber_sections` (chapter-level) and `weber_chunks` (paragraph-level). Cosine similarity via `hnsw:space`.

### Data flow

**Ingest pipeline** (`ingest.py`):
```
Source files → Loader (load_epub / load_markdown) → sections[]
  → embed each section via EmbeddingModel → add_sections() to ChromaDB
  → chunk each section via chunker → embed chunks → add_chunks() to ChromaDB
```

Loaders return a uniform `list[dict]` where each dict has `{"text": str, "metadata": {...}}`. The metadata dict must include `section_id`, `book`, `chapter`, `edition`, and `source_category` — these fields power retrieval filtering and citation formatting.

The **chunker** (`chunker.py`) splits Chinese text at natural boundaries with this priority: paragraph break (`\n\n`) > sentence-ending punctuation (`。？！`) > clause boundary (`，；`) > hard character cutoff. Configurable via `CHUNK_SIZE`/`CHUNK_OVERLAP` in `config.py`.

**Embedding model** (`embeddings.py`): Factory pattern via `create_embedding_model()`. Returns a subclass of the abstract `EmbeddingModel` — either `BGEM3Embedding` (local SentenceTransformer) or `OpenAIEmbedding` (API). Auto-falls back to local BGE if no OpenAI key is found.

**Retrieval** (`store.py` → `hierarchical_search()`):
1. Embed user query
2. Stage 1: `search_sections()` — find top-K chapters by cosine similarity, optionally filtered by `source_category`
3. Stage 2: `search_chunks()` — search within those chapters' `section_id`s for the most relevant paragraphs
4. Returns both section and chunk results for context assembly

**Query** (`query.py`):
1. Retrieve sections + chunks
2. Format into a structured reference block (chapters section, paragraphs section)
3. Send to LLM with a SYSTEM_PROMPT that instructs it to act as a Weber expert, cite sources, and acknowledge gaps
4. Append a source summary to the response
5. Interactive mode (`-i`): maintains conversation history for follow-up questions. First question triggers full RAG retrieval; follow-ups re-retrieve with new query but include prior chat context. Use `/new` to reset.

### Adding new books

1. Add entry to `SOURCES` list in `config.py` with `type` (`epub` or `markdown`), `category`, and `edition`
2. Run `python ingest.py` (incremental — only the new book will be processed)

### Source categories

- `韦伯著述` — Weber's own writings
- `传记与介绍` — Biography/introductions (Käsler)
- `相关史料` — Historical materials (future)
- `思想研究与讨论` — Research/discussion (future)
