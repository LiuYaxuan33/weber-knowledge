# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## About

This is a personal research collection of materials related to **Max Weber** (马克斯·韦伯, 1864–1920), the German sociologist, historian, and political economist.

## Contents

Source files are organized under `资料原档/`:
- **`资料原档/著述/上海人民出版社-韦伯作品集/`** — 7 EPUBs, 上海人民出版社 edition
- **`资料原档/著述/上海三联书店-韦伯作品集/`** — 11 EPUBs, 上海三联书店（理想国）edition
- **`资料原档/著述/`** — 1 EPUB (三联-民族国家与经济政策)
- **`资料原档/传记与介绍/`** — 3 EPUBs + 2 Markdown (Käsler, Kaube, Mommsen, Bendix, Mommsen & Osterhammel)
- **`资料原档/思想研究与讨论/`** — 4 EPUBs + 1 PDF set (难以驯化的利维坦, 陈涛 2026, marker OCR → markdown, 4/8 chapters done)
- **`资料原档/史料/`** — 1 EPUB (新编剑桥世界近代史 第11–12卷)

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
python query.py -s "学术与政治" "..."     # filter by source name (fuzzy match)
python query.py -s "书A" -s "书B" "..."  # multi-source: repeat -s for each
python query.py -c "韦伯著述" "..."       # filter by category
python query.py -c "韦伯著述" -c "传记与介绍" "..."  # multi-category
python query.py --list-sources           # show sources and chunk counts
python query.py --top-sections 6 --top-chunks 10 "..."  # override retrieval depth

# Interactive mode: /new to reset conversation, quit to exit
```

### Important operational notes

- **Publisher names use FULL names** (not abbreviations):
  - `生活·读书·新知三联书店` (not "三联" — ambiguous with 上海三联)
  - `上海人民出版社` (not "上人社")
  - `上海三联书店` (for 理想国 series)
  - `法律出版社` (Käsler biography publisher)
- **bge-m3 model**: ~2GB, downloads to `D:\huggingface_cache\`. `HF_HUB_OFFLINE=1` is set automatically in `embeddings.py`.
- **GPU VRAM**: RTX 4060 Laptop 8GB. `EMBEDDING_BATCH_SIZE=3` is the max safe value (~4.4GB used with single process). Default (32) OOMs. **Only run one ingest process at a time** — two processes = two bge-m3 models in VRAM = OOM.
- **Incremental ingest**: `get_ingested_sources()` checks `source_name` metadata. To re-ingest a single source: `--delete SRC` then `python ingest.py`.
- **Source ordering**: SOURCES in `config.py` are ordered small→large so quick wins finish first.
- **EPUB parser** (`loaders/epub.py`): Uses NCX fragment anchors (`#sigil_toc_id_1`) for precise section boundary detection when available, falls back to text matching with full-width→half-width normalization. For books with broken TOCs (image-only pages), scans all HTML files directly. See "EPUB loader architecture" below.
- **终端中文乱码**: Windows GBK terminal + Python UTF-8. Always use `export PYTHONIOENCODING=utf-8` before Python commands.
- **Desktop launcher** (`start_weber.bat`): Uses hardcoded conda Python path for reliability when double-clicked. If Anaconda is installed elsewhere, edit the path in the bat file. Gradio's `inbrowser=True` handles browser opening — do NOT add `start http://...` before `python app.py` (would open before server is ready).

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
2. Stage 1: `search_sections()` — find top-K chapters by cosine similarity
3. Stage 2: `search_chunks()` — search within those chapters' `section_id`s for the most relevant paragraphs
4. Post-processing:
   - **Front matter filter**: `_is_front_matter()` skips chapters matching patterns like "前言", "目录", "Title Page", "Contents", "索引", etc. Add patterns to `_FRONT_MATTER_PATTERNS` in `store.py`.
   - **Diversity bonus**: top-1 chunk per source gets +0.1 score boost to prevent single-book dominance
   - **Cross-language bonus**: chunks in a different language from the query get +0.05 boost (CJK vs non-CJK detection via `_is_cjk()`)
5. Returns (section_results, chunk_results)

**Filter flags** (`--list-sources`, `-s`, `-c`):
- `-s <name>` — filter by `source_name` (config entry name). Uses fuzzy matching via `resolve_book_name()`. Repeatable (`-s A -s B`) for multiple sources; passed as list to `_build_where()` which uses ChromaDB `$in`.
- `-c <name>` — filter by `source_category` (韦伯著述, 传记与介绍, etc.). Repeatable for multiple categories.
- `--list-sources` — show all sources grouped, with chunk counts

**Query** (`query.py`):
1. Retrieve sections + chunks
2. Format into a structured reference block using `_format_source()`: `书：《title》 | 章节：chapter | 出版社：publisher year`
3. Send to LLM with SYSTEM_PROMPT (act as Weber expert, cite sources with `[书名, 章节名, 出版社]` format, acknowledge gaps)
4. Append reference list using book titles (not internal IDs): `《book》 chapter（publisher）`
5. Interactive mode (`-i`): `/new` to reset, `/source <name>` to filter, `/exclude <name>` to exclude

