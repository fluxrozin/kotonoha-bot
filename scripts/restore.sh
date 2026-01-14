#!/bin/bash
# Kotonoha Bot - データベースリストアスクリプト
#
# 使用方法:
#   ./scripts/restore.sh [backup_file]
#   docker exec kotonoha-bot /app/scripts/restore.sh /app/backups/kotonoha_20260114_120000.db.gz
#
# 引数:
#   backup_file: リストアするバックアップファイル（.db.gz または .db）
#                指定しない場合は最新のバックアップを使用

set -e

# エラーハンドリング
trap 'echo "Error: Restore failed at line $LINENO"; exit 1' ERR

# 設定
BACKUP_DIR="${BACKUP_DIR:-/app/backups}"
DATA_DIR="${DATA_DIR:-/app/data}"
DATABASE_NAME="${DATABASE_NAME:-sessions.db}"
DB_FILE="${DATA_DIR}/${DATABASE_NAME}"

# バックアップファイルの指定
if [ -n "$1" ]; then
    BACKUP_FILE="$1"
else
    # 最新のバックアップを検索
    BACKUP_FILE=$(ls -t "${BACKUP_DIR}"/kotonoha_*.db.gz 2>/dev/null | head -1)
    if [ -z "${BACKUP_FILE}" ]; then
        echo "Error: No backup files found in ${BACKUP_DIR}"
        exit 1
    fi
fi

# バックアップファイルの存在確認
if [ ! -f "${BACKUP_FILE}" ]; then
    echo "Error: Backup file not found: ${BACKUP_FILE}"
    exit 1
fi

echo "Restoring from: ${BACKUP_FILE}"

# ボット停止確認の警告
echo ""
echo "WARNING: Restoring while the bot is running may cause data corruption."
echo "Please ensure the bot is stopped before proceeding."
echo ""
read -p "Continue with restore? (y/N): " -r CONFIRM
if [[ ! "$CONFIRM" =~ ^[Yy]$ ]]; then
    echo "Restore cancelled."
    exit 0
fi

# データディレクトリの作成
mkdir -p "${DATA_DIR}"

# 既存のデータベースをバックアップ（存在する場合）
if [ -f "${DB_FILE}" ]; then
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    DB_BASENAME=$(basename "${DATABASE_NAME}" .db)
    CURRENT_BACKUP="${DATA_DIR}/${DB_BASENAME}_before_restore_${TIMESTAMP}.db"
    echo "Backing up current database to: ${CURRENT_BACKUP}"
    cp "${DB_FILE}" "${CURRENT_BACKUP}"
fi

# リストア
if [[ "${BACKUP_FILE}" == *.gz ]]; then
    echo "Decompressing and restoring..."
    gunzip -c "${BACKUP_FILE}" > "${DB_FILE}"
else
    echo "Restoring..."
    cp "${BACKUP_FILE}" "${DB_FILE}"
fi

# 整合性チェック
echo "Checking database integrity..."
INTEGRITY=$(sqlite3 "${DB_FILE}" "PRAGMA integrity_check;")
if [ "${INTEGRITY}" = "ok" ]; then
    echo "Database integrity check: OK"
else
    echo "Warning: Database integrity check failed: ${INTEGRITY}"
fi

echo "Restore completed successfully."
echo "Please restart the bot to apply changes."
