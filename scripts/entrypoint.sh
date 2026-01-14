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
        echo "WARNING: Required directory $dir is not writable by current user ($(id -u))"
        echo "Directory info:"
        ls -ld "$dir" || true
        echo ""
        echo "Attempting to fix permissions automatically..."
        
        # パーミッション修正を試行（777で全員に書き込み権限を付与）
        if chmod 777 "$dir" 2>/dev/null; then
            echo "Successfully fixed permissions for $dir"
            # 再度書き込み可能か確認
            if [ -w "$dir" ]; then
                echo "Required directory $dir is now writable ✓"
            else
                echo "ERROR: Permission fix failed. Directory is still not writable."
                echo "Please check the directory permissions on the host system."
                echo "The directory should be writable by the container user (UID: $(id -u))."
                exit 1
            fi
        else
            echo "ERROR: Failed to fix permissions automatically."
            echo "Please check the directory permissions on the host system."
            echo "Run on the host: chmod 775 $dir (or chmod 777 $dir)"
            echo "The directory should be writable by the container user (UID: $(id -u))."
            exit 1
        fi
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
        echo "Attempting to fix permissions automatically..."
        
        # パーミッション修正を試行
        if chmod 777 "$dir" 2>/dev/null; then
            echo "Successfully fixed permissions for $dir"
            if [ -w "$dir" ]; then
                echo "Optional directory $dir is now writable ✓"
            else
                echo "WARNING: Permission fix failed for optional directory $dir (this is OK if not needed)"
            fi
        else
            echo "WARNING: Could not fix permissions for optional directory $dir"
            echo "This is OK if you don't need file logging or backups."
            echo "To enable, fix permissions on the host: chmod 775 $dir (or chmod 777 $dir)"
        fi
    else
        echo "Optional directory $dir is writable ✓"
    fi
done

echo "Directory checks complete. Starting application..."
echo ""

# Python アプリケーションを実行
exec python -m kotonoha_bot.main "$@"
