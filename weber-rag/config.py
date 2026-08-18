import os
from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEBER_RAG_DIR = os.path.dirname(os.path.abspath(__file__))
CHROMA_PERSIST_DIR = os.path.join(WEBER_RAG_DIR, "data", "chroma_db")
INDEX_MANIFEST_PATH = os.path.join(WEBER_RAG_DIR, "data", "index_manifest.json")
INDEX_SCHEMA_VERSION = 2

# Chunking
CHUNK_SIZE = 512       # Chinese characters per chunk
CHUNK_OVERLAP = 128    # Overlap between adjacent chunks

# Embedding
EMBEDDING_MODEL = "BAAI/bge-m3"  # BGE flagship, multilingual, ~2GB
EMBEDDING_DIM = 1024   # bge-m3 outputs 1024-dim vectors
EMBEDDING_BATCH_SIZE = 3  # Lower = less VRAM; increase if you have >16GB GPU
EMBEDDING_DEVICE = None   # None = auto (GPU if available), "cpu" to force CPU
HF_HUB_OFFLINE = os.environ.get("HF_HUB_OFFLINE", "").lower() in {"1", "true", "yes"}

# Retrieval
TOP_SECTIONS = 10      # Number of top sections to retrieve in stage 1
TOP_CHUNKS = 15        # Number of top chunks to retrieve in stage 2
DIVERSITY_BONUS = 0.15 # Score boost for the first chunk from each book
CROSS_LANG_BONUS = 0.10 # Score boost for chunks in a different language

# LLM
LLM_MODEL = "deepseek-chat"
LLM_TEMPERATURE = 0.1
LLM_MAX_TOKENS = 8192
LLM_BASE_URL = "https://api.deepseek.com"
LLM_API_KEY_ENV = "DEEPSEEK_API_KEY"
LLM_CONTEXT_TOKEN_BUDGET = 28_000
LLM_HISTORY_TOKEN_BUDGET = 12_000

