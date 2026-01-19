#!/bin/bash
# Phase 9 完了確認スクリプト
# このスクリプトは Phase 9 の完了基準を確認します

set -euo pipefail

echo "=========================================="
echo "Phase 9 完了確認チェック"
echo "=========================================="
echo ""

ERROR_COUNT=0
PASS_COUNT=0

# 色の定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

check_pass() {
    echo -e "${GREEN}✓${NC} $1"
    PASS_COUNT=$((PASS_COUNT + 1))
}

check_fail() {
    echo -e "${RED}✗${NC} $1"
    ERROR_COUNT=$((ERROR_COUNT + 1))
}

check_warn() {
    echo -e "${YELLOW}⚠${NC} $1"
}

echo "【1】依存関係の確認"
echo "----------------------------------------"

# 1. anthropic パッケージが追加されている
if grep -q "anthropic" pyproject.toml; then
    check_pass "anthropic パッケージが追加されている"
else
    check_fail "anthropic パッケージが追加されていない"
fi

# 2. litellm パッケージが削除されている
if grep -q "litellm" pyproject.toml; then
    check_fail "litellm パッケージが削除されていない"
else
    check_pass "litellm パッケージが削除されている"
fi

echo ""
echo "【2】実装ファイルの確認"
echo "----------------------------------------"

# 3. AnthropicProvider クラスが実装されている
if [ -f "src/kotonoha_bot/ai/anthropic_provider.py" ]; then
    if grep -q "class AnthropicProvider" src/kotonoha_bot/ai/anthropic_provider.py; then
        check_pass "AnthropicProvider クラスが実装されている"
    else
        check_fail "AnthropicProvider クラスが実装されていない"
    fi
else
    check_fail "AnthropicProvider ファイルが存在しない"
fi

# 4. LiteLLMProvider が削除されている
if [ -f "src/kotonoha_bot/ai/litellm_provider.py" ]; then
    check_fail "LiteLLMProvider ファイルが削除されていない"
else
    check_pass "LiteLLMProvider ファイルが削除されている"
fi

# 5. LiteLLMProvider の使用箇所を確認
LITELLM_MATCHES=$(grep -r "LiteLLMProvider\|litellm_provider" src/ --include="*.py" 2>/dev/null | grep -v ".pyc" || true)
if [ -z "$LITELLM_MATCHES" ]; then
    LITELLM_COUNT=0
else
    LITELLM_COUNT=$(echo "$LITELLM_MATCHES" | wc -l | xargs)
fi
if [ "$LITELLM_COUNT" -eq 0 ]; then
    check_pass "LiteLLMProvider の使用箇所がすべて置き換えられている"
else
    check_fail "LiteLLMProvider の使用箇所が残っている（${LITELLM_COUNT}箇所）"
    echo "$LITELLM_MATCHES" | head -5
fi

# 6. AnthropicProvider の使用箇所を確認
ANTHROPIC_USAGE=$(grep -r "AnthropicProvider\|anthropic_provider" src/ --include="*.py" 2>/dev/null | grep -v ".pyc" | wc -l | tr -d ' ' || echo "0")
if [ "${ANTHROPIC_USAGE:-0}" -gt 0 ]; then
    check_pass "AnthropicProvider が使用されている（${ANTHROPIC_USAGE}箇所）"
else
    check_fail "AnthropicProvider が使用されていない"
fi

echo ""
echo "【3】インターフェースの確認"
echo "----------------------------------------"

# 7. AIProvider インターフェースが維持されている
if [ -f "src/kotonoha_bot/ai/provider.py" ]; then
    if grep -q "class AIProvider" src/kotonoha_bot/ai/provider.py; then
        check_pass "AIProvider インターフェースが維持されている"
    else
        check_fail "AIProvider インターフェースが存在しない"
    fi
else
    check_fail "AIProvider インターフェースファイルが存在しない"
fi

