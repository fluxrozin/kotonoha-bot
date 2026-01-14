#!/bin/bash
# Kotonoha Bot - データベースバックアップスクリプト
#
# 使用方法:
#   ./scripts/backup.sh
#   docker exec kotonoha-bot /app/scripts/backup.sh
#
# 環境変数:
#   BACKUP_DIR: バックアップ先ディレクトリ (デフォルト: /app/backups)
#   DATA_DIR: データディレクトリ (デフォルト: /app/data)
#   RETENTION_DAYS: バックアップ保持日数 (デフォルト: 7)

set -e

# 設定
BACKUP_DIR="${BACKUP_DIR:-/app/backups}"
DATA_DIR="${DATA_DIR:-/app/data}"
RETENTION_DAYS="${RETENTION_DAYS:-7}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/kotonoha_${TIMESTAMP}.db"

# バックアップディレクトリの作成
mkdir -p "${BACKUP_DIR}"

# データベースファイルの存在確認
DB_FILE="${DATA_DIR}/sessions.db"
if [ ! -f "${DB_FILE}" ]; then
    echo "Warning: Database file not found: ${DB_FILE}"
    exit 0
fi

# SQLite のバックアップ（オンラインバックアップ）
echo "Starting backup..."
sqlite3 "${DB_FILE}" ".backup '${BACKUP_FILE}'"

# バックアップファイルの圧縮
gzip -f "${BACKUP_FILE}"
BACKUP_FILE="${BACKUP_FILE}.gz"

# バックアップサイズの表示
BACKUP_SIZE=$(du -h "${BACKUP_FILE}" | cut -f1)
echo "Backup completed: ${BACKUP_FILE} (${BACKUP_SIZE})"

# 古いバックアップの削除
echo "Cleaning up old backups (older than ${RETENTION_DAYS} days)..."
find "${BACKUP_DIR}" -name "kotonoha_*.db.gz" -mtime +${RETENTION_DAYS} -delete

# 残っているバックアップの一覧表示
echo "Current backups:"
ls -lh "${BACKUP_DIR}"/kotonoha_*.db.gz 2>/dev/null || echo "  (none)"

echo "Backup process completed."