# Source registry
# Ordered small → large so quick wins finish first.
#
# Required fields per entry:
#   name     — unique identifier (used in --add / --delete)
#   type     — "epub" or "markdown"
#   path     — absolute or PROJECT_ROOT-relative path
#   category — must be one of CATEGORIES
#   author   — author(s) in standard citation form
#   title    — book title
#   publisher— publisher name
#   year     — publication year (int)
#   translator — (optional) translator name
#   isbn     — (optional) ISBN
SOURCES = [
    # ================================================================
    # 韦伯著述 · 上海人民出版社
    # ================================================================
    {
        "name": "上海人民-学术与政治",
        "type": "epub",
        "path": os.path.join(PROJECT_ROOT, "资料原档", "著述", "上海人民出版社-韦伯作品集",
                             "学术与政治 (马克斯·韦伯) (z-library.sk, 1lib.sk, z-lib.sk).epub"),
        "category": "韦伯著述",
        "author": "[德]马克斯·韦伯",
        "title": "学术与政治",
        "publisher": "上海人民出版社",
        "year": 2021,
    },
    {
        "name": "上海人民-新教伦理与资本主义精神",
        "type": "epub",
        "path": os.path.join(PROJECT_ROOT, "资料原档", "著述", "上海人民出版社-韦伯作品集",
                             "新教伦理与资本主义精神 (（德）马克斯·韦伯（Max Weber）) (z-library.sk, 1lib.sk, z-lib.sk).epub"),
        "category": "韦伯著述",
        "author": "[德]马克斯·韦伯",
        "title": "新教伦理与资本主义精神",
        "publisher": "上海人民出版社",
        "year": 2019,
    },
    {
        "name": "上海人民-罗雪尔与克尼斯",
        "type": "epub",
        "path": os.path.join(PROJECT_ROOT, "资料原档", "著述", "上海人民出版社-韦伯作品集",
                             "罗雪尔与克尼斯 - 历史经济学的逻辑问题 -- 韦伯 Weber, Max 1864-1920 -- Di 1 ban, Shanghai, 2020 -- 上海：上海人民出版社 -- isbn13 9787208161856 -- c06858327033e428e7f22f0cbbcb1018 -- Anna’s Archive.epub"),
        "category": "韦伯著述",
        "author": "[德]马克斯·韦伯",
        "title": "罗雪尔与克尼斯：历史经济学的逻辑问题",
        "publisher": "上海人民出版社",
        "year": 2020,
        "translator": "李荣山",
    },
    {
        "name": "上海人民-批判施塔姆勒",
        "type": "epub",
        "path": os.path.join(PROJECT_ROOT, "资料原档", "著述", "上海人民出版社-韦伯作品集",
                             "批判施塔姆勒 -- 韦伯 Weber, Max 1864-1920 -- Di 1 ban, Shanghai, 2020 -- 上海：上海人民出版社 -- isbn13 9787208161863 -- bd6f173baf25b50828433f5cf2114a86 -- Anna’s Archive.epub"),
        "category": "韦伯著述",
        "author": "[德]马克斯·韦伯",
        "title": "批判施塔姆勒",
        "publisher": "上海人民出版社",
        "year": 2020,
        "translator": "李荣山",
    },
    {
        "name": "上海人民-韦伯政治著作选",
        "type": "epub",
        "path": os.path.join(PROJECT_ROOT, "资料原档", "著述", "上海人民出版社-韦伯作品集",
                             "韦伯政治著作选 -- 【德】马克斯·韦伯 -- 上海人民出版社 -- 02bab94afad8948a31b68b48929dcbfa -- Anna’s Archive.epub"),
        "category": "韦伯著述",
        "author": "[德]马克斯·韦伯",
        "title": "韦伯政治著作选",
        "publisher": "上海人民出版社",
        "year": None,
    },
    {
        "name": "上海人民-社会科学方法论文集",
        "type": "epub",
        "path": os.path.join(PROJECT_ROOT, "资料原档", "著述", "上海人民出版社-韦伯作品集",
                             "马克斯·韦伯 - 2022 - 社会科学方法论文集.epub"),
        "category": "韦伯著述",
        "author": "[德]马克斯·韦伯",
        "title": "社会科学方法论文集",
        "publisher": "上海人民出版社",
        "year": 2022,
        "translator": "阎克文, 姚燕",
    },
    {
        "name": "上海人民-经济与社会",
        "type": "epub",
        "path": os.path.join(PROJECT_ROOT, "资料原档", "著述", "上海人民出版社-韦伯作品集",
                             "经济与社会 (Max Weber) (Z-Library).epub"),
        "category": "韦伯著述",
        "author": "[德]马克斯·韦伯",
        "title": "经济与社会",
        "publisher": "上海人民出版社",
        "year": 2020,
    },
    # ================================================================
    # 韦伯著述 · 上海三联书店（理想国）
    # ================================================================
    {
        "name": "上海三联-学术与政治",
        "type": "epub",
        "path": os.path.join(PROJECT_ROOT, "资料原档", "著述", "上海三联书店-韦伯作品集",
                             "学术与政治 (马克斯·韦伯, Max Weber) (z-library.sk, 1lib.sk, z-lib.sk).epub"),
        "category": "韦伯著述",
        "author": "[德]马克斯·韦伯",
        "title": "学术与政治",
        "publisher": "上海三联书店",
        "year": 2010,
    },
    {
        "name": "上海三联-新教伦理与资本主义精神",
        "type": "epub",
        "path": os.path.join(PROJECT_ROOT, "资料原档", "著述", "上海三联书店-韦伯作品集",
                             "新教伦理与资本主义精神 (马克斯·韦伯) (z-library.sk, 1lib.sk, z-lib.sk).epub"),
        "category": "韦伯著述",
        "author": "[德]马克斯·韦伯",
        "title": "新教伦理与资本主义精神",
        "publisher": "上海三联书店",
        "year": 2019,
    },
    {
        "name": "上海三联-社会学的基本概念",
        "type": "epub",
        "path": os.path.join(PROJECT_ROOT, "资料原档", "著述", "上海三联书店-韦伯作品集",
                             "社会学的基本概念·经济行动与社会团体 (马克斯·韦伯) (z-library.sk, 1lib.sk, z-lib.sk).epub"),
        "category": "韦伯著述",
        "author": "[德]马克斯·韦伯",
        "title": "社会学的基本概念·经济行动与社会团体",
        "publisher": "上海三联书店",
        "year": 2020,
    },
    {
        "name": "上海三联-支配社会学",
        "type": "epub",
        "path": os.path.join(PROJECT_ROOT, "资料原档", "著述", "上海三联书店-韦伯作品集",
                             "支配社会学 (马克斯·韦伯) (z-library.sk, 1lib.sk, z-lib.sk).epub"),
        "category": "韦伯著述",
        "author": "[德]马克斯·韦伯",
        "title": "支配社会学",
        "publisher": "上海三联书店",
        "year": 2020,
    },
    {
        "name": "上海三联-经济与历史",
        "type": "epub",
        "path": os.path.join(PROJECT_ROOT, "资料原档", "著述", "上海三联书店-韦伯作品集",
                             "经济与历史 支配的类型 -- [德] 马克斯·韦伯 -- 上海三联书店·理想国 -- 9142555e5de0d7b943e4d4def39852c5 -- Anna’s Archive.epub"),
        "category": "韦伯著述",
        "author": "[德]马克斯·韦伯",
        "title": "经济与历史 支配的类型",
        "publisher": "上海三联书店",
        "year": 2021,
    },
    {
        "name": "上海三联-法律社会学",
        "type": "epub",
        "path": os.path.join(PROJECT_ROOT, "资料原档", "著述", "上海三联书店-韦伯作品集",
                             "法律社会学 非正当性的支配 -- 【德】马克斯·韦伯 -- 2021 -- 上海三联书店·理想国 -- 04c68b8f187c19f9f8957177521f5d1a -- Anna’s Archive.epub"),
        "category": "韦伯著述",
        "author": "[德]马克斯·韦伯",
        "title": "法律社会学 非正当性的支配",
        "publisher": "上海三联书店",
        "year": 2021,
    },
    {
        "name": "上海三联-宗教社会学",
        "type": "epub",
        "path": os.path.join(PROJECT_ROOT, "资料原档", "著述", "上海三联书店-韦伯作品集",
                             "宗教社会学 宗教与世界 (（德）马克斯·韦伯著；康乐，简惠美译) (z-library.sk, 1lib.sk, z-lib.sk).epub"),
        "category": "韦伯著述",
        "author": "[德]马克斯·韦伯",
        "title": "宗教社会学 宗教与世界",
        "publisher": "上海三联书店",
        "year": None,
        "translator": "康乐, 简惠美",
    },
    {
        "name": "上海三联-中国的宗教",
        "type": "epub",
        "path": os.path.join(PROJECT_ROOT, "资料原档", "著述", "上海三联书店-韦伯作品集",
                             "中国的宗教：儒教与道教 (马克斯·韦伯) (z-library.sk, 1lib.sk, z-lib.sk).epub"),
        "category": "韦伯著述",
        "author": "[德]马克斯·韦伯",
        "title": "中国的宗教：儒教与道教",
        "publisher": "上海三联书店",
        "year": 2020,
    },
    {
        "name": "上海三联-印度的宗教",
        "type": "epub",
        "path": os.path.join(PROJECT_ROOT, "资料原档", "著述", "上海三联书店-韦伯作品集",
                             "印度的宗教：印度教与佛教 (马克斯·韦伯) (z-library.sk, 1lib.sk, z-lib.sk).epub"),
        "category": "韦伯著述",
        "author": "[德]马克斯·韦伯",
        "title": "印度的宗教：印度教与佛教",
        "publisher": "上海三联书店",
        "year": 2020,
    },
    {
        "name": "上海三联-古犹太教",
        "type": "epub",
        "path": os.path.join(PROJECT_ROOT, "资料原档", "著述", "上海三联书店-韦伯作品集",
                             "古犹太教 (现代社会学主要奠基人马克斯•韦伯，三大宗教鸿篇巨制之一 理想国出品） (马克斯•韦伯) (z-library.sk, 1lib.sk, z-lib.sk).epub"),
        "category": "韦伯著述",
        "author": "[德]马克斯·韦伯",
        "title": "古犹太教",
        "publisher": "上海三联书店",
        "year": 2021,
    },
    # ================================================================
    # 韦伯著述 · 生活·读书·新知三联书店
    # ================================================================
    {
        "name": "三联-民族国家与经济政策",
        "type": "epub",
        "path": os.path.join(PROJECT_ROOT, "资料原档", "著述",
                             "马克斯·韦伯 - 2018 - 民族国家与经济政策：修订译本.epub"),
        "category": "韦伯著述",
        "author": "[德]马克斯·韦伯",
        "title": "民族国家与经济政策",
        "publisher": "生活·读书·新知三联书店",
        "year": 2018,
    },
    # ================================================================
    # 传记与介绍
    # ================================================================
    {
        "name": "克斯勒-韦伯生平著述及影响",
        "type": "markdown",
        "path": os.path.join(PROJECT_ROOT, "资料原档", "传记与介绍",
                             "迪尔克·克斯勒 - 2004 - 马克斯·韦伯的生平、著述及影响",
                             "迪尔克·克斯勒 - 2004 - 马克斯·韦伯的生平、著述及影响.md"),
        "category": "传记与介绍",
        "author": "[德]迪尔克·克斯勒",
        "title": "马克斯·韦伯的生平、著述及影响",
        "publisher": "法律出版社",
        "year": 2000,
        "translator": "郭锋",
    },
    {
        "name": "考伯-跨越时代的人生",
        "type": "epub",
        "path": os.path.join(PROJECT_ROOT, "资料原档", "传记与介绍",
                             "马克斯·韦伯-跨越时代的人生 -- [[德]于尔根·考伯(Jürgen Kaube)] -- 2020 -- 社会科学文献出版社 -- 307efb2d83d66647b46e3fac13fbf1de -- Anna’s Archive.epub"),
        "category": "传记与介绍",
        "author": "[德]于尔根·考伯",
        "title": "马克斯·韦伯：跨越时代的人生",
        "publisher": "社会科学文献出版社",
        "year": 2020,
    },
    {
        "name": "蒙森-韦伯与德国政治",
        "type": "markdown",
        "path": os.path.join(PROJECT_ROOT, "资料原档", "传记与介绍",
                             "沃尔夫冈·J. 蒙森 - 2016 - 马克斯·韦伯与德国政治：1890—1920",
                             "马克斯·韦伯与德国政治：1890—1920.md"),
        "category": "传记与介绍",
        "author": "[德]沃尔夫冈·J. 蒙森",
        "title": "马克斯·韦伯与德国政治：1890—1920",
        "publisher": "中信出版社",
        "year": 2016,
        "translator": "阎克文",
        "isbn": "978-7-5086-6448-4",
    },
    {
        "name": "本迪克斯-韦伯思想肖像",
        "type": "epub",
        "path": os.path.join(PROJECT_ROOT, "资料原档", "传记与介绍",
                             "马克斯·韦伯思想肖像 -- 莱因哈特·本迪克斯 [莱因哈特·本迪克斯] -- 2019 -- 4189ba0ef561474b1fe4ddbb2193ee1b -- Anna’s Archive.epub"),
        "category": "传记与介绍",
        "author": "[美]莱因哈特·本迪克斯",
        "title": "马克斯·韦伯思想肖像",
        "publisher": None,
        "year": 2019,
    },
    {
        "name": "Max Weber and His Contemporaries",
        "type": "epub",
        "path": os.path.join(PROJECT_ROOT, "资料原档", "传记与介绍",
                             "Max Weber and his Contemporaries -- Wolfgang J_ Mommsen & Jürgen Osterhammel -- 2022 -- Routledge -- isbn13 9780203708644 -- 8cc8777f908c211c85acf92f7a7f1c53 -- Anna’s Archive.epub"),
        "category": "传记与介绍",
        "author": "Wolfgang J. Mommsen, Jürgen Osterhammel",
        "title": "Max Weber and His Contemporaries",
        "publisher": "Routledge",
        "year": 2022,
        "isbn": "9780203708644",
    },
    # ================================================================
    # 思想研究与讨论
    # ================================================================
    {
        "name": "科学作为天职",
        "type": "epub",
        "path": os.path.join(PROJECT_ROOT, "资料原档", "思想研究与讨论",
                             "科学作为天职 - 韦伯与我们时代的命运 = Wissenschaft als Beruf -- (德)马克斯·韦伯等著 ; 李猛编; 韦伯; 李猛 -- 1st, 2018 -- 北京：生活·读书·新知三联书店 -- isbn13 9787108063151 -- 686ac2f701bab7657d30df….epub"),
        "category": "思想研究与讨论",
        "author": "[德]马克斯·韦伯 等",
        "title": "科学作为天职：韦伯与我们时代的命运",
        "publisher": "生活·读书·新知三联书店",
        "year": 2018,
        "translator": "李猛 编",
        "isbn": "9787108063151",
    },
    {
        "name": "Max Weber: From History to Modernity",
        "type": "epub",
        "path": os.path.join(PROJECT_ROOT, "资料原档", "思想研究与讨论",
                             "Max Weber - from history to modernity -- Profesor Bryan S_ Turner -- 1, 20020911 -- Taylor & Francis Group -- isbn13 9780044459354 -- 209e7429fba591f0c635cca5c4217183 -- Anna’s Archive.epub"),
        "category": "思想研究与讨论",
        "author": "Bryan S. Turner",
        "title": "Max Weber: From History to Modernity",
        "publisher": "Taylor & Francis",
        "year": 2011,
        "isbn": "9780044459354",
    },
    {
        "name": "Max Weber and Karl Marx",
        "type": "epub",
        "path": os.path.join(PROJECT_ROOT, "资料原档", "思想研究与讨论",
                             "Max Weber and Karl Marx -- L̈owith, Karl -- 1, 20021101 -- Taylor & Francis (CAM) -- isbn13 9780203422229 -- ca3c5a6417d100a0c3cde2689f8a90d2 -- Anna’s Archive.epub"),
        "category": "思想研究与讨论",
        "author": "Karl Löwith",
        "title": "Max Weber and Karl Marx",
        "publisher": "Taylor & Francis",
        "year": 2011,
        "isbn": "9780203422229",
    },
    {
        "name": "Natural Right and History",
        "type": "epub",
        "path": os.path.join(PROJECT_ROOT, "资料原档", "思想研究与讨论",
                             "natural right and history.epub"),
        "category": "思想研究与讨论",
        "author": "Leo Strauss",
        "title": "Natural Right and History",
        "publisher": "University of Chicago Press",
        "year": 2013,
    },
    {
        "name": "陈涛-难以驯化的利维坦",
        "type": "markdown",
        "path": os.path.join(PROJECT_ROOT, "资料原档", "思想研究与讨论",
                             "难以驯化的利维坦_陈涛_2026",
                             "难以驯化的利维坦.md"),
        "category": "思想研究与讨论",
        "author": "陈涛",
        "title": '难以驯化的利维坦：基于韦伯“国家社会学”的研究',
        "publisher": "生活·读书·新知三联书店",
        "year": 2026,
    },
    # ================================================================
    # 相关史料
    # ================================================================
    {
        "name": "新编剑桥世界近代史",
        "type": "epub",
        "path": os.path.join(PROJECT_ROOT, "资料原档", "史料",
                             "新编剑桥世界近代史-第11、12卷.epub"),
        "category": "相关史料",
        "author": "[英]G.R.波特 编",
        "title": "新编剑桥世界近代史（第11–12卷）",
        "publisher": "中国社会科学出版社",
        "year": 2018,
    },
]

CATEGORIES = ["韦伯著述", "传记与介绍", "相关史料", "思想研究与讨论"]
