# Weber RAG 知识库

基于向量检索 + LLM 的马克斯·韦伯著作问答系统。

## 架构

```
Source files (EPUB/Markdown)
  → Loader (按章节拆分)
    → Embedding (BAAI/bge-m3, 1024-dim)
      → ChromaDB (两层索引: sections + chunks)
        → 查询 → 分层检索 → LLM 生成回答
```

- **Embedding**: `BAAI/bge-m3`（本地运行，~2GB，首次自动下载到 `D:\huggingface_cache\`）
- **Vector DB**: ChromaDB，两层集合 — `weber_sections`（章节级）和 `weber_chunks`（段落级）
- **LLM**: DeepSeek Chat API
- **分层检索**:
  1. Stage 1: 找到 Top-K 相关章节
  2. Stage 2: 在这些章节内找到最相关的段落

## 快速开始

### 新电脑（从 git clone 开始）

```bash
# 一键安装
bash setup.sh        # Mac / Linux / Git Bash
# 或
setup.bat            # Windows CMD
```

`setup.sh` 自动完成：检查 Python → 配置 `.env`（提示输入 API Key）→ 安装依赖 → 从分片文件重建向量库。

### 已有完整环境（仅更新代码）

```bash
git pull
python ingest.py     # 增量索引（如有新增来源）
```

### Web 界面（推荐）

```bash
python app.py                  # 浏览器打开 http://127.0.0.1:7860
python app.py --port 8080      # 自定义端口
```

界面提供：
- 聊天式问答（支持多轮追问）
- 左侧筛选：按来源/分类过滤
- 「仅搜索」模式：只检索不调用 LLM（不消耗 API）
- 输入 `/new` 重置对话

### 终端查询

```bash
python query.py "韦伯如何定义'理想类型'？"
python query.py -i              # 交互模式（支持追问）
```

## 可移植数据

向量数据库（ChromaDB）已预先构建并导出为分片文件，新电脑无需运行 `ingest.py`。

### 从源机器导出

```bash
python export_data.py --split 50   # 生成 data/weber_data.npz + .part* 分片
git add data/weber_data.npz.part*
git commit -m "Update vector data"
```

### 在新机器上导入

`setup.sh` 自动处理。手动操作：

```bash
python import_data.py             # 从 .npz 或分片重建 chroma_db
python import_data.py --force     # 覆盖已有数据
```

## 查询

### 基本查询

```bash
python query.py "新教伦理与资本主义精神的核心论点是什么？"
```

### 按来源过滤

```bash
# 限定在某本书中搜索
python query.py --source "学术与政治" "什么是Klarheit？"
python query.py -s "新教伦理" "天职概念"

# 排除某本书
python query.py --exclude "宗教社会学" "魔鬼"
python query.py -e "经济与社会" "官僚制"

# 按大类筛选
python query.py --category "韦伯著述" "理想类型"
python query.py -c "传记与介绍" "韦伯生平"

# 按合集搜索（父子来源）
python query.py --collection "三联-韦伯作品集" "卡里斯玛"
python query.py -C "社会科学方法论文集" "价值无涉"
python query.py -E "上人社-韦伯作品集" "新教伦理"  # 排除整个合集

# 组合使用
python query.py -c "韦伯著述" -C "三联" -s "学术与政治" "价值中立"
```

### 查看可用的过滤选项

```bash
python query.py --list-sources     # 按来源分组列出书名（自动过滤前后附页）
python query.py --list-sources --show-all  # 含目录、译者说明等附页
python query.py --list-categories   # 列出分类和索引统计
```

`--list-sources` 会按父来源（EPUB 合集）分组显示，并自动隐藏少于 30 段的前后附页（目录、译者说明等）。

### 交互模式

```bash
python query.py -i

# 带初始过滤启动
python query.py -i -s "学术与政治"
python query.py -i -c "韦伯著述" -e "经济与社会"
```

交互模式下，第一问触发完整 RAG 检索；后续追问会重新检索，同时保留对话历史。

**会话内命令：**

| 命令 | 说明 | 示例 |
|------|------|------|
| `/source <书名>` | 限定搜索范围（模糊匹配） | `/source 学术与政治` |
| `/s <书名>` | 同上（短写） | `/s 新教伦理` |
| `/exclude <书名>` | 排除指定书（模糊匹配） | `/exclude 宗教社会学` |
| `/e <书名>` | 同上（短写） | `/e 经济与社会` |
| `/collection <合集>` | 限定到整个合集 | `/collection 三联` |
| `/col <合集>` | 同上（短写） | `/col 上人社` |
| `/exclude-collection <合集>` | 排除整个合集 | `/ecol 民族国家` |
| `/category <分类>` | 按分类筛选 | `/category 韦伯著述` |
| `/c <分类>` | 同上（短写） | `/c 传记与介绍` |
| `/filters` | 查看当前过滤条件 | |
| `/filter off` | 关闭所有过滤 | |
| `/new` | 重置对话历史 | |
| `quit` / `exit` | 退出 | |

书名参数支持与 `--source`/`--exclude` 相同的模糊匹配规则。切换过滤条件时对话历史会自动重置，因为上下文范围发生了变化。

### 调整检索深度

```bash
python query.py --top-sections 10 --top-chunks 15 "韦伯的方法论"
```

## 索引管理

```bash
# 增量索引（只处理新来源）
python ingest.py