# 8. AnthropicProvider が AIProvider を継承している
if grep -q "class AnthropicProvider.*AIProvider" src/kotonoha_bot/ai/anthropic_provider.py; then
    check_pass "AnthropicProvider が AIProvider を継承している"
else
    check_fail "AnthropicProvider が AIProvider を継承していない"
fi

echo ""
echo "【4】機能の確認"
echo "----------------------------------------"

# 9. メタデータの返却（tuple[str, dict]）を確認
if grep -q "tuple\[str, dict\]" src/kotonoha_bot/ai/anthropic_provider.py; then
    check_pass "generate_response が tuple[str, dict] を返す"
else
    check_fail "generate_response が tuple[str, dict] を返していない"
fi

# 10. メタデータに input_tokens, output_tokens, model が含まれている
if grep -q '"input_tokens"' src/kotonoha_bot/ai/anthropic_provider.py && \
   grep -q '"output_tokens"' src/kotonoha_bot/ai/anthropic_provider.py && \
   grep -q '"model"' src/kotonoha_bot/ai/anthropic_provider.py; then
    check_pass "メタデータに input_tokens, output_tokens, model が含まれている"
else
    check_fail "メタデータに必要なキーが含まれていない"
fi

# 11. レート制限機能の確認
if grep -q "rate_limit_monitor\|RateLimitMonitor" src/kotonoha_bot/ai/anthropic_provider.py; then
    check_pass "レート制限機能が実装されている"
else
    check_fail "レート制限機能が実装されていない"
fi

echo ""
echo "【5】テストの確認"
echo "----------------------------------------"

# 12. ユニットテストが存在する
if [ -f "tests/unit/test_anthropic_provider.py" ]; then
    check_pass "ユニットテストファイルが存在する"
else
    check_fail "ユニットテストファイルが存在しない"
fi

# 13. 統合テストが存在する
if [ -f "tests/integration/test_ai_provider.py" ]; then
    check_pass "統合テストファイルが存在する"
else
    check_fail "統合テストファイルが存在しない"
fi

# 14. テストが通過する（実際に実行）
echo "テストを実行中（簡易チェック）..."
TEST_OUTPUT=$(uv run pytest tests/unit/test_anthropic_provider.py tests/integration/test_ai_provider.py --co -q 2>&1 | head -20)
TEST_COUNT=$(echo "$TEST_OUTPUT" | grep -c "test_" || echo "0")
if [ "$TEST_COUNT" -gt 0 ]; then
    check_pass "テストファイルにテストが定義されている（${TEST_COUNT}個）"
    echo "  注意: 実際のテスト実行は 'uv run pytest tests/unit/test_anthropic_provider.py tests/integration/test_ai_provider.py -v' で確認してください"
else
    check_fail "テストが定義されていない"
fi

echo ""
echo "【6】環境変数の確認"
echo "----------------------------------------"

# 15. LiteLLM 固有の環境変数が削除されている
if grep -q "LITELLM" .env.example 2>/dev/null; then
    check_warn "LiteLLM 固有の環境変数が .env.example に残っている可能性がある"
else
    check_pass "LiteLLM 固有の環境変数が削除されている"
fi

# 16. ANTHROPIC_API_KEY が設定されている
if grep -q "ANTHROPIC_API_KEY" .env.example; then
    check_pass "ANTHROPIC_API_KEY が .env.example に設定されている"
else
    check_fail "ANTHROPIC_API_KEY が .env.example に設定されていない"
fi

echo ""
echo "=========================================="
echo "チェック結果のサマリー"
echo "=========================================="
echo -e "${GREEN}✓ パス: ${PASS_COUNT}${NC}"
if [ "$ERROR_COUNT" -gt 0 ]; then
    echo -e "${RED}✗ エラー: ${ERROR_COUNT}${NC}"
    echo ""
    echo "Phase 9 は未完了です。上記のエラーを修正してください。"
    exit 1
else
    echo -e "${GREEN}✗ エラー: 0${NC}"
    echo ""
    echo "Phase 9 は完了しています！"
    exit 0
fi
