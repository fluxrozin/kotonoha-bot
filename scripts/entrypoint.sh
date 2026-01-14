#!/bin/bash
# Kotonoha Bot - エントリポイントスクリプト
# マウントされたディレクトリの所有者を修正し、botuserでアプリケーションを起動

set -e

# rootで実行されている場合のみ権限を修正
if [ "$(id -u)" -eq 0 ]; then
    # マウントされたディレクトリの所有者をbotuserに変更
    for dir in /app/data /app/logs /app/backups; do
        if [ -d "$dir" ]; then
            chown -R botuser:botuser "$dir" 2>/dev/null || true
            chmod 775 "$dir" 2>/dev/null || chmod 777 "$dir" 2>/dev/null || true
        fi
    done
    
    # botuserに切り替えてアプリケーションを起動
    exec gosu botuser python -m kotonoha_bot.main "$@"
else
    # 既にbotuserで実行されている場合
    exec python -m kotonoha_bot.main "$@"
fi
