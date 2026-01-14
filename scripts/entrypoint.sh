#!/bin/bash
# Kotonoha Bot - エントリポイントスクリプト
# 起動前に必要なディレクトリの権限を確認

set -e

echo "Kotonoha Bot - Starting initialization..."

# 現在のユーザー情報を表示
echo "Current user: $(id)"
echo "Current working directory: $(pwd)"

# rootで実行されている場合、パーミッション修正後にユーザーを切り替える
RUN_AS_ROOT=false
if [ "$(id -u)" -eq 0 ]; then
    RUN_AS_ROOT=true
    echo "Running as root - will fix permissions and switch to botuser"
fi

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
        
        # パーミッション修正を試行（まず775を試し、失敗したら777を使用）
        # rootで実行されている場合は確実に修正できる
        if [ "$(id -u)" -eq 0 ]; then
            # まず775（グループ書き込み）を試す（より安全）
            chmod 775 "$dir" 2>/dev/null
            # botuserとして書き込み可能か確認
            if gosu botuser test -w "$dir" 2>/dev/null; then
                echo "Successfully fixed permissions for $dir (chmod 775) ✓"
            else
                # 775でダメな場合は777（全員書き込み）を試す
                chmod 777 "$dir"
                if gosu botuser test -w "$dir" 2>/dev/null; then
                    echo "Successfully fixed permissions for $dir (chmod 777) ✓"
                else
                    echo "WARNING: Could not verify write permission as botuser, but continuing..."
                fi
            fi
        else
            # rootでない場合、パーミッション修正はできない可能性が高い
            echo "ERROR: Cannot fix permissions automatically (not running as root)."
            echo "Current user: $(id)"
            echo ""
            echo "This container requires root privileges to automatically fix directory permissions."
            echo "Please use one of the following methods:"
            echo ""
            echo "Method 1 (Recommended): Use docker-compose.yml with 'user: root'"
            echo "  The docker-compose.yml file already has 'user: root' configured."
            echo ""
            echo "Method 2: Run with docker run and --user root"
            echo "  docker run --user root ..."
            echo ""
            echo "Method 3: Fix permissions manually on the host"
            echo "  chmod 775 $dir (or chmod 777 $dir)"
            echo ""
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
        
        # パーミッション修正を試行（まず775を試し、失敗したら777を使用）
        if [ "$(id -u)" -eq 0 ]; then
            # まず775（グループ書き込み）を試す（より安全）
            chmod 775 "$dir" 2>/dev/null
            # botuserとして書き込み可能か確認
            if gosu botuser test -w "$dir" 2>/dev/null; then
                echo "Successfully fixed permissions for $dir (chmod 775) ✓"
            else
                # 775でダメな場合は777（全員書き込み）を試す
                chmod 777 "$dir"
                if gosu botuser test -w "$dir" 2>/dev/null; then
                    echo "Successfully fixed permissions for $dir (chmod 777) ✓"
                else
                    echo "WARNING: Optional directory $dir may not be writable by botuser (this is OK if not needed)"
                fi
            fi
        else
            # rootでない場合、パーミッション修正はできない可能性が高い
            # オプショナルディレクトリなので警告のみで続行
            if chmod 775 "$dir" 2>/dev/null && [ -w "$dir" ]; then
                echo "Successfully fixed permissions for $dir (chmod 775) ✓"
            elif chmod 777 "$dir" 2>/dev/null && [ -w "$dir" ]; then
                echo "Successfully fixed permissions for $dir (chmod 777) ✓"
            else
                echo "WARNING: Could not fix permissions for optional directory $dir (not running as root)"
                echo "This is OK if you don't need file logging or backups."
                echo "To enable, either:"
                echo "  1. Run container as root (recommended: use docker-compose.yml with 'user: root')"
                echo "  2. Fix permissions manually on the host: chmod 775 $dir (or chmod 777 $dir)"
            fi
        fi
    else
        echo "Optional directory $dir is writable ✓"
    fi
done

echo "Directory checks complete. Starting application..."
echo ""

# rootで実行されている場合、botuserに切り替えてからアプリケーションを実行
if [ "$RUN_AS_ROOT" = true ]; then
    echo "Switching to botuser (UID 1000) and starting application..."
    exec gosu botuser python -m kotonoha_bot.main "$@"
else
    # 既にbotuserで実行されている場合
    exec python -m kotonoha_bot.main "$@"
fi
