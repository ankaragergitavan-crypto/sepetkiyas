"""SepetKıyas'ı Hugging Face Spaces'e Docker Space olarak yayınlar."""

from __future__ import annotations

import shutil
from pathlib import Path

from huggingface_hub import HfApi, create_repo, whoami

ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / ".hf_space"


def main() -> None:
    info = whoami()
    user = info["name"]
    repo_id = f"{user}/sepetkiyas"
    print(f"Kullanıcı: {user}")
    print(f"Space: https://huggingface.co/spaces/{repo_id}")

    create_repo(repo_id, repo_type="space", space_sdk="docker", private=False, exist_ok=True)

    if STAGE.exists():
        shutil.rmtree(STAGE)
    STAGE.mkdir(parents=True)

    # Space Dockerfile — HF PORT=7860 kullanır
    (STAGE / "Dockerfile").write_text(
        "\n".join(
            [
                "FROM python:3.12-slim",
                "WORKDIR /app",
                "ENV PYTHONDONTWRITEBYTECODE=1",
                "ENV PYTHONUNBUFFERED=1",
                "COPY requirements.txt .",
                "RUN pip install --no-cache-dir -r requirements.txt",
                "COPY backend ./backend",
                "COPY frontend ./frontend",
                "EXPOSE 7860",
                'CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "7860"]',
                "",
            ]
        ),
        encoding="utf-8",
    )
    (STAGE / "README.md").write_text(
        "---\n"
        "title: SepetKiyas\n"
        "emoji: 🛒\n"
        "colorFrom: green\n"
        "colorTo: blue\n"
        "sdk: docker\n"
        "pinned: false\n"
        "app_port: 7860\n"
        "---\n\n"
        "# SepetKıyas\n\n"
        "Ankara market fiyat karşılaştırma (A101, Migros, Şok, BİM, Tarım Kredi, Getir).\n",
        encoding="utf-8",
    )
    shutil.copy2(ROOT / "requirements.txt", STAGE / "requirements.txt")
    shutil.copytree(ROOT / "backend", STAGE / "backend")
    shutil.copytree(ROOT / "frontend", STAGE / "frontend")

    api = HfApi()
    api.upload_folder(
        folder_path=str(STAGE),
        repo_id=repo_id,
        repo_type="space",
        commit_message="Deploy SepetKiyas",
    )
    print("Yüklendi.")
    print(f"Aç: https://huggingface.co/spaces/{repo_id}")
    print(f"Doğrudan uygulama (hazır olunca): https://{user.lower().replace('_', '-')}-sepetkiyas.hf.space")


if __name__ == "__main__":
    main()
