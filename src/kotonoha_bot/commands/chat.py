"""チャットコマンド"""

import logging
from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands

from ..bot.handlers import MessageHandler

logger = logging.getLogger(__name__)


class ChatCommands(commands.Cog):
    """チャットコマンド"""

    def __init__(self, bot: commands.Bot, handler: MessageHandler):
        self.bot = bot
        self.handler = handler

    @app_commands.command(name="reset", description="会話履歴をリセットします")
    async def chat_reset(self, interaction: discord.Interaction):
        """会話履歴をリセット

        Args:
            interaction: Discord インタラクション
        """
        await interaction.response.defer(ephemeral=True)

        try:
            # セッションキーを決定
            if isinstance(interaction.channel, discord.Thread):
                session_key = f"thread:{interaction.channel.id}"
            elif isinstance(interaction.channel, discord.DMChannel):
                session_key = f"dm:{interaction.channel.id}"
            else:
                session_key = f"mention:{interaction.user.id}"

            # セッションを取得
            session = await self.handler.session_manager.get_session(session_key)
            if not session:
                await interaction.followup.send(
                    "会話履歴が見つかりませんでした。", ephemeral=True
                )
                return

            # 会話履歴をクリア（messagesリストを空にする）
            session.messages.clear()
            session.last_active_at = datetime.now()  # 最終アクセス時刻を更新
            session.last_archived_message_index = 0  # アーカイブインデックスもリセット
            await self.handler.session_manager.save_session(session_key)

            await interaction.followup.send(
                "会話履歴をリセットしました。新しい会話として始めましょう。",
                ephemeral=True,
            )

        except Exception as e:
            logger.exception(f"Error in /chat reset: {e}")
            await interaction.followup.send(
                "会話履歴のリセットに失敗しました。", ephemeral=True
            )

    @app_commands.command(name="status", description="セッション状態を表示します")
    async def chat_status(self, interaction: discord.Interaction):
        """セッション状態を表示

        Args:
            interaction: Discord インタラクション
        """
        await interaction.response.defer(ephemeral=True)

        try:
            # セッションキーを決定
            if isinstance(interaction.channel, discord.Thread):
                session_key = f"thread:{interaction.channel.id}"
                session_type = "スレッド型"
            elif isinstance(interaction.channel, discord.DMChannel):
                session_key = f"dm:{interaction.channel.id}"
                session_type = "DM型"
            else:
                session_key = f"mention:{interaction.user.id}"
                session_type = "メンション応答型"

            # セッションを取得
            session = await self.handler.session_manager.get_session(session_key)
            if not session:
                await interaction.followup.send(
                    "セッションが見つかりませんでした。", ephemeral=True
                )
                return

            # セッション情報を取得
            history = session.get_conversation_history()
            message_count = len(history)
            start_time = session.created_at.strftime("%Y-%m-%d %H:%M:%S")

            # 応答を送信
            await interaction.followup.send(
                f"現在のセッション情報:\n"
                f"- タイプ: {session_type}\n"
                f"- 会話履歴: {message_count}件\n"
                f"- 開始時刻: {start_time}",
                ephemeral=True,
            )

        except Exception as e:
            logger.exception(f"Error in /chat status: {e}")
            await interaction.followup.send(
                "セッション状態の取得に失敗しました。", ephemeral=True
            )


async def setup(bot: commands.Bot, handler: MessageHandler):
    """コマンドを登録

    Args:
        bot: Discord Bot（KotonohaBot）
        handler: メッセージハンドラー
    """
    await bot.add_cog(ChatCommands(bot, handler))
    # スラッシュコマンドの同期は on_ready イベント内で実行する
    # （bot.start() が呼ばれる前に application_id が設定されていないため）
    logger.info("Chat commands registered")
