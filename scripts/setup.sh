#!/bin/bash
# Kotonoha Bot - セットアップスクリプト
# ホスト側のファイルとディレクトリの権限を自動設定

set -e

echo "Kotonoha Bot - Setup script"
echo "============================"
echo ""

# 現在のディレクトリを取得
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

echo "Project root: $PROJECT_ROOT"
echo ""

# データ保存用ディレクトリの作成
echo "Creating data directories..."
mkdir -p data logs backups
echo "✓ Directories created"
echo ""

# ファイルの権限設定
echo "Setting file permissions..."

# 設定ファイル（読み取り可能）
chmod 644 docker-compose.yml Dockerfile pyproject.toml uv.lock README.md 2>/dev/null || true

# .envファイル（機密情報を含むため、所有者のみ読み書き可能）
if [ -f .env ]; then
    chmod 600 .env
    echo "✓ .env file permissions set to 600 (owner read/write only)"
else
    echo "⚠ .env file not found (this is OK if you haven't created it yet)"
fi

# スクリプトの実行権限設定
if [ -d scripts ]; then
    chmod +x scripts/*.sh 2>/dev/null || true
    echo "✓ Script execution permissions set"
fi

echo "✓ File permissions configured"
echo ""

# ディレクトリの権限設定（オプション - 通常は不要）
# コンテナ起動時にentrypoint.shが自動的に修正します
echo "Directory permissions:"
echo "  - data/, logs/, backups/ will be automatically fixed by entrypoint.sh"
echo "  - No manual permission setting required for these directories"
echo ""

echo "Setup completed successfully!"
echo ""
echo "Next steps:"
echo "  1. Create .env file from .env.example if you haven't already:"
echo "     cp .env.example .env"
echo "  2. Edit .env file with your actual values"
echo "  3. Run: docker compose up -d"
echo ""
