#!/bin/bash
# PostgreSQLデータベース完全初期化スクリプト
# 本番用とテスト用の両方に対応

set -e

# 色の定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 引数の解析
TARGET="${1:-all}"  # all, main, test

echo "=========================================="
echo "PostgreSQLデータベース初期化スクリプト"
echo "=========================================="
echo ""
echo -e "${RED}⚠️  警告: この操作はすべてのデータを削除します${NC}"
echo ""

# 確認
read -p "本当にデータベースを初期化しますか？ (yes/no): " confirm
if [ "$confirm" != "yes" ]; then
    echo "初期化をキャンセルしました"
    exit 0
fi

echo ""
echo "初期化対象: ${TARGET}"
echo ""

# 環境変数の読み込み（KEY=VALUE形式の行のみ、コメント行や空行は無視）
if [ -f .env ]; then
    set -a
    # KEY=VALUE形式の行のみを抽出して読み込む（行内コメントも除去）
    grep -E '^[A-Z_][A-Z0-9_]*=.*' .env | sed 's/#.*$//' | sed 's/[[:space:]]*$//' | grep -v '^$' > /tmp/.env.clean
    . /tmp/.env.clean 2>/dev/null || true
    rm -f /tmp/.env.clean
    set +a
fi

# 本番用データベースの初期化
if [ "$TARGET" = "all" ] || [ "$TARGET" = "main" ]; then
    echo "=========================================="
    echo "本番用データベースの初期化"
    echo "=========================================="
    echo ""
    
    # コンテナを停止
    echo "1. コンテナを停止中..."
    docker compose stop postgres kotonoha 2>/dev/null || true
    docker compose rm -f postgres kotonoha 2>/dev/null || true
    
    # ボリュームを削除
    echo "2. データボリュームを削除中..."
    if docker volume ls | grep -q "kotonoha-bot_postgres_data"; then
        docker volume rm kotonoha-bot_postgres_data
        echo -e "${GREEN}   ✅ 本番用データボリュームを削除しました${NC}"
    else
        echo -e "${YELLOW}   ⚠️  本番用データボリュームが見つかりませんでした${NC}"
    fi
    
    # コンテナを再起動
    echo "3. PostgreSQLコンテナを起動中..."
    docker compose up -d postgres
    
    # 起動を待機
    echo "4. データベースの起動を待機中..."
    timeout=60
    elapsed=0
    while [ $elapsed -lt $timeout ]; do
        if docker compose exec -T postgres pg_isready -U ${POSTGRES_USER:-kotonoha} >/dev/null 2>&1; then
            echo -e "${GREEN}   ✅ データベースが起動しました${NC}"
            break
        fi
        sleep 2
        elapsed=$((elapsed + 2))
        echo "   待機中... (${elapsed}/${timeout}秒)"
    done
    
    if [ $elapsed -ge $timeout ]; then
        echo -e "${RED}   ❌ データベースの起動に失敗しました${NC}"
        exit 1
    fi
    
    # マイグレーションの実行
    echo "5. マイグレーションを実行中..."
    # 環境変数を明示的に設定（ホストマシンから実行するためlocalhostを使用）
    # .envファイルのPOSTGRES_HOSTが"postgres"（Dockerサービス名）の場合は上書き
    if [ "${POSTGRES_HOST:-}" = "postgres" ]; then
        export POSTGRES_HOST="localhost"
    else
        export POSTGRES_HOST="${POSTGRES_HOST:-localhost}"
    fi
    export POSTGRES_PORT="${POSTGRES_PORT:-5433}"
    export POSTGRES_DB="${POSTGRES_DB:-kotonoha}"
    export POSTGRES_USER="${POSTGRES_USER:-kotonoha}"
    export POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-password}"
    
    # DATABASE_URLを明示的に構築（.envのDATABASE_URLは無視）
    export DATABASE_URL="postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:${POSTGRES_PORT}/${POSTGRES_DB}"
    
    if uv run alembic upgrade head; then
        echo -e "${GREEN}   ✅ マイグレーションが完了しました${NC}"
    else
        echo -e "${RED}   ❌ マイグレーションの実行に失敗しました${NC}"
        echo "   手動実行: uv run alembic upgrade head"
        echo "   接続情報: ${DATABASE_URL}"
        exit 1
    fi
    
    # 確認
    echo "6. データベースの状態を確認中..."
    if docker compose exec -T postgres psql -U ${POSTGRES_USER:-kotonoha} -d ${POSTGRES_DB:-kotonoha} -c "SELECT version();" >/dev/null 2>&1; then
        echo -e "${GREEN}   ✅ 本番用データベースが正常に初期化されました${NC}"
    else
        echo -e "${RED}   ❌ 本番用データベースの確認に失敗しました${NC}"
    fi
    
    echo ""