# 查看当前状态
python ingest.py --stats

# 添加/重新索引单个来源
python ingest.py --add SRC_NAME

# 删除单个来源（不重建 DB）
python ingest.py --delete SRC_NAME

# 完全重建
python ingest.py --force

# 修复旧数据的 source_name 字段
python ingest.py --repair
```

## 来源列表

| 书名 | 类型 | 分类 | 出版社 |
|------|------|------|--------|
| 经济与社会（第1卷） | EPUB | 韦伯著述 | 上海人民出版社 |
| 经济与社会（第2卷） | EPUB | 韦伯著述 | 上海人民出版社 |
| 新教伦理与资本主义精神 | EPUB | 韦伯著述 | 生活·读书·新知三联书店 |
| 学术与政治 | EPUB | 韦伯著述 | 生活·读书·新知三联书店 |
| 支配社会学 | EPUB | 韦伯著述 | 生活·读书·新知三联书店 |
| 宗教社会学 宗教与世界 | EPUB | 韦伯著述 | 生活·读书·新知三联书店 |
| 法律社会学 非正当性的支配 | EPUB | 韦伯著述 | 生活·读书·新知三联书店 |
| 经济与历史 支配的类型 | EPUB | 韦伯著述 | 生活·读书·新知三联书店 |
| 中国的宗教：儒教与道教 | EPUB | 韦伯著述 | 生活·读书·新知三联书店 |
| 印度的宗教：印度教与佛教 | EPUB | 韦伯著述 | 生活·读书·新知三联书店 |
| 社会学的基本概念；经济行动与社会团体 | EPUB | 韦伯著述 | 生活·读书·新知三联书店 |
| 民族国家与经济政策 | EPUB | 韦伯著述 | 生活·读书·新知三联书店 |
| 社会科学方法论文集 | EPUB | 韦伯著述 | 上海人民出版社 |
| 克斯勒-韦伯生平著述及影响 | Markdown | 传记与介绍 | 法律出版社 |

### 书名模糊匹配

`--source` 和 `--exclude` 支持模糊匹配，解析规则为：

1. **精确匹配**（忽略大小写）
2. **子串匹配**：`"新教伦理"` → `"新教伦理与资本主义精神"`
3. **相似匹配**（通过 difflib）：如果都不匹配，列出最接近的书名
4. **歧义提示**：如果匹配到多个，列出候选项让你选

## 配置

所有参数在 `config.py` 中调整：

```python
# 检索
TOP_SECTIONS = 10       # Stage 1: 检索章节数
TOP_CHUNKS = 15         # Stage 2: 检索段落数（受 section 范围限制）

# 分块
CHUNK_SIZE = 512        # 每块中文字符数
CHUNK_OVERLAP = 128     # 相邻块重叠字符数

# 嵌入
EMBEDDING_MODEL = "BAAI/bge-m3"
EMBEDDING_BATCH_SIZE = 3   # GPU VRAM 限制（8GB 安全值）
EMBEDDING_DEVICE = None    # None=自动，设为 "cpu" 强制 CPU

# LLM
LLM_MODEL = "deepseek-chat"
LLM_MAX_TOKENS = 8192
LLM_TEMPERATURE = 0.1
```

### 切换嵌入模型

```python
# 更小的中文模型（~400MB）
EMBEDDING_MODEL = "BAAI/bge-small-zh-v1.5"
EMBEDDING_DIM = 512

# OpenAI（需 API Key）
EMBEDDING_MODEL = "openai:text-embedding-3-small"
```

## 添加新著作

1. 将文件放入项目根目录
2. 在 `config.py` 的 `SOURCES` 列表添加条目：
   ```python
   {
       "name": "新书名称",
       "type": "epub",           # 或 "markdown"
       "path": os.path.join(PROJECT_ROOT, "新书文件.epub"),
       "category": "韦伯著述",    # 选择一个分类
       "edition": "出版社全称",
   }
   ```
3. 运行 `python ingest.py`（增量索引，只处理新书）

### 分类

- `韦伯著述` — Weber 本人的著作
- `传记与介绍` — 传记和介绍性作品
- `相关史料` — 历史材料（待添加）
- `思想研究与讨论` — 研究和讨论（待添加）

## 硬件要求

- **GPU**: 8GB+ VRAM 推荐（RTX 4060 Laptop 8GB 测试通过）
- **CPU**: 可以纯 CPU 运行（设置 `EMBEDDING_DEVICE = "cpu"`），但较慢
- **磁盘**: 模型 ~2GB，ChromaDB 索引 ~500MB
- **内存**: 8GB+ 推荐

## 离线运行

系统默认在加载 BGE-M3 模型时自动设置 `HF_HUB_OFFLINE=1`。模型首次下载后会缓存，后续查询无需联网即可完成向量检索。调用 DeepSeek API 生成回答仍需网络。

## 注意事项

- **出版社名使用全称**：`生活·读书·新知三联书店`（不是"三联"），`上海人民出版社`（不是"上人社"）
- **bge-m3 模型**首次运行自动下载，约 2GB
- **GPU VRAM 安全限制**：`EMBEDDING_BATCH_SIZE=3` 约用 7.3GB。增大需确认有足够显存
- **增量索引**：依赖 `source_name` 元数据字段判断已索引来源。旧数据可能缺失此字段，用 `--repair` 修复