### Gradio Web UI (`app.py`)

```bash
python app.py                    # http://127.0.0.1:7860, opens browser automatically
python app.py --port 8080        # custom port
python app.py --share            # public Gradio share link
```

**Desktop launcher**: `start_weber.bat` in repo root. Double-click to start the server + auto-open browser. Uses full conda Python path (`C:\Users\32783\Anaconda3\python.exe`) so it works without PATH setup. Does NOT open browser prematurely — Gradio's `inbrowser=True` handles timing correctly.

**UI layout**: Left sidebar (filters) + right chat area.

Filter controls:
- **来源筛选** — multi-select dropdown (matches `source_name`). Empty = all sources.
- **分类筛选** — multi-select dropdown (matches `source_category`). Empty = all categories.
- **屏蔽来源** — multi-select dropdown (exclude specific sources).
- **仅搜索** — checkbox to skip LLM Q&A (retrieval only).
- **每本书首位加权** / **跨语言加权** — sliders (0–0.5 / 0–0.3), update `config.DIVERSITY_BONUS` / `config.CROSS_LANG_BONUS` at runtime.

All three dropdowns are multi-select. The store layer (`_build_where()`) handles `list[str]` filters via ChromaDB `$in` for OR matching (e.g., select two categories → match either).

**Scrollbar**: Page uses `fill_height=True` on Blocks. Chatbot height is viewport-relative (`calc(100vh - 220px)`). Sidebar has `overflow-y: auto` for independent scroll when content is tall. Only one scroll context on the page (chatbot).

**Gradio 6.x note**: CSS goes to `launch(css=...)`, not `Blocks(css=...)`. `fill_height` is only valid on `Blocks`, not on `Row` or `Column`. `equal_height=True` is the Row-level equivalent.

### EPUB loader architecture

`loaders/epub.py` extracts structured text from EPUBs. Key design:

1. **TOC parsing** (`_parse_ncx`): Parses NCX (EPUB2) or NAV (EPUB3) into a tree of `{title, href, level, children}`.

2. **HTML extraction** (`_extract_html`): Converts HTML to clean text. **Anchor marker insertion**: for each HTML element with an `id` attribute, inserts a marker (`ANCHOR{id}ANCHOR`) into the text. Markers are located after extraction and removed, giving us `{file: {anchor_id: text_position}}` maps.

3. **Section splitting** (`_extract_section_text`): When multiple TOC entries share one HTML file, splits the document at anchor positions. Priority: NCX fragment anchor → text match with normalization → full doc fallback. Returns `""` for child entries that can't be split (avoids content duplication).

4. **Text matching fallback** (`_text_search`): Tries exact match → char normalization (full-width `　：（）` → half-width ` :()`) → footnote-stripped match. Only used when anchors are unavailable.

5. **Fallback HTML scan** (`_fallback_html_scan`): When TOC produces 0 sections (e.g., TOC points to image-only pages), scans all HTML files directly. Skips front matter (版权页, 目录, etc.) and image pages (< 500 chars). Detects volume boundaries by CIP page markers. Skips index pages (`first_line.startswith('索引')`).

### Common pitfalls when adding EPUBs

- **Full-width vs half-width**: NCX titles often use half-width spaces ` ` while body text uses full-width `　`. The normalizer handles this, but if a new EPUB shows content overlap, check `_char_normalize`.
- **"Same page" anchors**: Some EPUBs have multiple TOC entries sharing one anchor (parent without fragment + child with unique fragment). This is handled correctly — the child's anchor splits the file.
- **Broken TOC**: If `_parse_ncx` returns 0 useful entries, the fallback HTML scanner kicks in. Check `_fallback_html_scan`'s SKIP_IF_CONTAINS list if chapters are missing.
- **TOC entries with empty hrefs**: Children sometimes have `href=""`. These get skipped by `_get_text_for_entry`.

### Common pitfalls when adding markdown files

- **Appendix/TOC-style content must not use `##` headings.** The markdown loader splits on all `## ` headings. If an appendix is a table-of-contents or outline (like 陈涛-《难以驯化的利维坦》's appendices), its internal structure must use `**...**` (bold) or plain text — NOT `##`/`###`/`####`. Otherwise each `##` creates a bogus tiny section. If the appendices are just reference material (not substantive content), consider deleting them from the file entirely.
- **Verify section count after ingest.** A single book should have roughly chapters+1 sections. If `python ingest.py --stats` shows an abnormally high count, check the headings with `grep "^##" <file>`.

### Adding new books

1. Add entry to `SOURCES` list in `config.py` with required fields: `name`, `type`, `path`, `category`, `author`, `title`, `publisher` (optional: `year`, `translator`, `isbn`)
2. Run `python ingest.py` (incremental — only the new book will be processed)
3. If the new book shows unexpected word counts or 0 sections, debug with the loaders directly

### Source categories

- `韦伯著述` — Weber's own writings
- `传记与介绍` — Biography/introductions
- `相关史料` — Historical materials
- `思想研究与讨论` — Research/discussion
