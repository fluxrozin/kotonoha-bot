#!/bin/bash
# Kotonoha Bot - エントリポイントスクリプト
# マウントされたディレクトリのパーミッションを修正し、botuser でアプリケーションを起動

set -e

log() {
    local log_file="/app/logs/entrypoint.log"
    local message="[$(date '+%Y-%m-%d %H:%M:%S')] $*"
    
    if [ -w "$(dirname "$log_file")" ] 2>/dev/null; then
        echo "$message" >> "$log_file" 2>/dev/null || echo "$message" >&2
    else
        echo "$message" >&2
    fi
}

if [ "$(id -u)" -eq 0 ]; then
    # ログディレクトリを先に作成
    mkdir -p /app/logs
    
    log "Running as root - fixing permissions and switching to botuser"
    
    for dir in /app/data /app/logs /app/backups; do
        mkdir -p "$dir"
        
        if chown -R botuser:botuser "$dir" 2>/dev/null; then
            if chmod 775 "$dir" 2>/dev/null || chmod 777 "$dir" 2>/dev/null; then
                log "Fixed permissions for $dir [OK]"
            else
                log "Warning: Could not set permissions for $dir"
            fi
        else
            log "Warning: Could not change ownership for $dir"
        fi
    done
    
    log "Switching to botuser (UID 1000) and starting application"
    exec gosu botuser python -m kotonoha_bot.main "$@"
else
    log "Running as non-root user - starting application"
    exec python -m kotonoha_bot.main "$@"
fi
