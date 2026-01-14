# Kotonoha Discord Bot - Dockerfile
# Python 3.14 + uv による軽量イメージ

# ============================================
# ビルドステージ
# ============================================
FROM python:3.14-slim AS builder

WORKDIR /app

# システムパッケージの更新
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# uv のインストール
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# プロジェクトファイルのコピー（README.mdはpyproject.tomlのビルド時に必要）
COPY pyproject.toml uv.lock README.md ./
COPY src/ ./src/

# 依存関係のインストール（本番用のみ）
RUN uv sync --frozen --no-dev

# ============================================
# 実行ステージ
# ============================================
FROM python:3.14-slim AS runtime

WORKDIR /app

# 必要な実行時パッケージのみインストール
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# 非rootユーザーの作成（UID/GID 1000で明示的に作成）
RUN groupadd -r -g 1000 botuser && useradd -r -u 1000 -g botuser -d /app -s /sbin/nologin botuser

# ビルドステージから必要なファイルをコピー
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src

# バックアップスクリプトのコピー
COPY scripts/ /app/scripts/

# データディレクトリの作成と権限設定
RUN mkdir -p /app/data /app/logs /app/backups \
    && chmod +x /app/scripts/*.sh \
    && chown -R botuser:botuser /app

# 環境変数の設定
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# ユーザー切り替え
USER botuser

# ヘルスチェック用ポート（オプション）
EXPOSE 8080

# ヘルスチェック
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import sys; sys.exit(0)" || exit 1

# エントリーポイント
ENTRYPOINT ["/app/scripts/entrypoint.sh"]
