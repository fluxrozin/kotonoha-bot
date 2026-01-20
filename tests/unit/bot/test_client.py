"""Bot クライアントのテスト."""

from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import discord
import pytest

from kotonoha_bot.bot.client import KotonohaBot
from kotonoha_bot.config import Config


@pytest.fixture
def mock_config():
    """モック設定."""
    config = MagicMock(spec=Config)
    config.BOT_PREFIX = "!"
    config.discord_token = "test_token"
    config.bot_prefix = "!"
    return config


@pytest.fixture
def bot(mock_config):
    """KotonohaBot インスタンス."""
    return KotonohaBot(config=mock_config)


class TestKotonohaBotInitialization:
    """KotonohaBot の初期化テスト."""

    def test_init_with_config(self, mock_config):
        """設定を指定して初期化できる."""
        bot = KotonohaBot(config=mock_config)
        assert bot.config == mock_config

    def test_init_without_config_raises_error(self):
        """設定なしで初期化するとエラーが発生する."""
        with pytest.raises(ValueError, match="config parameter is required"):
            KotonohaBot(config=None)

    def test_init_sets_intents(self, bot):
        """インテントが正しく設定される."""
        assert bot.intents.message_content is True
        assert bot.intents.messages is True
        assert bot.intents.guilds is True

    def test_init_sets_command_prefix(self, bot, mock_config):
        """コマンドプレフィックスが正しく設定される."""
        assert bot.command_prefix == mock_config.BOT_PREFIX

    def test_init_disables_help_command(self, bot):
        """デフォルトのhelpコマンドが無効化される."""
        assert bot.help_command is None


class TestKotonohaBotOnReady:
    """on_ready イベントのテスト."""

    @pytest.mark.asyncio
    async def test_on_ready_logs_user_info(self, bot):
        """on_ready でユーザー情報がログに記録される."""
        mock_user = MagicMock()
        mock_user.id = 123456789
        # __str__ メソッドを適切に設定（self は __str__ のシグネチャとして必要）
        mock_user.__str__ = lambda self: "TestBot#1234"  # noqa: ARG005

        # discord.py の Bot.user と guilds はプロパティなので、PropertyMock を使用
        mock_guilds = [MagicMock(), MagicMock()]
        bot.change_presence = AsyncMock()
        with (
            patch.object(
                type(bot), "user", new_callable=PropertyMock, return_value=mock_user
            ),
            patch.object(
                type(bot), "guilds", new_callable=PropertyMock, return_value=mock_guilds
            ),
            patch("kotonoha_bot.bot.client.logger") as mock_logger,
        ):
            await bot.on_ready()
            # ログ呼び出しを確認（順序は問わない）
            log_calls = [str(call) for call in mock_logger.info.call_args_list]
            logged_in_found = any(
                "Logged in as" in str(call) for call in mock_logger.info.call_args_list
            )
            connected_found = any(
                "Connected to 2 guilds" in str(call)
                for call in mock_logger.info.call_args_list
            )
            assert logged_in_found, f"Logged in message not found in calls: {log_calls}"
            assert connected_found, f"Connected message not found in calls: {log_calls}"

    @pytest.mark.asyncio
    async def test_on_ready_sets_presence(self, bot):
        """on_ready でステータスが設定される."""
        mock_user = MagicMock()
        mock_user.id = 123456789

        # discord.py の Bot.user と guilds はプロパティなので、PropertyMock を使用
        with (
            patch.object(
                type(bot), "user", new_callable=PropertyMock, return_value=mock_user
            ),
            patch.object(
                type(bot), "guilds", new_callable=PropertyMock, return_value=[]
            ),
        ):
            bot.change_presence = AsyncMock()

            await bot.on_ready()

            bot.change_presence.assert_called_once()
            call_args = bot.change_presence.call_args
            # activity が kwargs または args に含まれる
            if "activity" in call_args.kwargs:
                activity = call_args.kwargs["activity"]
            else:
                activity = call_args.args[0] if call_args.args else None
            assert activity is not None
            assert activity.type == discord.ActivityType.listening
            assert activity.name == "@メンション"

    @pytest.mark.asyncio
    async def test_on_ready_handles_none_user(self, bot):
        """on_ready でuserがNoneの場合にエラーログが記録される."""
        # user プロパティをモックで None を返すように設定
        # discord.py の Bot.user と guilds はプロパティなので、PropertyMock を使用
        with (
            patch.object(
                type(bot), "user", new_callable=PropertyMock, return_value=None
            ),
            patch.object(
                type(bot), "guilds", new_callable=PropertyMock, return_value=[]
            ),
        ):
            bot.change_presence = AsyncMock()

            with patch("kotonoha_bot.bot.client.logger") as mock_logger:
                await bot.on_ready()
                # エラーログが記録されることを確認
                mock_logger.error.assert_called_once_with(
                    "Bot user is None in on_ready event"
                )
                # change_presence は呼ばれない
                bot.change_presence.assert_not_called()


class TestKotonohaBotOnError:
    """on_error イベントのテスト."""

    @pytest.mark.asyncio
    async def test_on_error_logs_exception(self, bot):
        """on_error で例外がログに記録される."""
        event_method = "on_message"
        test_args = (MagicMock(),)
        test_kwargs = {"extra": "data"}

        with patch("kotonoha_bot.bot.client.logger") as mock_logger:
            await bot.on_error(event_method, *test_args, **test_kwargs)
            mock_logger.exception.assert_called_once_with(f"Error in {event_method}")
