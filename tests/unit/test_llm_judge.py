"""聞き耳型LLM判断機能のテスト"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from kotonoha_bot.eavesdrop.llm_judge import LLMJudge


@pytest.fixture
def mock_session_manager():
    """モックSessionManager"""
    manager = MagicMock()
    manager.get_session = MagicMock(return_value=None)
    manager.create_session = MagicMock(return_value=MagicMock())
    manager.add_message = MagicMock()
    manager.save_session = MagicMock()
    return manager


@pytest.fixture
def mock_ai_provider():
    """モックAIProvider"""
    provider = MagicMock()
    # generate_responseは非同期関数なので、AsyncMockを使用
    # 戻り値は tuple[str, dict] 形式
    provider.generate_response = AsyncMock(return_value=("YES", {}))
    return provider


@pytest.fixture
def llm_judge(mock_session_manager, mock_ai_provider):
    """LLMJudgeのフィクスチャ"""
    return LLMJudge(mock_session_manager, mock_ai_provider)


@pytest.fixture
def mock_message():
    """モックメッセージ"""
    message = MagicMock()
    message.author = MagicMock()
    message.author.display_name = "テストユーザー"
    message.content = "テストメッセージ"
    return message


@pytest.fixture
def recent_messages():
    """直近のメッセージリスト"""
    messages = []
    for i in range(5):
        msg = MagicMock()
        msg.author = MagicMock()
        msg.author.display_name = f"ユーザー{i}"
        msg.content = f"メッセージ{i}"
        messages.append(msg)
    return messages


@pytest.mark.asyncio
async def test_should_respond_empty_messages(llm_judge):
    """空のメッセージリストの場合はFalseを返す"""
    result = await llm_judge.should_respond(123456789, [])
    assert result is False


@pytest.mark.asyncio
async def test_should_respond_yes_response(llm_judge, recent_messages):
    """YES応答の場合、Trueを返す"""
    llm_judge.ai_provider.generate_response = AsyncMock(return_value=("YES", {}))
    # 会話状態分析をモック化
    with patch.object(
        llm_judge, "_analyze_conversation_state", new_callable=AsyncMock
    ) as mock_state:
        mock_state.return_value = "active"
        # 介入履歴チェックをモック化
        with patch.object(
            llm_judge,
            "_has_conversation_changed_after_intervention",
            new_callable=AsyncMock,
        ) as mock_changed:
            mock_changed.return_value = True

            result = await llm_judge.should_respond(123456789, recent_messages)

            assert result is True
            # 介入が記録されたことを確認
            assert 123456789 in llm_judge.intervention_history


@pytest.mark.asyncio
async def test_should_respond_no_response(llm_judge, recent_messages):
    """NO応答の場合、Falseを返す"""
    llm_judge.ai_provider.generate_response = AsyncMock(return_value=("NO", {}))
    # 会話状態分析をモック化
    with patch.object(
        llm_judge, "_analyze_conversation_state", new_callable=AsyncMock
    ) as mock_state:
        mock_state.return_value = "active"
        # 介入履歴チェックをモック化
        with patch.object(
            llm_judge,
            "_has_conversation_changed_after_intervention",
            new_callable=AsyncMock,
        ) as mock_changed:
            mock_changed.return_value = True

            result = await llm_judge.should_respond(123456789, recent_messages)

            assert result is False
            # 介入が記録されなかったことを確認
            assert (
                123456789 not in llm_judge.intervention_history
                or len(llm_judge.intervention_history.get(123456789, [])) == 0
            )


@pytest.mark.asyncio
async def test_should_respond_conversation_ending(llm_judge, recent_messages):
    """会話が終了しようとしている場合はFalseを返す"""
    # 会話状態分析をモック化
    with patch.object(
        llm_judge, "_analyze_conversation_state", new_callable=AsyncMock
    ) as mock_state:
        mock_state.return_value = "ending"

        result = await llm_judge.should_respond(123456789, recent_messages)

        assert result is False
        # LLM判定が呼ばれなかったことを確認
        llm_judge.ai_provider.generate_response.assert_not_called()


@pytest.mark.asyncio
async def test_should_respond_conversation_not_changed(llm_judge, recent_messages):
    """会話状況が変わっていない場合はFalseを返す"""
    # 介入履歴を設定
    llm_judge.intervention_history[123456789] = [
        (datetime.now() - timedelta(minutes=5), "前回の会話ログ")
    ]

    # 会話状態分析をモック化
    with patch.object(
        llm_judge, "_analyze_conversation_state", new_callable=AsyncMock
    ) as mock_state:
        mock_state.return_value = "active"
        # 介入履歴チェックをモック化
        with patch.object(
            llm_judge,
            "_has_conversation_changed_after_intervention",
            new_callable=AsyncMock,
        ) as mock_changed:
            mock_changed.return_value = False

            result = await llm_judge.should_respond(123456789, recent_messages)

            assert result is False
            # LLM判定が呼ばれなかったことを確認
            llm_judge.ai_provider.generate_response.assert_not_called()


@pytest.mark.asyncio
async def test_should_respond_error_handling(llm_judge, recent_messages):
    """エラーが発生した場合はFalseを返す"""
    llm_judge.ai_provider.generate_response = AsyncMock(
        side_effect=Exception("テストエラー")
    )
    # 会話状態分析をモック化
    with patch.object(
        llm_judge, "_analyze_conversation_state", new_callable=AsyncMock
    ) as mock_state:
        mock_state.return_value = "active"
        # 介入履歴チェックをモック化
        with patch.object(
            llm_judge,
            "_has_conversation_changed_after_intervention",
            new_callable=AsyncMock,
        ) as mock_changed:
            mock_changed.return_value = True

            result = await llm_judge.should_respond(123456789, recent_messages)

            assert result is False


@pytest.mark.asyncio
async def test_generate_response_should_not_respond(llm_judge, recent_messages):
    """should_respondがFalseの場合、Noneを返す"""
    with patch.object(
        llm_judge, "should_respond", new_callable=AsyncMock
    ) as mock_should:
        mock_should.return_value = False

        result = await llm_judge.generate_response(123456789, recent_messages)

        assert result is None
        # 応答生成が呼ばれなかったことを確認
        llm_judge.ai_provider.generate_response.assert_not_called()


@pytest.mark.asyncio
async def test_generate_response_success(llm_judge, recent_messages):
    """should_respondがTrueの場合、応答を生成する"""
    with patch.object(
        llm_judge, "should_respond", new_callable=AsyncMock
    ) as mock_should:
        mock_should.return_value = True
        llm_judge.ai_provider.generate_response = AsyncMock(
            return_value=("生成された応答", {})
        )

        result = await llm_judge.generate_response(123456789, recent_messages)

        assert result == "生成された応答"
        # 応答生成が呼ばれたことを確認
        assert llm_judge.ai_provider.generate_response.call_count == 1


@pytest.mark.asyncio
async def test_generate_response_error_handling(llm_judge, recent_messages):
    """応答生成でエラーが発生した場合、Noneを返す"""
    with patch.object(
        llm_judge, "should_respond", new_callable=AsyncMock
    ) as mock_should:
        mock_should.return_value = True
        llm_judge.ai_provider.generate_response = AsyncMock(
            side_effect=Exception("テストエラー")
        )

        result = await llm_judge.generate_response(123456789, recent_messages)

        assert result is None


@pytest.mark.asyncio
async def test_format_conversation_log(llm_judge, recent_messages):
    """会話ログのフォーマットが正しく動作する"""
    log = llm_judge._format_conversation_log(recent_messages)

    assert isinstance(log, str)
    # 各メッセージが含まれていることを確認
    for msg in recent_messages:
        assert msg.author.display_name in log
        assert msg.content in log


@pytest.mark.asyncio
async def test_record_intervention(llm_judge, recent_messages):
    """介入が正しく記録される"""
    channel_id = 123456789
    llm_judge._record_intervention(channel_id, recent_messages)

    # 介入履歴に記録されたことを確認
    assert channel_id in llm_judge.intervention_history
    assert len(llm_judge.intervention_history[channel_id]) == 1
    # 記録された時刻と会話ログを確認
    intervention_time, intervention_log = llm_judge.intervention_history[channel_id][0]
    assert isinstance(intervention_time, datetime)
    assert isinstance(intervention_log, str)


@pytest.mark.asyncio
async def test_get_intervention_context_no_history(llm_judge):
    """介入履歴がない場合、Noneを返す"""
    context = llm_judge._get_intervention_context(123456789)
    assert context is None


@pytest.mark.asyncio
async def test_get_intervention_context_with_history(llm_judge, recent_messages):
    """介入履歴がある場合、コンテキストを返す"""
    channel_id = 123456789
    # 介入を記録
    llm_judge._record_intervention(channel_id, recent_messages)

    context = llm_judge._get_intervention_context(channel_id)

    assert context is not None
    assert isinstance(context, str)
    assert "介入履歴" in context or "最後の介入" in context


@pytest.mark.asyncio
async def test_analyze_conversation_state(llm_judge, recent_messages):
    """会話状態の分析が正しく動作する"""
    llm_judge.ai_provider.generate_response = AsyncMock(return_value=("ACTIVE", {}))

    state = await llm_judge._analyze_conversation_state(recent_messages)

    assert state in ("active", "ending", "misunderstanding", "conflict")
    # LLM判定が呼ばれたことを確認
    llm_judge.ai_provider.generate_response.assert_called_once()


@pytest.mark.asyncio
async def test_analyze_conversation_state_ending(llm_judge, recent_messages):
    """会話が終了しようとしている場合、endingを返す"""
    llm_judge.ai_provider.generate_response = AsyncMock(return_value=("ENDING", {}))

    state = await llm_judge._analyze_conversation_state(recent_messages)

    assert state == "ending"


@pytest.mark.asyncio
async def test_analyze_conversation_state_error(llm_judge, recent_messages):
    """エラーが発生した場合、activeを返す（デフォルト）"""
    llm_judge.ai_provider.generate_response = AsyncMock(
        side_effect=Exception("テストエラー")
    )

    state = await llm_judge._analyze_conversation_state(recent_messages)

    assert state == "active"  # デフォルト値


@pytest.mark.asyncio
async def test_has_conversation_changed_after_intervention_no_history(
    llm_judge, recent_messages
):
    """介入履歴がない場合、Trueを返す（初回介入）"""
    result = await llm_judge._has_conversation_changed_after_intervention(
        123456789, recent_messages
    )
    assert result is True


@pytest.mark.asyncio
async def test_has_conversation_changed_after_intervention_min_interval(
    llm_judge, recent_messages
):
    """最小間隔が経過していない場合、Falseを返す"""
    channel_id = 123456789
    # 最近の介入を記録
    llm_judge.intervention_history[channel_id] = [
        (datetime.now() - timedelta(minutes=1), "前回の会話ログ")
    ]

    # 最小間隔を短く設定（テスト用）
    with patch("kotonoha_bot.eavesdrop.llm_judge.Config") as mock_config:
        mock_config.EAVESDROP_MIN_INTERVENTION_INTERVAL_MINUTES = 10

        result = await llm_judge._has_conversation_changed_after_intervention(
            channel_id, recent_messages
        )

        assert result is False


@pytest.mark.asyncio
async def test_has_conversation_changed_after_intervention_different_conversation(
    llm_judge, recent_messages
):
    """別の会話の場合、Trueを返す"""
    channel_id = 123456789
    # 古い介入を記録
    llm_judge.intervention_history[channel_id] = [
        (datetime.now() - timedelta(minutes=15), "前回の会話ログ")
    ]

    # 最小間隔を短く設定（テスト用）
    with patch("kotonoha_bot.eavesdrop.llm_judge.Config") as mock_config:
        mock_config.EAVESDROP_MIN_INTERVENTION_INTERVAL_MINUTES = 10
        # 同じ会話判定をモック化
        with patch.object(
            llm_judge, "_is_same_conversation", new_callable=AsyncMock
        ) as mock_same:
            mock_same.return_value = False  # 別の会話

            result = await llm_judge._has_conversation_changed_after_intervention(
                channel_id, recent_messages
            )

            assert result is True


@pytest.mark.asyncio
async def test_is_same_conversation(llm_judge):
    """同じ会話判定が正しく動作する"""
    previous_log = "ユーザー1: こんにちは\nユーザー2: こんにちは"
    current_log = "ユーザー1: 元気ですか？\nユーザー2: はい、元気です"

    llm_judge.ai_provider.generate_response = AsyncMock(return_value=("SAME", {}))

    result = await llm_judge._is_same_conversation(previous_log, current_log)

    assert isinstance(result, bool)
    # LLM判定が呼ばれたことを確認
    llm_judge.ai_provider.generate_response.assert_called_once()


@pytest.mark.asyncio
async def test_is_same_conversation_error(llm_judge):
    """エラーが発生した場合、Trueを返す（安全側）"""
    previous_log = "前回のログ"
    current_log = "現在のログ"

    llm_judge.ai_provider.generate_response = AsyncMock(
        side_effect=Exception("テストエラー")
    )

    result = await llm_judge._is_same_conversation(previous_log, current_log)

    assert result is True  # 安全側に倒す


@pytest.mark.asyncio
async def test_check_conversation_situation_changed(llm_judge):
    """会話状況が変わったかの判定が正しく動作する"""
    last_intervention_log = "前回の介入時の会話ログ"
    current_log = "現在の会話ログ"

    llm_judge.ai_provider.generate_response = AsyncMock(return_value=("CHANGED", {}))

    result = await llm_judge._check_conversation_situation_changed(
        last_intervention_log, current_log
    )

    assert result is True
    # LLM判定が呼ばれたことを確認
    llm_judge.ai_provider.generate_response.assert_called_once()


@pytest.mark.asyncio
async def test_check_conversation_situation_changed_unchanged(llm_judge):
    """会話状況が変わっていない場合、Falseを返す"""
    last_intervention_log = "前回の介入時の会話ログ"
    current_log = "現在の会話ログ"

    llm_judge.ai_provider.generate_response = AsyncMock(return_value=("UNCHANGED", {}))

    result = await llm_judge._check_conversation_situation_changed(
        last_intervention_log, current_log
    )

    assert result is False


@pytest.mark.asyncio
async def test_check_conversation_situation_changed_error(llm_judge):
    """エラーが発生した場合、Trueを返す（安全側）"""
    last_intervention_log = "前回の介入時の会話ログ"
    current_log = "現在の会話ログ"

    llm_judge.ai_provider.generate_response = AsyncMock(
        side_effect=Exception("テストエラー")
    )

    result = await llm_judge._check_conversation_situation_changed(
        last_intervention_log, current_log
    )

    assert result is True  # 安全側に倒す
