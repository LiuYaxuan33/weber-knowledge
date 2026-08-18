# Weber RAG 知识库

基于向量检索 + LLM 的马克斯·韦伯（Max Weber, 1864–1920）著作问答系统。

## 架构

```
Source files (EPUB/Markdown)
  → Loader (按章节拆分)
    → Embedding (BAAI/bge-m3, 1024-dim)
      → ChromaDB (两层索引: sections + chunks)
        → 查询 → 分层检索 → LLM 生成回答
```

- **Embedding**: `BAAI/bge-m3` — 本地运行，多语言，1024 维。首次自动下载（~2GB），之后离线可用
- **Vector DB**: ChromaDB，两个集合 — `weber_sections`（章节级）和 `weber_chunks`（段落级），余弦相似度
- **LLM**: DeepSeek Chat API
- **分层检索**: 章节向量由该章全部段落向量归一化汇总（不会截断长章节）；Stage 1 找 Top-K 章节 → Stage 2 在这些章节内找最相关段落 → 多样性排序

## 快速开始

### 新电脑（git clone 后首次）

```bash
setup.bat            # Windows CMD，按提示输入 DeepSeek API Key
# 或
bash setup.sh        # Mac / Linux / Git Bash
```

`setup` 自动完成：创建独立 `.venv` → 配置 `.env` → 安装依赖 → 校验并从分片文件重建向量库。**无需 GPU，无需源文件，无需运行 ingest。** 首次查询会下载 bge-m3（约 2GB），之后可离线使用。

### 日常使用

```bash
# Web 界面（推荐）
python app.py                    # 浏览器打开 http://127.0.0.1:7860
python app.py --port 8080        # 自定义端口

# 终端单次查询
python query.py "韦伯如何定义'理想类型'？"

# 终端交互模式
python query.py -i
```

### Web 界面功能

- 聊天式问答，支持多轮追问（自动保留对话上下文）
- 左侧筛选面板：按来源/分类过滤，一键切换
- 「仅搜索」模式：只检索不调 LLM（不消耗 API token）
- 输入 `/new` 重置对话
- 点击示例问题快速开始

## 使用指南

### 基本查询

```bash
python query.py "新教伦理与资本主义精神的核心论点"
```

### 过滤

```bash
# 按分类
python query.py -c "韦伯著述" "理想类型"
python query.py -c "传记与介绍" "韦伯生平"

# 按书（模糊匹配）
python query.py -s "学术与政治" "Klarheit"
python query.py -s "新教伦理" "天职概念"

# 按合集
python query.py -C "上海三联" "卡里斯玛"

# 排除
python query.py -e "宗教社会学" "魔鬼"

# 组合
python query.py -c "韦伯著述" -C "上海三联" -s "支配社会学" "卡里斯玛权威"
```

### 查看可用来源

```bash
python query.py --list-sources               # 按合集分组列出所有书
python query.py --list-sources --show-all    # 含目录/附页
python query.py --list-categories            # 列出分类
```

### 交互模式

```bash
python query.py -i                    # 启动交互模式
python query.py -i -c "韦伯著述"      # 带初始过滤
```

交互模式支持 `/source`、`/exclude`、`/category`、`/new` 等命令。详见 [COMMANDS.md](COMMANDS.md)。

### 仅搜索模式

```bash
python query.py -S "理想类型"    # 只检索，跳过 LLM
```
Web 界面中勾选「仅搜索」开关即可。

### 调整检索深度

```bash
python query.py --top-sections 10 --top-chunks 15 "方法论"
```

## 数据管理

### 索引管理

```bash
python ingest.py                  # 增量索引（只处理新来源）
python ingest.py --stats          # 查看当前状态
python ingest.py --add SRC        # 重新索引指定来源
python ingest.py --delete SRC     # 删除指定来源
python ingest.py --force          # 清空重建
python ingest.py --repair         # 修复旧数据的 source_name 字段
```

### 可移植数据

向量库已预构建为分片文件（约 192MB，4 个分片），随 git 分发。新电脑无需运行 `ingest.py`。

**源机器导出**（每次更新向量库后）：

```bash
python export_data.py --split 50     # → data/weber_data.npz + 4 个 .part* 分片
git add data/weber_data.npz.part*
git commit -m "Update vector data"
git push
```

**新机器导入**（`setup` 自动调用）：

```bash
python import_data.py                # 从 .npz 或 .part* 分片重建 chroma_db
python import_data.py --force        # 覆盖已有数据
```

### 添加新著作

1. 将文件放入 `资料原档/` 对应目录
2. 在 `config.py` 的 `SOURCES` 列表添加条目（必填：`name`、`type`、`path`、`category`、`author`、`title`、`publisher`）
3. 运行 `python ingest.py`（增量索引，只处理新书）
4. 运行 `python export_data.py --split 50` 更新分片数据

## 来源列表

共 **29 个来源**，分 4 个分类。

### 韦伯著述（18 个）

