"""聞き耳型応答ハンドラー。."""

import asyncio
import logging

import discord

from kotonoha_bot.bot.client import KotonohaBot
from kotonoha_bot.bot.router import MessageRouter
from kotonoha_bot.config import Config
from kotonoha_bot.db.models import MessageRole
from kotonoha_bot.rate_limit.request_queue import RequestPriority, RequestQueue
from kotonoha_bot.services.ai import AIProvider
from kotonoha_bot.services.eavesdrop import ConversationBuffer, LLMJudge
from kotonoha_bot.services.session import SessionManager
from kotonoha_bot.utils.message import (
    create_response_embed,
    format_split_messages,
    split_message,
)

logger = logging.getLogger(__name__)


class EavesdropHandler:
    """聞き耳型応答ハンドラー."""

    def __init__(
        self,
        bot: KotonohaBot,
        session_manager: SessionManager,
        ai_provider: AIProvider,
        llm_judge: LLMJudge,
        buffer: ConversationBuffer,
        router: MessageRouter,
        request_queue: RequestQueue,
        config: Config | None = None,
    ):
        """EavesdropHandler を初期化.

        Args:
            bot: Discord クライアント
            session_manager: セッションマネージャー
            ai_provider: AIプロバイダー
            llm_judge: LLM判定
            buffer: 会話バッファ
            router: メッセージルーター
            request_queue: リクエストキュー
            config: 設定インスタンス（省略可）
        """
        self.bot = bot
        self.session_manager = session_manager
        self.ai_provider = ai_provider
        self.llm_judge = llm_judge
        self.conversation_buffer = buffer
        self.router = router
        self.request_queue = request_queue
        self.config = config

    async def handle(self, message: discord.Message) -> None:
        """聞き耳型の処理（リクエストキューに追加）.

        Args:
            message: Discord メッセージ
        """
        # Bot自身のメッセージは無視
        if message.author.bot:
            return

        # 聞き耳型が有効なチャンネルか確認
        if message.channel.id not in self.router.eavesdrop_enabled_channels:
            return

        logger.debug(f"Eavesdrop message from {message.author} in {message.channel}")

        # リクエストキューに追加（優先度: EAVESDROP - 最高優先度）
        try:
            future = await self.request_queue.enqueue(
                RequestPriority.EAVESDROP,
                self._process,
                message,
            )
            # 結果を待機（エラーハンドリングは内部で行う）
            await future
        except Exception as e:
            logger.exception(f"Error enqueuing eavesdrop request: {e}")
            # キューが満杯などの場合のフォールバック
            try:
                await self._process(message)
            except Exception as inner_e:
                logger.exception(f"Error in fallback eavesdrop processing: {inner_e}")

    async def _process(self, message: discord.Message) -> None:
        """聞き耳型処理の実装.

        Args:
            message: Discord メッセージ
        """
        try:
            # 会話ログに追加
            self.conversation_buffer.add_message(message.channel.id, message)

            # 直近のメッセージを取得
            recent_messages = self.conversation_buffer.get_recent_messages(
                message.channel.id,
                limit=self.config.EAVESDROP_BUFFER_SIZE if self.config else 20,
            )

            # 聞き耳型は会話の流れを理解するため、最低限のメッセージ数が必要
            min_messages = self.config.EAVESDROP_MIN_MESSAGES if self.config else 3
            if len(recent_messages) < min_messages:
                logger.debug(
                    f"Not enough messages for eavesdrop (got {len(recent_messages)}, "
                    f"need {min_messages})"
                )
                return

            # LLM 判断機能を呼び出し
            response_text = await self.llm_judge.generate_response(
                message.channel.id, recent_messages
            )

            # 応答がある場合のみ投稿
            if response_text:
                # セッションキーを生成
                session_key = f"eavesdrop:{message.channel.id}"

                # セッションを取得または作成
                session = await self.session_manager.get_session(session_key)
                if not session:
                    # ⚠️ 重要: guild_id は Discord URL生成に必要
                    guild_id = message.guild.id if message.guild else None
                    session = await self.session_manager.create_session(
                        session_key=session_key,
                        session_type="eavesdrop",
                        guild_id=guild_id,
                        channel_id=message.channel.id,
                    )
                    logger.info(f"Created new eavesdrop session: {session_key}")

                # アシスタントメッセージを追加
                await self.session_manager.add_message(
                    session_key=session_key,
                    role=MessageRole.ASSISTANT,
                    content=response_text,
                )

                # セッションを保存
                await self.session_manager.save_session(session_key)

                # メインチャンネルに直接投稿（メッセージ分割対応）
                response_chunks = split_message(response_text)
                formatted_chunks = format_split_messages(
                    response_chunks, len(response_chunks)
                )

                # 使用モデル名とレート制限使用率を取得
                model_name = self.ai_provider.get_last_used_model()
                rate_limit_usage = self.ai_provider.get_rate_limit_usage()

                # 最初のメッセージを送信（フッター付き）
                if formatted_chunks:
                    # 最初のメッセージのみEmbedで送信（フッター付き）
                    embed = create_response_embed(
                        formatted_chunks[0], model_name, rate_limit_usage
                    )
                    await message.channel.send(embed=embed)

                    # 残りのメッセージは順次送信
                    for chunk in formatted_chunks[1:]:
                        await message.channel.send(chunk)
                        await asyncio.sleep(0.5)

                logger.info(f"Sent eavesdrop response in channel: {message.channel.id}")

        except Exception as e:
            logger.exception(f"Error handling eavesdrop: {e}")
            # 聞き耳型ではエラーメッセージを送信しない（自然な会話参加のため）