fi

# テスト用データベースの初期化
if [ "$TARGET" = "all" ] || [ "$TARGET" = "test" ]; then
    echo "=========================================="
    echo "テスト用データベースの初期化"
    echo "=========================================="
    echo ""
    
    # コンテナを停止
    echo "1. テスト用コンテナを停止中..."
    docker compose --profile test stop postgres-test 2>/dev/null || true
    docker compose --profile test rm -f postgres-test 2>/dev/null || true
    
    # ボリュームを削除
    echo "2. テスト用データボリュームを削除中..."
    if docker volume ls | grep -q "kotonoha-bot_postgres_test_data"; then
        docker volume rm kotonoha-bot_postgres_test_data
        echo -e "${GREEN}   ✅ テスト用データボリュームを削除しました${NC}"
    else
        echo -e "${YELLOW}   ⚠️  テスト用データボリュームが見つかりませんでした${NC}"
    fi
    
    # コンテナを再起動
    echo "3. テスト用PostgreSQLコンテナを起動中..."
    docker compose --profile test up -d postgres-test
    
    # 起動を待機
    echo "4. テスト用データベースの起動を待機中..."
    timeout=60
    elapsed=0
    while [ $elapsed -lt $timeout ]; do
        if docker compose --profile test exec -T postgres-test pg_isready -U ${TEST_POSTGRES_USER:-test} -d ${TEST_POSTGRES_DB:-test_kotonoha} >/dev/null 2>&1; then
            echo -e "${GREEN}   ✅ テスト用データベースが起動しました${NC}"
            break
        fi
        sleep 2
        elapsed=$((elapsed + 2))
        echo "   待機中... (${elapsed}/${timeout}秒)"
    done
    
    if [ $elapsed -ge $timeout ]; then
        echo -e "${RED}   ❌ テスト用データベースの起動に失敗しました${NC}"
        exit 1
    fi
    
    # マイグレーションの実行（テスト用）
    echo "5. テスト用データベースにマイグレーションを実行中..."
    # テスト用環境変数を明示的に設定
    export POSTGRES_HOST="${TEST_POSTGRES_HOST:-localhost}"
    export POSTGRES_PORT="${TEST_POSTGRES_PORT:-5435}"
    export POSTGRES_DB="${TEST_POSTGRES_DB:-test_kotonoha}"
    export POSTGRES_USER="${TEST_POSTGRES_USER:-test}"
    export POSTGRES_PASSWORD="${TEST_POSTGRES_PASSWORD:-test}"
    
    # DATABASE_URLをテスト用に設定
    export DATABASE_URL="postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:${POSTGRES_PORT}/${POSTGRES_DB}"
    
    if uv run alembic upgrade head; then
        echo -e "${GREEN}   ✅ テスト用データベースのマイグレーションが完了しました${NC}"
    else
        echo -e "${RED}   ❌ テスト用データベースのマイグレーションの実行に失敗しました${NC}"
        echo "   手動実行: DATABASE_URL=\"${DATABASE_URL}\" uv run alembic upgrade head"
        exit 1
    fi
    
    # 確認
    echo "6. テスト用データベースの状態を確認中..."
    if docker compose --profile test exec -T postgres-test psql -U ${TEST_POSTGRES_USER:-test} -d ${TEST_POSTGRES_DB:-test_kotonoha} -c "SELECT version();" >/dev/null 2>&1; then
        echo -e "${GREEN}   ✅ テスト用データベースが正常に初期化されました${NC}"
    else
        echo -e "${RED}   ❌ テスト用データベースの確認に失敗しました${NC}"
    fi
    
    echo ""
fi

echo "=========================================="
echo -e "${GREEN}初期化完了${NC}"
echo "=========================================="
echo ""
echo "次のステップ:"
echo "  1. すべてのサービスを起動: docker compose up -d"
echo "  2. テストを実行: uv run pytest"
echo ""