| 书名 | 出版社 | 年份 |
|------|--------|------|
| 学术与政治 | 上海人民出版社 | 2021 |
| 新教伦理与资本主义精神 | 上海人民出版社 | 2019 |
| 罗雪尔与克尼斯：历史经济学的逻辑问题 | 上海人民出版社 | 2020 |
| 批判施塔姆勒 | 上海人民出版社 | 2020 |
| 韦伯政治著作选 | 上海人民出版社 | — |
| 社会科学方法论文集 | 上海人民出版社 | 2022 |
| 经济与社会 | 上海人民出版社 | 2020 |
| 学术与政治 | 上海三联书店 | 2010 |
| 新教伦理与资本主义精神 | 上海三联书店 | 2019 |
| 社会学的基本概念·经济行动与社会团体 | 上海三联书店 | 2020 |
| 支配社会学 | 上海三联书店 | 2020 |
| 经济与历史 支配的类型 | 上海三联书店 | 2021 |
| 法律社会学 非正当性的支配 | 上海三联书店 | 2021 |
| 宗教社会学 宗教与世界 | 上海三联书店 | — |
| 中国的宗教：儒教与道教 | 上海三联书店 | 2020 |
| 印度的宗教：印度教与佛教 | 上海三联书店 | 2020 |
| 古犹太教 | 上海三联书店 | 2021 |
| 民族国家与经济政策 | 生活·读书·新知三联书店 | 2018 |

### 传记与介绍（5 个）

| 书名 | 作者 | 出版社 |
|------|------|--------|
| 马克斯·韦伯的生平、著述及影响 | 克斯勒 | 法律出版社 |
| 马克斯·韦伯：跨越时代的人生 | 考伯 | 社会科学文献出版社 |
| 马克斯·韦伯与德国政治：1890—1920 | 蒙森 | 中信出版社 |
| 马克斯·韦伯思想肖像 | 本迪克斯 | — |
| Max Weber and His Contemporaries | Mommsen & Osterhammel | Routledge |

### 思想研究与讨论（5 个）

| 书名 | 作者 | 出版社 |
|------|------|--------|
| 科学作为天职：韦伯与我们时代的命运 | 韦伯 等 / 李猛 编 | 生活·读书·新知三联书店 |
| 难以驯化的利维坦 | 陈涛 | 生活·读书·新知三联书店 |
| Max Weber: From History to Modernity | Bryan S. Turner | Taylor & Francis |
| Max Weber and Karl Marx | Karl Löwith | Taylor & Francis |
| Natural Right and History | Leo Strauss | University of Chicago Press |

### 相关史料（1 个）

| 书名 | 出版社 |
|------|--------|
| 新编剑桥世界近代史（第 11–12 卷） | 中国社会科学出版社 |

### 书名模糊匹配

过滤参数（`-s`、`-e`、`-C`、`-E`）支持模糊匹配，解析优先级：

1. **精确匹配**（忽略大小写）
2. **子串匹配** — `"新教伦理"` → `新教伦理与资本主义精神`
3. **相似匹配**（difflib） — 列出最接近候选项
4. **歧义提示** — 匹配到多个时列出让你选

## 配置

`config.py` 中所有可调参数：

```python
# 检索
TOP_SECTIONS = 10        # Stage 1: 检索章节数
TOP_CHUNKS = 15          # Stage 2: 检索段落数

# 分块
CHUNK_SIZE = 512         # 每块中文字符数
CHUNK_OVERLAP = 128      # 相邻块重叠

# 嵌入
EMBEDDING_MODEL = "BAAI/bge-m3"
EMBEDDING_DIM = 1024
EMBEDDING_BATCH_SIZE = 3        # 8GB VRAM 安全值，更大显存可调高
EMBEDDING_DEVICE = None         # None=自动，"cpu"=强制 CPU

# LLM
LLM_MODEL = "deepseek-chat"
LLM_MAX_TOKENS = 8192
LLM_TEMPERATURE = 0.1
LLM_BASE_URL = "https://api.deepseek.com"
```

### 切换嵌入模型

```python
EMBEDDING_MODEL = "BAAI/bge-small-zh-v1.5"   # 更小（~400MB），仅中文
EMBEDDING_MODEL = "text-embedding-3-small"    # OpenAI（需 API Key）
```

切换模型后需 `python ingest.py --force` 重建索引。

## 硬件要求

| 资源 | 最低 | 推荐 |
|------|------|------|
| GPU | 无（CPU 可运行） | 8GB+ VRAM |
| 内存 | 8GB | 16GB |
| 磁盘 | ~3GB（模型 2GB + 向量库 ~200MB + 源文件 73MB） | — |

CPU 模式：在 `config.py` 设 `EMBEDDING_DEVICE = "cpu"`。

## 离线运行

模型首次下载需要联网，之后 Hugging Face 会直接复用本地缓存。需要强制断网运行时，可设置 `HF_HUB_OFFLINE=1`；调用 DeepSeek API 生成回答仍需网络。

## 在线使用

根目录已提供 GitHub Codespaces 配置。创建 Codespace 后会自动安装依赖、恢复索引、缓存模型并启动仅本人可访问的私有端口；`Dockerfile` 作为其他容器平台的可选方案保留。配置方式见项目根目录的 [README](../README.md)。

## 注意事项

- **出版社名使用全称**：`生活·读书·新知三联书店`（不是"三联"），`上海人民出版社`（不是"上人社"），`上海三联书店`（不是"三联"）
- **bge-m3 模型** ~2GB，首次运行自动下载
- **GPU VRAM**：`EMBEDDING_BATCH_SIZE=3` 约用 4.4GB（单进程）。不要同时跑两个 ingest 进程（两个模型实例 → OOM）
- **增量索引**：依赖 `source_name` 元数据判断已索引来源。旧数据缺失此字段时用 `--repair` 修复
- **Markdown 文件注意事项**：附录/TOC 类内容不要用 `##` 标题（markdown loader 会按 `##` 拆分段）。用 `**粗体**` 代替
- **终端中文乱码**：Windows GBK 终端 + Python UTF-8，命令前加 `export PYTHONIOENCODING=utf-8`
