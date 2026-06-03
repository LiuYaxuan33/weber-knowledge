# Weber RAG 命令参考

## 一、查询 (`python query.py`)

### 基本

```bash
python query.py "韦伯如何定义'理想类型'？"
python query.py "新教伦理与资本主义精神的关系"
```

### 过滤

```bash
# ── 按分类 ──
python query.py -c "韦伯著述" "理想类型"
python query.py -c "传记与介绍" "韦伯生平"

# ── 按合集（父来源） ──
python query.py -C "三联-韦伯作品集" "卡里斯玛"
python query.py -C "上人社" "官僚制"
python query.py -C "社会科学方法论文集" "价值无涉"

# ── 按书 ──
python query.py -s "学术与政治" "Klarheit"
python query.py -s "新教伦理" "天职概念"

# ── 排除 ──
python query.py -e "宗教社会学" "魔鬼"
python query.py -E "上人社-韦伯作品集" "新教伦理"

# ── 组合 ──
python query.py -C "三联" -s "支配社会学" "卡里斯玛权威"
python query.py -c "韦伯著述" -E "经济与社会" -e "学术与政治" "支配概念"
```

### 信息查询

```bash
python query.py --list-sources            # 按合集分组列出所有书（过滤前后附页）
python query.py --list-sources --show-all # 同上，含目录/译者说明等附页
python query.py --list-categories         # 列出分类和索引统计
```

### 调整检索范围

```bash
python query.py --top-sections 10 --top-chunks 15 "方法论"
```

---

## 二、交互模式 (`python query.py -i`)

### 启动

```bash
python query.py -i                          # 无过滤
python query.py -i -C "三联"                # 带初始过滤
python query.py -i -c "韦伯著述" -e "宗教社会学"
```

启动后显示当前过滤条件和可用命令。

### 会话内命令

| 命令 | 说明 |
|------|------|
| `/source <书名>` `/s` | 限定到指定书（模糊匹配，切换时重置对话） |
| `/exclude <书名>` `/e` | 排除指定书（模糊匹配，切换时重置对话） |
| `/collection <合集>` `/col` | 限定到指定合集（模糊匹配，切换时重置对话） |
| `/exclude-collection <合集>` `/ecol` | 排除指定合集（模糊匹配，切换时重置对话） |
| `/category <分类>` `/c` | 按分类筛选（切换时重置对话） |
| `/filters` | 查看当前过滤条件 |
| `/filter off` | 关闭所有过滤（重置对话） |
| `/new` | 重置对话历史（保留过滤条件） |
| `quit` / `exit` / `q` | 退出 |
| `<直接输入问题>` | 提交查询 |

---

## 三、索引管理 (`python ingest.py`)

```bash
python ingest.py                  # 增量索引（只处理新来源）
python ingest.py --stats          # 查看索引统计
python ingest.py --add SRC_NAME   # 重新索引指定来源
python ingest.py --delete SRC_NAME# 删除指定来源
python ingest.py --force          # 清空重建全部索引
python ingest.py --repair         # 修复旧数据缺失的 source_name 字段
```

---

## 四、过滤规则速查

### 模糊匹配（`--source` / `--exclude` / `--collection`）

输入可以是全名或部分名，按优先级自动解析：

| 优先级 | 规则 | 示例 |
|--------|------|------|
| 1 | 精确匹配 | `"学术与政治"` → `学术与政治` |
| 2 | 子串匹配 | `"新教伦理"` → `新教伦理与资本主义精神` |
| 3 | 模糊匹配 | `"三联"` → `三联-韦伯作品集` |
| — | 歧义提示 | `"社会学"` → 列出 5 个匹配项，让你选 |

### 过滤层次

```
分类 (category)
  └─ 合集 (collection / source_name)
       └─ 书 (source / book)
            └─ 章节 → 段落
```

- `--category`/`-c`：按 `韦伯著述` | `传记与介绍` | `相关史料` | `思想研究与讨论`
- `--collection`/`-C`：按合集名（对应 `source_name` 字段）→ `python query.py --list-sources` 查看
- `--source`/`-s`：按书名（对应 `book` 字段）→ `python query.py --list-sources` 查看
- `--exclude`/`-e`：排除书，`--exclude-collection`/`-E`：排除合集

### 当前收录来源

| 合集 | 出版社 | 书数 |
|------|--------|------|
| 三联-韦伯作品集 | 生活·读书·新知三联书店 | 9 |
| 上人社-韦伯作品集 | 上海人民出版社 | 5 |
| 克斯勒-韦伯生平著述及影响 | 法律出版社 | 1 |
| 民族国家与经济政策 | 生活·读书·新知三联书店 | 5 |
| 社会科学方法论文集 | 上海人民出版社 | 7 |

---

## 五、环境

```bash
# 安装
pip install -r weber-rag/requirements.txt

# 配置
cp weber-rag/.env.template weber-rag/.env
# 编辑 .env：DEEPSEEK_API_KEY=sk-xxx

# 首次索引（下载模型约 2GB + 索引全部著作）
cd weber-rag && python ingest.py
```
