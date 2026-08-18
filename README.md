---
title: Weber Knowledge Base
emoji: 📚
colorFrom: gray
colorTo: blue
sdk: gradio
app_file: weber-rag/serve.py
python_version: "3.12"
sdk_version: "6.15.0"
---

# Weber Knowledge Base

马克斯·韦伯著作、传记与研究文献的个人 RAG 知识库。支持浏览器问答、仅检索、来源筛选和多轮追问。

详细使用说明见 [weber-rag/README.md](weber-rag/README.md)。

## 在线部署

本项目由 GitHub Actions 自动同步到一个私有 Hugging Face Gradio Space。GitHub Pages 不能运行 Python 后端，因此 GitHub 负责版本管理、测试与部署，Space 提供固定的浏览器访问网址。根目录的 `Dockerfile` 保留用于其他容器平台，但 Hugging Face 免费部署不依赖 Docker。

在 GitHub 仓库的 `Settings → Secrets and variables → Actions` 中配置：

- `HF_TOKEN`：有仓库写权限的 Hugging Face User Access Token
- `HF_SPACE_ID`：例如 `your-name/weber-knowledge`
- `DEEPSEEK_API_KEY`：问答所需的 DeepSeek API Key

随后运行 `Deploy private Weber app` workflow。工作流会创建或更新私有 Space，并把 DeepSeek Key 写入 Space Secret；密钥不会进入代码或镜像。

## 本地启动

Windows 双击 `start_weber.bat`。首次安装请进入 `weber-rag` 后运行 `setup.bat`；macOS/Linux 使用 `bash setup.sh`。
