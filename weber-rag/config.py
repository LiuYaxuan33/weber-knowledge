import os
from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WBER_RAG_DIR = os.path.dirname(os.path.abspath(__file__))
CHROMA_PERSIST_DIR = os.path.join(WBER_RAG_DIR, "data", "chroma_db")

# Chunking
CHUNK_SIZE = 512       # Chinese characters per chunk
CHUNK_OVERLAP = 128    # Overlap between adjacent chunks

# Embedding
EMBEDDING_MODEL = "BAAI/bge-m3"  # BGE flagship, multilingual, ~2GB
EMBEDDING_DIM = 1024   # bge-m3 outputs 1024-dim vectors
EMBEDDING_BATCH_SIZE = 3  # Lower = less VRAM; increase if you have >16GB GPU
EMBEDDING_DEVICE = None   # None = auto (GPU if available), "cpu" to force CPU

# Retrieval
TOP_SECTIONS = 4       # Number of top sections to retrieve in stage 1
TOP_CHUNKS = 6         # Number of top chunks to retrieve in stage 2

# LLM
LLM_MODEL = "deepseek-chat"
LLM_TEMPERATURE = 0.1
LLM_MAX_TOKENS = 2048
LLM_BASE_URL = "https://api.deepseek.com"
LLM_API_KEY_ENV = "DEEPSEEK_API_KEY"

# Source registry — add new books here
# Ordered small → large so quick wins finish first
SOURCES = [
    {
        "name": "民族国家与经济政策",
        "type": "epub",
        "path": os.path.join(PROJECT_ROOT, "马克斯·韦伯 - 2018 - 民族国家与经济政策：修订译本.epub"),
        "category": "韦伯著述",
        "edition": "生活·读书·新知三联书店",
    },
    {
        "name": "社会科学方法论文集",
        "type": "epub",
        "path": os.path.join(PROJECT_ROOT, "马克斯·韦伯 - 2022 - 社会科学方法论文集.epub"),
        "category": "韦伯著述",
        "edition": "上海人民出版社",
    },
    {
        "name": "克斯勒-韦伯生平著述及影响",
        "type": "markdown",
        "path": os.path.join(PROJECT_ROOT, "迪尔克·克斯勒 - 2004 - 马克斯·韦伯的生平、著述及影响/迪尔克·克斯勒 - 2004 - 马克斯·韦伯的生平、著述及影响.md"),
        "category": "传记与介绍",
        "edition": "法律出版社",
    },
    {
        "name": "三联-韦伯作品集",
        "type": "epub",
        "path": os.path.join(PROJECT_ROOT, "三联-韦伯作品集.epub"),
        "category": "韦伯著述",
        "edition": "生活·读书·新知三联书店",
    },
    {
        "name": "上人社-韦伯作品集",
        "type": "epub",
        "path": os.path.join(PROJECT_ROOT, "上人社-韦伯作品集.epub"),
        "category": "韦伯著述",
        "edition": "上海人民出版社",
    },
]

CATEGORIES = ["韦伯著述", "传记与介绍", "相关史料", "思想研究与讨论"]
