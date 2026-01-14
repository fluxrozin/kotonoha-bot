#!/bin/bash
# Kotonoha Bot - エントリポイントスクリプト
# 起動前に必要なディレクトリの権限を確認

set -e

echo "Kotonoha Bot - Starting initialization..."

# 現在のユーザー情報を表示
echo "Current user: $(id)"
echo "Current working directory: $(pwd)"

# 必須ディレクトリ（エラーで終了）
REQUIRED_DIRS=(
    "/app/data"
)

# オプショナルディレクトリ（警告のみ）
OPTIONAL_DIRS=(
    "/app/logs"
    "/app/backups"
)

# 必須ディレクトリのチェック
for dir in "${REQUIRED_DIRS[@]}"; do
    if [ ! -d "$dir" ]; then
        echo "Creating required directory: $dir"
        mkdir -p "$dir" || {
            echo "ERROR: Failed to create required directory $dir"
            echo "Current user may not have permission to create directories."
            exit 1
        }
    fi
    
    # ディレクトリが書き込み可能か確認
    if [ ! -w "$dir" ]; then
        echo "ERROR: Required directory $dir is not writable by current user ($(id -u))"
        echo "Directory info:"
        ls -ld "$dir" || true
        echo ""
        echo "Please check the directory permissions on the host system."
        echo "The directory should be writable by the container user (UID: $(id -u))."
        exit 1
    else
        echo "Required directory $dir is writable ✓"
    fi
done

# オプショナルディレクトリのチェック（警告のみ）
for dir in "${OPTIONAL_DIRS[@]}"; do
    if [ ! -d "$dir" ]; then
        echo "Creating optional directory: $dir"
        mkdir -p "$dir" 2>/dev/null || {
            echo "WARNING: Could not create optional directory $dir (this is OK if not needed)"
        }
    fi
    
    # ディレクトリが書き込み可能か確認
    if [ ! -w "$dir" ]; then
        echo "WARNING: Optional directory $dir is not writable by current user ($(id -u))"
        echo "Directory info:"
        ls -ld "$dir" || true
        echo "This is OK if you don't need file logging or backups."
        echo "To enable, fix permissions on the host: chmod 755 $dir"
    else
        echo "Optional directory $dir is writable ✓"
    fi
done

echo "Directory checks complete. Starting application..."
echo ""

# Python アプリケーションを実行
exec python -m kotonoha_bot.main "$@"
