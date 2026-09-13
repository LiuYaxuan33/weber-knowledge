# Weber Knowledge Base

马克斯·韦伯著作、传记与研究文献的个人 RAG 知识库。支持浏览器问答、仅检索、来源筛选和多轮追问。

详细使用说明见 [weber-rag/README.md](weber-rag/README.md)。

## 公开在线使用（永久免费静态版）

打开 <https://liuyaxuan33.github.io/weber-knowledge/>。这是专门面向上海人民出版社、上海三联书店两套韦伯作品集的浏览器检索问答版：无需登录、没有服务器休眠。网页先在浏览器中定位原文，再通过 Cloudflare Worker 调用 DeepSeek；API Key 只保存在 Worker Secret 中。

静态网页位于 `docs/`，每次推送到 `master` 后由 `Deploy free static Weber search` workflow 自动发布。运行 `node scripts/build_static_search_index.mjs` 可从现有 NPZ 索引重新生成浏览器语料。

完整的向量检索与 DeepSeek 多轮问答仍可通过下面的 Codespaces 或本地版本使用。

## 开发预览（GitHub Codespaces）

项目包含 `.devcontainer` 配置。创建 Codespace 后会自动安装依赖、恢复 42,317 条向量、缓存 BGE-M3 模型并启动网页服务。

1. 在仓库 `Settings → Secrets and variables → Codespaces` 中添加 `DEEPSEEK_API_KEY`。
2. 在仓库点击 `Code → Codespaces → Create codespace on master`。
3. 首次创建需等待依赖和约 2 GB 模型下载；完成后会自动打开 `Weber Knowledge Base` 私有端口。

转发端口默认仅创建者可访问，并要求登录 GitHub。Codespace 默认闲置 30 分钟后停止；再次使用时前往 <https://github.com/codespaces> 启动原 Codespace，网址保持不变。

根目录的 `Dockerfile` 作为其他容器平台的可选方案保留。

## 本地启动

Windows 双击 `start_weber.bat`。首次安装请进入 `weber-rag` 后运行 `setup.bat`；macOS/Linux 使用 `bash setup.sh`。
