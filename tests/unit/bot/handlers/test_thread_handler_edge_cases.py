"""ThreadHandler のエッジケースと境界値テスト."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from kotonoha_bot.bot.handlers.thread import ThreadHandler
from kotonoha_bot.db.models import ChatSession


@pytest.fixture
def mock_bot():
    """モックBot."""
    bot = MagicMock()
    bot.user = MagicMock()
    bot.user.id = 123456789
    return bot


@pytest.fixture
def mock_session_manager():
    """モックセッションマネージャー."""
    manager = MagicMock()
    manager.get_session = AsyncMock(return_value=None)
    manager.create_session = AsyncMock()
    manager.add_message = AsyncMock()
    manager.save_session = AsyncMock()
    return manager


@pytest.fixture
def mock_ai_provider():
    """モックAIプロバイダー."""
    provider = MagicMock()
    provider.generate_response = AsyncMock(return_value=("テスト応答", MagicMock()))
    provider.get_last_used_model = MagicMock(return_value="claude-sonnet-4-5")
    provider.get_rate_limit_usage = MagicMock(return_value=0.5)
    return provider


@pytest.fixture
def mock_router():
    """モックルーター."""
    router = MagicMock()
    router.register_bot_thread = MagicMock()
    return router


@pytest.fixture
def mock_mention_handler():
    """モックメンションハンドラー."""
    handler = MagicMock()
    handler.handle = AsyncMock()
    return handler


@pytest.fixture
def mock_config():
    """モックConfig."""
    config = MagicMock()
    config.THREAD_AUTO_ARCHIVE_DURATION = None
    return config


@pytest.fixture
def thread_handler(
    mock_bot,
    mock_session_manager,
    mock_ai_provider,
    mock_router,
    mock_mention_handler,
    mock_config,
):
    """ThreadHandler インスタンス."""
    return ThreadHandler(
        bot=mock_bot,
        session_manager=mock_session_manager,
        ai_provider=mock_ai_provider,
        router=mock_router,
        request_queue=MagicMock(),
        mention_handler=mock_mention_handler,
        config=mock_config,
    )


class TestThreadNameGenerationEdgeCases:
    """スレッド名生成のエッジケーステスト."""

    @pytest.mark.asyncio
    async def test_thread_name_empty_content(self, thread_handler):
        """メッセージ内容が空の場合、デフォルト名が使用される."""
        mock_message = MagicMock(spec=discord.Message)
        mock_message.content = ""
        mock_message.mentions = []
        mock_message.thread = None
        mock_message.reply = AsyncMock()
        mock_message.channel = MagicMock()
        mock_message.channel.id = 111222333
        mock_message.author = MagicMock()
        mock_message.author.id = 987654321

        mock_thread = MagicMock(spec=discord.Thread)
        mock_thread.id = 444555666
        mock_thread.guild = MagicMock()
        mock_thread.guild.id = 111222333
        # typing()は非同期コンテキストマネージャーとして動作する
        typing_context = AsyncMock()
        typing_context.__aenter__ = AsyncMock(return_value=None)
        typing_context.__aexit__ = AsyncMock(return_value=None)
        mock_thread.typing = MagicMock(return_value=typing_context)
        mock_thread.send = AsyncMock()
        _f = asyncio.Future()
        _f.set_result(mock_thread)
        mock_message.create_thread = MagicMock(return_value=_f)

        await thread_handler._create_thread_and_respond(mock_message)

        # デフォルト名「会話」が使用されることを確認
        mock_message.create_thread.assert_called_once()
        call_args = mock_message.create_thread.call_args
        assert call_args.kwargs["name"] == "会話"

    @pytest.mark.asyncio
    async def test_thread_name_only_mention(self, thread_handler):
        """メンションのみの場合、デフォルト名が使用される."""
        mock_message = MagicMock(spec=discord.Message)
        mock_message.content = "<@123456789>"
        mock_message.mentions = [thread_handler.bot.user]
        mock_message.thread = None
        mock_message.reply = AsyncMock()
        mock_message.channel = MagicMock()
        mock_message.channel.id = 111222333
        mock_message.author = MagicMock()
        mock_message.author.id = 987654321

        mock_thread = MagicMock(spec=discord.Thread)
        mock_thread.id = 444555666
        mock_thread.guild = MagicMock()
        mock_thread.guild.id = 111222333
        # typing()は非同期コンテキストマネージャーとして動作する
        typing_context = AsyncMock()
        typing_context.__aenter__ = AsyncMock(return_value=None)
        typing_context.__aexit__ = AsyncMock(return_value=None)
        mock_thread.typing = MagicMock(return_value=typing_context)
        mock_thread.send = AsyncMock()
        _f = asyncio.Future()
        _f.set_result(mock_thread)
        mock_message.create_thread = MagicMock(return_value=_f)

        await thread_handler._create_thread_and_respond(mock_message)

        # デフォルト名「会話」が使用されることを確認
        call_args = mock_message.create_thread.call_args
        assert call_args.kwargs["name"] == "会話"

    @pytest.mark.asyncio
    async def test_thread_name_very_long_content(self, thread_handler):
        """非常に長いメッセージの場合、50文字に切り詰められる."""
        long_message = "あ" * 200  # 200文字の長いメッセージ
        mock_message = MagicMock(spec=discord.Message)
        mock_message.content = long_message
        mock_message.mentions = []
        mock_message.thread = None
        mock_message.reply = AsyncMock()
        mock_message.channel = MagicMock()
        mock_message.channel.id = 111222333
        mock_message.author = MagicMock()
        mock_message.author.id = 987654321

        mock_thread = MagicMock(spec=discord.Thread)
        mock_thread.id = 444555666
        mock_thread.guild = MagicMock()
        mock_thread.guild.id = 111222333
        # typing()は非同期コンテキストマネージャーとして動作する
        typing_context = AsyncMock()
        typing_context.__aenter__ = AsyncMock(return_value=None)
        typing_context.__aexit__ = AsyncMock(return_value=None)
        mock_thread.typing = MagicMock(return_value=typing_context)
        mock_thread.send = AsyncMock()
        _f = asyncio.Future()
        _f.set_result(mock_thread)
        mock_message.create_thread = MagicMock(return_value=_f)

        await thread_handler._create_thread_and_respond(mock_message)

        # 50文字に切り詰められることを確認
        call_args = mock_message.create_thread.call_args
        thread_name = call_args.kwargs["name"]
        assert len(thread_name) <= 50

    @pytest.mark.asyncio
    async def test_thread_name_with_sentence_delimiter(self, thread_handler):
        """文の区切り文字がある場合、区切りで切られる."""
        mock_message = MagicMock(spec=discord.Message)
        mock_message.content = "これは最初の文です。これは2番目の文です。"
        mock_message.mentions = []
        mock_message.thread = None
        mock_message.reply = AsyncMock()
        mock_message.channel = MagicMock()
        mock_message.channel.id = 111222333
        mock_message.author = MagicMock()
        mock_message.author.id = 987654321

        mock_thread = MagicMock(spec=discord.Thread)
        mock_thread.id = 444555666
        mock_thread.guild = MagicMock()
        mock_thread.guild.id = 111222333
        # typing()は非同期コンテキストマネージャーとして動作する
        typing_context = AsyncMock()
        typing_context.__aenter__ = AsyncMock(return_value=None)
        typing_context.__aexit__ = AsyncMock(return_value=None)
        mock_thread.typing = MagicMock(return_value=typing_context)
        mock_thread.send = AsyncMock()
        _f = asyncio.Future()
        _f.set_result(mock_thread)
        mock_message.create_thread = MagicMock(return_value=_f)

        await thread_handler._create_thread_and_respond(mock_message)

        # 最初の文のみが使用されることを確認
        call_args = mock_message.create_thread.call_args
        thread_name = call_args.kwargs["name"]
        assert "。" not in thread_name or thread_name.endswith("。")
        assert "最初の文" in thread_name

    @pytest.mark.asyncio
    async def test_thread_name_only_whitespace(self, thread_handler):
        """空白のみの場合、デフォルト名が使用される."""
        mock_message = MagicMock(spec=discord.Message)
        mock_message.content = "   \n\t  "
        mock_message.mentions = []
        mock_message.thread = None
        mock_message.reply = AsyncMock()
        mock_message.channel = MagicMock()
        mock_message.channel.id = 111222333
        mock_message.author = MagicMock()
        mock_message.author.id = 987654321

        mock_thread = MagicMock(spec=discord.Thread)
        mock_thread.id = 444555666
        mock_thread.guild = MagicMock()
        mock_thread.guild.id = 111222333
        # typing()は非同期コンテキストマネージャーとして動作する
        typing_context = AsyncMock()
        typing_context.__aenter__ = AsyncMock(return_value=None)
        typing_context.__aexit__ = AsyncMock(return_value=None)
        mock_thread.typing = MagicMock(return_value=typing_context)
        mock_thread.send = AsyncMock()
        _f = asyncio.Future()
        _f.set_result(mock_thread)
        mock_message.create_thread = MagicMock(return_value=_f)

        await thread_handler._create_thread_and_respond(mock_message)

        # デフォルト名「会話」が使用されることを確認
        call_args = mock_message.create_thread.call_args
        assert call_args.kwargs["name"] == "会話"

    @pytest.mark.asyncio
    async def test_thread_name_none_content(self, thread_handler):
        """message.content が None の場合、デフォルト名が使用される."""
        mock_message = MagicMock(spec=discord.Message)
        mock_message.content = None
        mock_message.mentions = []
        mock_message.thread = None
        mock_message.reply = AsyncMock()
        mock_message.channel = MagicMock()
        mock_message.channel.id = 111222333
        mock_message.author = MagicMock()
        mock_message.author.id = 987654321

        mock_thread = MagicMock(spec=discord.Thread)
        mock_thread.id = 444555666
        mock_thread.guild = MagicMock()
        mock_thread.guild.id = 111222333
        # typing()は非同期コンテキストマネージャーとして動作する
        typing_context = AsyncMock()
        typing_context.__aenter__ = AsyncMock(return_value=None)
        typing_context.__aexit__ = AsyncMock(return_value=None)
        mock_thread.typing = MagicMock(return_value=typing_context)
        mock_thread.send = AsyncMock()
        _f = asyncio.Future()
        _f.set_result(mock_thread)
        mock_message.create_thread = MagicMock(return_value=_f)

        await thread_handler._create_thread_and_respond(mock_message)

        # デフォルト名「会話」が使用されることを確認
        call_args = mock_message.create_thread.call_args
        assert call_args.kwargs["name"] == "会話"


class TestThreadCreationErrorHandling:
    """スレッド作成エラーハンドリングのテスト."""

    @pytest.mark.asyncio
    async def test_thread_creation_fetch_message_error(self, thread_handler):
        """メッセージ再取得でエラーが発生した場合."""
        mock_message = MagicMock(spec=discord.Message)
        mock_message.content = "テスト"
        mock_message.mentions = []
        mock_message.thread = None
        mock_message.create_thread = AsyncMock(
            side_effect=discord.errors.HTTPException(
                MagicMock(), {"code": 160004, "message": "Thread already exists"}
            )
        )
        mock_message.channel.fetch_message = AsyncMock(
            side_effect=Exception("Fetch error")
        )
        mock_message.reply = AsyncMock()

        result = await thread_handler._create_thread_and_respond(mock_message)

        # False が返されることを確認
        assert result is False
        # エラーメッセージが送信されることを確認
        mock_message.reply.assert_called_once()

    @pytest.mark.asyncio
    async def test_thread_creation_http_exception_other_code(self, thread_handler):
        """HTTPException の他のエラーコードの場合."""
        mock_message = MagicMock(spec=discord.Message)
        mock_message.content = "テスト"
        mock_message.mentions = []
        mock_message.thread = None
        mock_message.create_thread = AsyncMock(
            side_effect=discord.errors.HTTPException(
                MagicMock(), {"code": 50013, "message": "Missing permissions"}
            )
        )
        mock_message.reply = AsyncMock()

        result = await thread_handler._create_thread_and_respond(mock_message)

        # False が返されることを確認
        assert result is False
        # エラーメッセージが送信されることを確認
        mock_message.reply.assert_called_once()

    @pytest.mark.asyncio
    async def test_thread_creation_unexpected_error(self, thread_handler):
        """予期しないエラーが発生した場合."""
        mock_message = MagicMock(spec=discord.Message)
        mock_message.content = "テスト"
        mock_message.mentions = []
        mock_message.thread = None
        mock_message.create_thread = AsyncMock(side_effect=ValueError("Unexpected"))
        mock_message.reply = AsyncMock()

        result = await thread_handler._create_thread_and_respond(mock_message)

        # False が返されることを確認
        assert result is False
        # エラーメッセージが送信されることを確認
        mock_message.reply.assert_called_once()

    @pytest.mark.asyncio
    async def test_thread_creation_reply_error(self, thread_handler):
        """エラーメッセージ送信でエラーが発生した場合、例外が呼び出し元に伝播する."""
        mock_message = MagicMock(spec=discord.Message)
        mock_message.content = "テスト"
        mock_message.mentions = []
        mock_message.thread = None
        mock_message.create_thread = AsyncMock(side_effect=ValueError("Error"))
        mock_message.reply = AsyncMock(side_effect=Exception("Reply error"))

        # reply が失敗した場合は例外を握りつぶさず伝播する
        with pytest.raises(Exception, match="Reply error"):
            await thread_handler._create_thread_and_respond(mock_message)

        # エラー通知のため reply が呼ばれたことを確認
        mock_message.reply.assert_called_once()


class TestThreadMessageProcessingEdgeCases:
    """スレッドメッセージ処理のエッジケーステスト."""

    @pytest.mark.asyncio
    async def test_process_message_not_thread_type(self, thread_handler):
        """Thread 型でない場合、処理がスキップされる."""
        mock_message = MagicMock(spec=discord.Message)
        mock_message.channel = MagicMock()  # Thread 型ではない

        await thread_handler._process_message(mock_message)

        # セッション管理が呼ばれないことを確認
        thread_handler.session_manager.get_session.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_message_empty_response(self, thread_handler):
        """AI応答が空の場合."""
        mock_message = MagicMock(spec=discord.Message)
        mock_message.channel = MagicMock(spec=discord.Thread)
        mock_message.channel.id = 444555666
        mock_message.channel.typing = MagicMock(return_value=AsyncMock())
        mock_message.channel.send = AsyncMock()
        mock_message.reply = AsyncMock()
        mock_message.author = MagicMock()
        mock_message.author.id = 987654321
        mock_message.content = "テスト"

        session = ChatSession(
            session_key="thread:444555666",
            session_type="thread",
        )
        thread_handler.session_manager.get_session = AsyncMock(return_value=session)
        thread_handler.ai_provider.generate_response = AsyncMock(
            return_value=("", MagicMock())
        )

        await thread_handler._process_message(mock_message)

        # メッセージが追加されたことを確認
        thread_handler.session_manager.add_message.assert_called()
