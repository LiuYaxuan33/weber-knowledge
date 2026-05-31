# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## About

This is a personal research collection of materials related to **Max Weber** (马克斯·韦伯, 1864–1920), the German sociologist, historian, and political economist.

## Contents

- **`三联-韦伯作品集.epub`** — Weber's collected works, Sanlian (三联) edition
- **`上人社-韦伯作品集.epub`** — Weber's collected works, Shanghai People's Publishing (上人社) edition
- **`迪尔克·克斯勒 - 2004 - 马克斯·韦伯的生平、著述及影响/`** — Dirk Käsler's *Max Weber: Eine Einführung in Leben, Werk und Wirkung* (Chinese translation by 郭锋, published by 法律出版社, 2000). Contains the full text in Markdown plus extracted figures/images.

## Python environment

All Python work uses the conda environment `Yearbook_Project`. Activate it before running any Python commands:

```bash
conda activate Yearbook_Project
```

Key packages available: `ebooklib`, `beautifulsoup4` (bs4), `lxml`.

## RAG Knowledge Base (`weber-rag/`)

Two-stage hierarchical retrieval system for querying Weber's works:

```bash
# Setup (on new machine)
conda create -n weber-rag python=3.10
conda activate weber-rag
pip install -r weber-rag/requirements.txt
cp weber-rag/.env.template weber-rag/.env   # then edit API keys

# Ingest all sources (builds ChromaDB index, ~10 min with bge-small)
cd weber-rag && python ingest.py

# Query
python query.py "韦伯如何定义'理想类型'？"
python query.py -i                    # interactive mode
python query.py -c "韦伯著述" "新教伦理"  # filter by category
python query.py --list-categories     # show categories
```

### Architecture

- **Embedding**: `BAAI/bge-small-zh-v1.5` (local, 512-dim) by default. Switch to `text-embedding-3-small` (OpenAI) or `BAAI/bge-m3` in `config.py`
- **LLM**: DeepSeek chat API (`deepseek-chat`). Configure `DEEPSEEK_API_KEY` in `.env`
- **Vector DB**: ChromaDB with two collections — `weber_sections` (chapter-level) and `weber_chunks` (paragraph-level)
- **Retrieval**: Stage 1 finds top-K relevant chapters, Stage 2 searches within them for specific paragraphs

### Adding new books

1. Add entry to `SOURCES` list in `config.py` with `type` (`epub` or `markdown`), `category`, and `edition`
2. Run `python ingest.py --force`

### Source categories

- `韦伯著述` — Weber's own writings (both EPUB editions)
- `传记与介绍` — Biography/introductions (Käsler)
- `相关史料` — Historical materials (future)
- `思想研究与讨论` — Research/discussion (future)
