"""聞き耳型ハンドラーの詳細テスト."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from kotonoha_bot.bot.handlers.eavesdrop import EavesdropHandler
from kotonoha_bot.db.models import ChatSession
from kotonoha_bot.rate_limit.request_queue import RequestPriority, RequestQueue
from kotonoha_bot.services.ai import TokenInfo
from kotonoha_bot.services.eavesdrop import ConversationBuffer, LLMJudge


@pytest.fixture
def mock_bot():
    """モックBot."""
    bot = MagicMock()
    bot.user = MagicMock()
    bot.user.id = 123456789
    return bot


@pytest.fixture
def mock_session_manager():
    """モックSessionManager."""
    manager = MagicMock()
    session = MagicMock(spec=ChatSession)
    session.session_key = "eavesdrop:777888999"
    session.get_conversation_history = MagicMock(return_value=[])
    session.messages = []
    manager.get_session = AsyncMock(return_value=None)
    manager.create_session = AsyncMock(return_value=session)
    manager.add_message = AsyncMock()
    manager.save_session = AsyncMock()
    return manager


@pytest.fixture
def mock_ai_provider():
    """モックAIProvider."""
    provider = MagicMock()
    token_info = TokenInfo(
        input_tokens=10,
        output_tokens=5,
        total_tokens=15,
        model_used="anthropic/claude-3-haiku-20240307",
        latency_ms=100,
    )
    provider.generate_response = AsyncMock(return_value=("テスト応答", token_info))
    provider.get_last_used_model = MagicMock(
        return_value="anthropic/claude-3-haiku-20240307"
    )
    provider.get_rate_limit_usage = MagicMock(return_value=0.5)
    return provider


@pytest.fixture
def mock_llm_judge():
    """モックLLMJudge."""
    judge = MagicMock(spec=LLMJudge)
    # generate_responseをAsyncMockとして設定（警告を防ぐため、return_valueを使用）
    judge.generate_response = AsyncMock(return_value="応答テキスト")
    return judge


@pytest.fixture
def mock_buffer():
    """モックConversationBuffer."""
    buffer = MagicMock(spec=ConversationBuffer)
    buffer.add_message = MagicMock()
    buffer.get_recent_messages = MagicMock(return_value=[])
    return buffer


@pytest.fixture
def mock_router():
    """モックMessageRouter."""
    router = MagicMock()
    router.eavesdrop_enabled_channels = {777888999}
    return router


@pytest.fixture
def mock_request_queue():
    """モックRequestQueue."""
    queue = MagicMock(spec=RequestQueue)

    async def enqueue_side_effect(_priority, func, *args, **kwargs):
        result = await func(*args, **kwargs)
        future = asyncio.Future()
        future.set_result(result)
        return future

    queue.enqueue = AsyncMock(side_effect=enqueue_side_effect)
    return queue


@pytest.fixture
def mock_config():
    """モックConfig."""
    config = MagicMock()
    config.EAVESDROP_BUFFER_SIZE = 20
    config.EAVESDROP_MIN_MESSAGES = 3
    return config


@pytest.fixture
def eavesdrop_handler(
    mock_bot,
    mock_session_manager,
    mock_ai_provider,
    mock_llm_judge,
    mock_buffer,
    mock_router,
    mock_request_queue,
    mock_config,
):
    """EavesdropHandler インスタンス."""
    return EavesdropHandler(
        bot=mock_bot,
        session_manager=mock_session_manager,
        ai_provider=mock_ai_provider,
        llm_judge=mock_llm_judge,
        buffer=mock_buffer,
        router=mock_router,
        request_queue=mock_request_queue,
        config=mock_config,
    )


class TestEavesdropHandlerProcess:
    """_process メソッドのテスト."""

    @pytest.mark.asyncio
    async def test_process_success_with_response(
        self, eavesdrop_handler, mock_session_manager, mock_llm_judge, mock_buffer
    ):
        """聞き耳型処理が成功し、応答が生成される."""
        mock_message = MagicMock(spec=discord.Message)
        mock_message.author = MagicMock()
        mock_message.author.bot = False
        mock_message.channel = MagicMock()
        mock_message.channel.id = 777888999
        mock_message.channel.send = AsyncMock()
        mock_message.guild = MagicMock()
        mock_message.guild.id = 111222333

        # 十分なメッセージがある場合
        mock_messages = [MagicMock(), MagicMock(), MagicMock()]
        mock_buffer.get_recent_messages = MagicMock(return_value=mock_messages)
        mock_llm_judge.generate_response = AsyncMock(return_value="応答テキスト")

        session = MagicMock(spec=ChatSession)
        session.get_conversation_history = MagicMock(return_value=[])
        mock_session_manager.get_session = AsyncMock(return_value=None)
        mock_session_manager.create_session = AsyncMock(return_value=session)

        await eavesdrop_handler._process(mock_message)

        # バッファにメッセージが追加されたことを確認
        mock_buffer.add_message.assert_called_once_with(777888999, mock_message)
        # LLM判定が呼ばれたことを確認
        mock_llm_judge.generate_response.assert_called_once()
        # セッションが作成されたことを確認
        mock_session_manager.create_session.assert_called_once()
        # 応答が送信されたことを確認
        mock_message.channel.send.assert_called()

    @pytest.mark.asyncio
    async def test_process_not_enough_messages(
        self, eavesdrop_handler, mock_buffer, mock_llm_judge
    ):
        """メッセージ数が不足している場合."""
        mock_message = MagicMock(spec=discord.Message)
        mock_message.author = MagicMock()
        mock_message.author.bot = False
        mock_message.channel = MagicMock()
        mock_message.channel.id = 777888999
        mock_message.channel.send = AsyncMock()

        # メッセージ数が不足している場合
        mock_buffer.get_recent_messages = MagicMock(return_value=[MagicMock()])

        await eavesdrop_handler._process(mock_message)

        # LLM判定は呼ばれないことを確認
        mock_llm_judge.generate_response.assert_not_called()
        # 応答は送信されないことを確認
        mock_message.channel.send.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_no_response(
        self, eavesdrop_handler, mock_session_manager, mock_llm_judge, mock_buffer
    ):
        """LLM判定で応答が生成されない場合."""
        mock_message = MagicMock(spec=discord.Message)
        mock_message.author = MagicMock()
        mock_message.author.bot = False
        mock_message.channel = MagicMock()
        mock_message.channel.id = 777888999
        mock_message.channel.send = AsyncMock()
        mock_message.guild = MagicMock()
        mock_message.guild.id = 111222333

        # 十分なメッセージがある場合
        mock_messages = [MagicMock(), MagicMock(), MagicMock()]
        mock_buffer.get_recent_messages = MagicMock(return_value=mock_messages)
        # 応答が生成されない場合
        mock_llm_judge.generate_response = AsyncMock(return_value=None)

        await eavesdrop_handler._process(mock_message)

        # LLM判定は呼ばれたことを確認
        mock_llm_judge.generate_response.assert_called_once()
        # 応答は送信されないことを確認
        mock_message.channel.send.assert_not_called()
        # セッションは作成されないことを確認
        mock_session_manager.create_session.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_existing_session(
        self, eavesdrop_handler, mock_session_manager, mock_llm_judge, mock_buffer
    ):
        """既存セッションがある場合."""
        mock_message = MagicMock(spec=discord.Message)
        mock_message.author = MagicMock()
        mock_message.author.bot = False
        mock_message.channel = MagicMock()
        mock_message.channel.id = 777888999
        mock_message.channel.send = AsyncMock()
        mock_message.guild = MagicMock()
        mock_message.guild.id = 111222333

        # 十分なメッセージがある場合
        mock_messages = [MagicMock(), MagicMock(), MagicMock()]
        mock_buffer.get_recent_messages = MagicMock(return_value=mock_messages)
        mock_llm_judge.generate_response = AsyncMock(return_value="応答テキスト")

        session = MagicMock(spec=ChatSession)
        session.get_conversation_history = MagicMock(return_value=[])
        mock_session_manager.get_session = AsyncMock(return_value=session)

        await eavesdrop_handler._process(mock_message)

        # 新規セッションは作成されないことを確認
        mock_session_manager.create_session.assert_not_called()
        # 応答が送信されたことを確認
        mock_message.channel.send.assert_called()

    @pytest.mark.asyncio
    async def test_process_error_no_error_message(
        self, eavesdrop_handler, mock_llm_judge, mock_buffer
    ):
        """エラーが発生してもエラーメッセージを送信しない."""
        mock_message = MagicMock(spec=discord.Message)
        mock_message.author = MagicMock()
        mock_message.author.bot = False
        mock_message.channel = MagicMock()
        mock_message.channel.id = 777888999
        mock_message.channel.send = AsyncMock()

        # 十分なメッセージがある場合
        mock_messages = [MagicMock(), MagicMock(), MagicMock()]
        mock_buffer.get_recent_messages = MagicMock(return_value=mock_messages)
        # エラーを発生させる
        mock_llm_judge.generate_response = AsyncMock(side_effect=RuntimeError("Error"))

        await eavesdrop_handler._process(mock_message)

        # エラーメッセージは送信されないことを確認
        mock_message.channel.send.assert_not_called()


class TestEavesdropHandlerHandle:
    """handle メソッドのテスト."""

    @pytest.mark.asyncio
    async def test_handle_bot_message_ignored(self, eavesdrop_handler):
        """Bot自身のメッセージは無視される."""
        mock_message = MagicMock(spec=discord.Message)
        mock_message.author = MagicMock()
        mock_message.author.bot = True

        await eavesdrop_handler.handle(mock_message)

        # リクエストキューに追加されないことを確認
        eavesdrop_handler.request_queue.enqueue.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_channel_not_enabled(self, eavesdrop_handler):
        """聞き耳型が有効でないチャンネルの場合."""
        mock_message = MagicMock(spec=discord.Message)
        mock_message.author = MagicMock()
        mock_message.author.bot = False
        mock_message.channel = MagicMock()
        mock_message.channel.id = 111222333  # 有効でないチャンネルID

        await eavesdrop_handler.handle(mock_message)

        # リクエストキューに追加されないことを確認
        eavesdrop_handler.request_queue.enqueue.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_success(self, eavesdrop_handler):
        """聞き耳型処理が成功する."""
        mock_message = MagicMock(spec=discord.Message)
        mock_message.author = MagicMock()
        mock_message.author.bot = False
        mock_message.channel = MagicMock()
        mock_message.channel.id = 777888999  # 有効なチャンネルID

        await eavesdrop_handler.handle(mock_message)

        # リクエストキューに追加されたことを確認
        eavesdrop_handler.request_queue.enqueue.assert_called_once()
        call_args = eavesdrop_handler.request_queue.enqueue.call_args
        assert call_args[0][0] == RequestPriority.EAVESDROP

    @pytest.mark.asyncio
    async def test_handle_queue_error_fallback(self, eavesdrop_handler):
        """キューエラー時のフォールバック処理."""
        mock_message = MagicMock(spec=discord.Message)
        mock_message.author = MagicMock()
        mock_message.author.bot = False
        mock_message.channel = MagicMock()
        mock_message.channel.id = 777888999

        # キューエラーを発生させる
        eavesdrop_handler.request_queue.enqueue = AsyncMock(
            side_effect=RuntimeError("Queue is full")
        )

        # _process をモック
        eavesdrop_handler._process = AsyncMock()

        await eavesdrop_handler.handle(mock_message)

        # フォールバック処理が実行されたことを確認
        eavesdrop_handler._process.assert_called_once_with(mock_message)
