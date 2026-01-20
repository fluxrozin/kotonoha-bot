# Kotonoha Discord Bot - Dockerfile
# Multi-stage build for minimal image size
#
# Phase 10 リファクタリング完了版
# - 新しいフォルダ構造に対応
# - Pydantic V2 ベースの設定管理
# - 依存性注入パターンに対応

# ============================================
# ビルドステージ: 依存関係のインストール
# ============================================
FROM python:3.14-slim AS builder

WORKDIR /app

# ビルドに必要なパッケージをインストール
RUN apt update && apt install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# uv パッケージマネージャーをインストール
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# プロジェクトファイルをコピー
COPY pyproject.toml uv.lock README.md ./
COPY src/ ./src/
# Phase 10: 新しいフォルダ構造（src/kotonoha_bot/）に対応
# prompts/ は src/kotonoha_bot/prompts/ に含まれているため、src/ のコピーで十分

# 依存関係をインストール（本番用のみ）
RUN uv sync --frozen --no-dev

# ============================================
# 実行ステージ: 最小限のランタイム環境
# ============================================
FROM python:3.14-slim AS runtime

WORKDIR /app

# 実行時に必要なパッケージをインストール
RUN apt update && apt install -y --no-install-recommends \
    ca-certificates \
    sqlite3 \
    gosu \
    gzip \
    tzdata \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# 非rootユーザーを作成（UID/GID 1000）
RUN groupadd -r -g 1000 botuser && \
    useradd -r -u 1000 -g botuser -d /app -s /sbin/nologin botuser

# ビルドステージからアプリケーションと依存関係をコピー
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src
# prompts/ は src/kotonoha_bot/prompts/ に含まれているため、src/ のコピーで十分
COPY scripts/ /app/scripts/
COPY alembic.ini /app/alembic.ini
COPY alembic/ /app/alembic/

# スクリプトに実行権限を付与
RUN chmod +x /app/scripts/*.sh

# 環境変数を設定
# Phase 10: PYTHONPATH は src/ を指す（kotonoha_bot パッケージのルート）
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH=/app/src \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TZ=Asia/Tokyo

# エントリーポイント（パーミッション修正後に botuser でアプリケーションを起動）
ENTRYPOINT ["/app/scripts/entrypoint.sh"]
