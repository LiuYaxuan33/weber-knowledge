"""Synchronize this checkout to a public, free Hugging Face Gradio Space."""

from __future__ import annotations

import os

from huggingface_hub import HfApi


def required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required GitHub Actions secret: {name}")
    return value


def main() -> None:
    token = required_env("HF_TOKEN")
    repo_id = required_env("HF_SPACE_ID")
    deepseek_key = required_env("DEEPSEEK_API_KEY")
    api = HfApi(token=token)

    api.create_repo(
        repo_id=repo_id,
        repo_type="space",
        space_sdk="gradio",
        private=False,
        exist_ok=True,
    )
    api.update_repo_settings(
        repo_id=repo_id,
        repo_type="space",
        visibility="public",
    )
    api.add_space_secret(
        repo_id=repo_id,
        key="DEEPSEEK_API_KEY",
        value=deepseek_key,
    )
    api.upload_folder(
        repo_id=repo_id,
        repo_type="space",
        folder_path=".",
        commit_message=os.environ.get("GITHUB_SHA", "GitHub deployment"),
        ignore_patterns=[
            ".git/**",
            ".github/**",
            ".devcontainer/**",
            ".claude/**",
            "tests/**",
            "scripts/**",
            "资料原档/**",
            "**/__pycache__/**",
            "**/.venv/**",
            "weber-rag/.env",
            "weber-rag/data/chroma_db/**",
        ],
        delete_patterns="*",
    )
    print(f"Deployed public Space: https://huggingface.co/spaces/{repo_id}")


if __name__ == "__main__":
    main()
