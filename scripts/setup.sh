#!/bin/bash
# Kotonoha Bot - セットアップスクリプト
# ホスト側のファイルとディレクトリの権限を自動設定

set -e

echo "Kotonoha Bot - Environment Setup Script"
echo "========================================"
echo ""

# 現在のディレクトリを取得
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

echo "Project root: $PROJECT_ROOT"
echo ""

# 成功した項目を追跡
SUCCESS_COUNT=0
TOTAL_COUNT=0

# データ保存用ディレクトリの作成
echo "Creating data directories..."
TOTAL_COUNT=$((TOTAL_COUNT + 1))
if mkdir -p data logs backups 2>/dev/null; then
    echo "[OK] Created directories: data/, logs/, backups/"
    SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
else
    echo "[ERROR] Failed to create directories"
fi
echo ""

# ファイルの権限設定
echo "Setting file permissions..."
TOTAL_COUNT=$((TOTAL_COUNT + 1))

# 設定ファイル（読み取り可能）
if chmod 644 docker-compose.yml Dockerfile pyproject.toml uv.lock README.md 2>/dev/null; then
    echo "[OK] Set permissions (644) for: docker-compose.yml, Dockerfile, pyproject.toml, uv.lock, README.md"
else
    echo "[WARN] Some configuration files not found (this is OK)"
fi

# .envファイル（機密情報を含むため、所有者のみ読み書き可能）
if [ -f .env ]; then
    if chmod 600 .env 2>/dev/null; then
        echo "[OK] Set permissions (600) for: .env (owner read/write only)"
    else
        echo "[WARN] Could not set permissions for .env"
    fi
else
    echo "[WARN] .env file not found (this is OK if you haven't created it yet)"
fi

# スクリプトの実行権限設定
if [ -d scripts ]; then
    if chmod +x scripts/*.sh 2>/dev/null; then
        echo "[OK] Set execution permissions for: scripts/*.sh"
    else
        echo "[WARN] Some scripts not found or could not set permissions"
fi
fi

SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
echo "[OK] File permissions configured"
echo ""

# ディレクトリの権限設定（オプション - 通常は不要）
# コンテナ起動時にentrypoint.shが自動的に修正します
echo "Directory permissions:"
echo "  - data/, logs/, backups/ will be automatically fixed by entrypoint.sh"
echo "  - No manual permission setting required for these directories"
echo ""

# 結果サマリー
echo "========================================"
if [ $SUCCESS_COUNT -eq $TOTAL_COUNT ]; then
    echo "Setup completed successfully! (All $SUCCESS_COUNT tasks completed)"
else
    echo "Setup completed with warnings. ($SUCCESS_COUNT/$TOTAL_COUNT tasks completed successfully)"
fi
echo ""
