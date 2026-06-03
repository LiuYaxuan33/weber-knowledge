# Weber RAG 命令参考

## 一、快速开始

### 新电脑（git clone 后首次）

```bash
setup.bat            # Windows CMD，按提示输入 DeepSeek API Key
# 或
bash setup.sh        # Mac / Linux / Git Bash
```

`setup` 自动完成：检查 Python → 配置 `.env` → `pip install` → 从分片文件重建 ChromaDB。

### Web 界面（推荐日常使用）

```bash
python app.py                  # 浏览器打开 http://127.0.0.1:7860
python app.py --port 8080      # 自定义端口
```

界面功能：
- 聊天式问答，支持多轮追问
- 左侧栏：来源下拉筛选 + 分类筛选 + 「仅搜索」开关（跳过 LLM，不消耗 API）
- 输入 `/new` 重置对话

### 终端查询

```bash
python query.py "韦伯如何定义'理想类型'？"
python query.py -i                    # 交互模式（支持追问和 / 命令）
```

---

## 二、查询 (`python query.py`)

### 基本

```bash
python query.py "新教伦理与资本主义精神的关系"
```

### 过滤

```bash
# 按分类
python query.py -c "韦伯著述" "理想类型"
python query.py -c "传记与介绍" "韦伯生平"

# 按合集（模糊匹配）
python query.py -C "上海三联" "卡里斯玛"
python query.py -C "上海人民" "官僚制"

# 按书（模糊匹配）
python query.py -s "学术与政治" "Klarheit"
python query.py -s "新教伦理" "天职概念"

# 排除
python query.py -e "宗教社会学" "魔鬼"
python query.py -E "上海人民" "新教伦理"

# 组合
python query.py -c "韦伯著述" -C "上海三联" -s "支配社会学" "卡里斯玛"
```

### 信息查询

```bash
python query.py --list-sources             # 按合集分组列出所有书
python query.py --list-sources --show-all  # 含目录/附页
python query.py --list-categories          # 列出分类
```

### 检索模式

```bash
python query.py -S "理想类型"                       # 仅搜索，不调 LLM
python query.py --top-sections 10 --top-chunks 15 "方法论"   # 调整检索深度
```

---

## 三、交互模式 (`python query.py -i`)

```bash
python query.py -i                     # 无过滤
python query.py -i -c "韦伯著述"       # 带初始过滤
```

| 命令 | 说明 |
|------|------|
| `/source <书名>` `/s` | 限定到指定书（重置对话） |
| `/exclude <书名>` `/e` | 排除指定书（重置对话） |
| `/collection <合集>` `/col` | 限定到指定合集（重置对话） |
| `/exclude-collection <合集>` `/ecol` | 排除指定合集（重置对话） |
| `/category <分类>` `/c` | 按分类筛选（重置对话） |
| `/search` | 切换「仅搜索」/「搜索+问答」 |
| `/filters` | 查看当前过滤条件 |
| `/filter off` | 关闭所有过滤（重置对话） |
| `/new` `/clear` | 重置对话（保留过滤条件） |
| `quit` `exit` `q` | 退出 |

---

## 四、索引管理 (`python ingest.py`)

```bash
python ingest.py                  # 增量索引（只处理新来源）
python ingest.py --stats          # 查看统计
python ingest.py --add SRC        # 重新索引指定来源
python ingest.py --delete SRC     # 删除指定来源
python ingest.py --force          # 清空重建
python ingest.py --repair         # 修复旧数据缺失的 source_name
```

---

## 五、可移植数据

### 导出（源机器，每次更新向量库后）

```bash
python export_data.py --split 50    # → data/weber_data.npz + 4 个 .part* 分片
git add data/weber_data.npz.part*
git commit -m "Update vector data"
git push
```

### 导入（新机器，setup 自动调用）

```bash
python import_data.py               # 从 .npz 或 .part* 分片重建 chroma_db
python import_data.py --force       # 覆盖已有数据
python import_data.py --input /path/to/data.npz
```

数据量：~1,400 章节 + 43,000 段落，压缩后 ~189MB（4×50MB 分片）。

---

## 六、过滤规则

### 模糊匹配优先级

| 优先级 | 规则 | 示例 |
|--------|------|------|
| 1 | 精确匹配 | `"学术与政治"` → `学术与政治` |
| 2 | 子串匹配 | `"新教伦理"` → `新教伦理与资本主义精神` |
| 3 | 模糊匹配 | `"三联"` → `上海三联-学术与政治` 等多个候选项 |
| — | 歧义提示 | 列出所有匹配项让你选 |

### 过滤层次

```
分类 (韦伯著述 | 传记与介绍 | 相关史料 | 思想研究与讨论)
  └─ 合集 (source_name，如 "上海三联-学术与政治")
       └─ 书 (book 字段，如 "学术与政治")
            └─ 章节 → 段落
```

---

## 七、环境

| 文件 | 用途 |
|------|------|
| `.env` | DeepSeek API Key（`DEEPSEEK_API_KEY=sk-xxx`） |
| `config.py` | 模型、检索、分块参数 |
| `requirements.txt` | Python 依赖 |

关键配置项（`config.py`）：

```python
EMBEDDING_MODEL = "BAAI/bge-m3"      # 嵌入模型（~2GB，首次自动下载）
EMBEDDING_BATCH_SIZE = 3             # GPU VRAM 安全值（8GB），CPU 可调大
EMBEDDING_DEVICE = None              # None=自动，"cpu"=强制 CPU
LLM_MODEL = "deepseek-chat"          # LLM 模型
TOP_SECTIONS = 10                    # Stage 1 检索章节数
TOP_CHUNKS = 15                      # Stage 2 检索段落数
```
