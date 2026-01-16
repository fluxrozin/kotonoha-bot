"""聞き耳型: LLM 判断機能"""

import hashlib
import logging
from datetime import datetime, timedelta
from pathlib import Path

import discord

from ..ai.litellm_provider import LiteLLMProvider
from ..ai.prompts import DEFAULT_SYSTEM_PROMPT
from ..config import Config
from ..session.manager import SessionManager
from ..session.models import Message, MessageRole

logger = logging.getLogger(__name__)


def _load_prompt_from_markdown(filename: str) -> str:
    """Markdownファイルからプロンプトを読み込む

    Args:
        filename: 読み込むMarkdownファイル名

    Returns:
        プロンプトテキスト（Markdownの見出しを除く）
    """
    # プロジェクトルートの prompts/ フォルダから読み込む
    # このファイルから見て、プロジェクトルートは src/kotonoha_bot/eavesdrop/ の3階層上
    project_root = Path(__file__).parent.parent.parent.parent
    prompts_dir = project_root / "prompts"
    md_file = prompts_dir / filename

    if not md_file.exists():
        raise FileNotFoundError(f"Prompt file not found: {md_file}")

    content = md_file.read_text(encoding="utf-8")

    # Markdownの見出し（# で始まる行）を除去
    lines = content.split("\n")
    # 最初の見出し行をスキップ
    if lines and lines[0].startswith("#"):
        lines = lines[1:]

    # 先頭と末尾の空行を除去
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()

    return "\n".join(lines)


# プロンプトテンプレート（Markdownファイルから読み込む）
JUDGE_PROMPT_TEMPLATE = _load_prompt_from_markdown("eavesdrop_judge_prompt.md")
RESPONSE_PROMPT_TEMPLATE = _load_prompt_from_markdown("eavesdrop_response_prompt.md")
SAME_CONVERSATION_PROMPT_TEMPLATE = _load_prompt_from_markdown(
    "eavesdrop_same_conversation_prompt.md"
)
CONVERSATION_STATE_PROMPT_TEMPLATE = _load_prompt_from_markdown(
    "eavesdrop_conversation_state_prompt.md"
)
CONVERSATION_SITUATION_CHANGED_PROMPT_TEMPLATE = _load_prompt_from_markdown(
    "eavesdrop_conversation_situation_changed_prompt.md"
)


class LLMJudge:
    """LLM 判断機能（アプローチ 1）

    会話ログを読み取り、LLM に「今、発言すべきか？」を判定させる。
    """

    def __init__(self, session_manager: SessionManager, ai_provider: LiteLLMProvider):
        self.session_manager = session_manager
        self.ai_provider = ai_provider
        # 判定用の軽量モデル（Gemini Flash など）
        self.judge_model = Config.EAVESDROP_JUDGE_MODEL
        # 応答生成用の通常モデル
        self.response_model = None  # デフォルトモデルを使用
        # 介入履歴の追跡（チャンネルごと）
        # キー: チャンネルID, 値: (介入時刻, 介入時の会話ログ)のリスト
        self.intervention_history: dict[int, list[tuple[datetime, str]]] = {}
        # 同じ会話判定のキャッシュ（トークン消費を削減）
        # キー: (チャンネルID, 会話ログのハッシュ), 値: (判定結果, キャッシュ時刻)
        self.conversation_check_cache: dict[tuple[int, str], tuple[bool, datetime]] = {}
        # キャッシュの有効期限（分）
        self.cache_ttl_minutes = 5

    async def should_respond(
        self, channel_id: int, recent_messages: list[discord.Message]
    ) -> bool:
        """発言すべきか判定

        Args:
            channel_id: チャンネル ID
            recent_messages: 直近のメッセージリスト（10〜20 件）

        Returns:
            発言すべき場合 True
        """
        if not recent_messages:
            return False

        # 会話の状態を判定（終了しようとしている場合は介入しない）
        conversation_state = await self._analyze_conversation_state(recent_messages)
        if conversation_state == "ending":
            logger.debug(
                f"Intervention blocked for channel {channel_id}: conversation is ending"
            )
            return False

        # 介入履歴がある場合、会話状況が変わったかをチェック
        if channel_id in self.intervention_history:
            has_changed = await self._has_conversation_changed_after_intervention(
                channel_id, recent_messages
            )
            if not has_changed:
                logger.debug(
                    f"Intervention blocked for channel {channel_id}: "
                    "conversation situation has not changed after last intervention"
                )
                return False

        # 介入履歴を取得（LLM判定に渡すため）
        intervention_context = self._get_intervention_context(channel_id)

        # 会話ログをフォーマット
        conversation_log = self._format_conversation_log(recent_messages)

        # 重要な前提: Discordの参加者は全て当事者である
        # 「店側やイベントを受ける側のスタッフ」という表現が含まれていても、
        # それは参加者が店舗スタッフの立場を代弁しているか、
        # 店舗スタッフからの注意を転記・共有しているだけの可能性がある
        # このような場合は、参加者間の会話として扱い、LLM判定に任せる

        # 会話の状態を判定（LLM判定を使用）
        # 場が荒れている、誤解が発生しているなどの状態を検出
        conversation_state = await self._analyze_conversation_state(recent_messages)
        if conversation_state in ("conflict", "misunderstanding"):
            logger.debug(
                f"Conversation state detected: {conversation_state}, "
                "proceeding to LLM judgment"
            )
            # LLM判定に任せる（場が荒れている、誤解が発生している可能性があるため）

        # 判定用プロンプト（介入履歴の情報も含める）
        judge_prompt = self._create_judge_prompt(conversation_log, intervention_context)

        try:
            # 判定用 AI に問い合わせ（軽量モデルを使用）
            judge_message = Message(role=MessageRole.USER, content=judge_prompt)
            response = await self.ai_provider.generate_response(
                messages=[judge_message],
                system_prompt="",
                model=self.judge_model,
                max_tokens=50,  # 会話の雰囲気を理解するため、少し余裕を持たせる
            )

            # 応答を解析
            response_upper = response.strip().upper()
            should_respond = response_upper.startswith("YES")

            if should_respond:
                logger.debug("LLM judge determined that response is needed")
                # 介入を記録（会話ログも保存）
                self._record_intervention(channel_id, recent_messages)
            else:
                logger.debug("LLM judge determined that response is not needed")

            return should_respond

        except Exception as e:
            logger.error(f"Error in judge phase: {e}")
            return False

    async def generate_response(
        self, channel_id: int, recent_messages: list[discord.Message]
    ) -> str | None:
        """応答を生成

        Args:
            channel_id: チャンネル ID（should_respond に渡すため必要）
            recent_messages: 直近のメッセージリスト

        Returns:
            生成された応答（発言しない場合は None）
        """
        # 判定フェーズ
        should_respond = await self.should_respond(channel_id, recent_messages)
        if not should_respond:
            return None

        # 発言生成フェーズ
        conversation_log = self._format_conversation_log(recent_messages)
        response_prompt = self._create_response_prompt(conversation_log)

        try:
            # 通常の AI で応答を生成
            response_message = Message(role=MessageRole.USER, content=response_prompt)
            response = await self.ai_provider.generate_response(
                messages=[response_message],
                system_prompt=DEFAULT_SYSTEM_PROMPT,
                model=self.response_model,  # デフォルトモデル
            )

            return response

        except Exception as e:
            logger.error(f"Error in response generation phase: {e}")
            return None

    def _get_intervention_context(self, channel_id: int) -> str | None:
        """介入履歴の情報を取得（LLM判定に渡すため）

        Args:
            channel_id: チャンネル ID

        Returns:
            介入履歴の情報（文字列）、履歴がない場合は None
        """
        now = datetime.now()

        # チャンネルの介入履歴を取得
        if channel_id not in self.intervention_history:
            return None

        history = self.intervention_history[channel_id]

        # 古い履歴を削除（一定時間以上前の介入は無視）
        cutoff_time = now - timedelta(hours=1)
        history[:] = [(t, log) for t, log in history if t > cutoff_time]

        if not history:
            return None

        # 最後の介入を取得
        last_intervention_time, last_intervention_log = max(history, key=lambda x: x[0])

        # 最後の介入からの経過時間を計算
        time_since_last = now - last_intervention_time
        minutes_since_last = int(time_since_last.total_seconds() / 60)

        # 30分以内の介入回数をカウント
        recent_interventions = [
            (t, log) for t, log in history if t > now - timedelta(minutes=30)
        ]
        intervention_count = len(recent_interventions)

        # 介入履歴の情報をフォーマット
        context = (
            f"【介入履歴】\n"
            f"- 最後の介入から {minutes_since_last} 分経過\n"
            f"- 30分以内の介入回数: {intervention_count} 回\n"
            f"- 最後の介入時の会話（参考）:\n{last_intervention_log[:200]}..."
        )

        return context

    async def _is_same_conversation(
        self,
        previous_log: str,
        current_log: str,
        cache_key: tuple[int, str] | None = None,
    ) -> bool:
        """LLMで「同じ会話かどうか」を判定

        Args:
            previous_log: 前回の介入時の会話ログ
            current_log: 現在の会話ログ
            cache_key: キャッシュキー（結果をキャッシュする場合）

        Returns:
            同じ会話の場合 True
        """
        if not previous_log or not current_log:
            return False

        # 判定用プロンプトを作成
        prompt = SAME_CONVERSATION_PROMPT_TEMPLATE.format(
            previous_conversation=previous_log,
            current_conversation=current_log,
        )

        try:
            # 判定用 AI に問い合わせ（軽量モデルを使用）
            judge_message = Message(role=MessageRole.USER, content=prompt)
            response = await self.ai_provider.generate_response(
                messages=[judge_message],
                system_prompt="",
                model=self.judge_model,
                max_tokens=20,  # SAME/DIFFERENT のみなので短く
            )

            # 応答を解析
            response_upper = response.strip().upper()
            is_same = response_upper.startswith("SAME")

            logger.debug(
                f"Same conversation check: {is_same} (response: {response_upper[:20]})"
            )

            # 結果をキャッシュ（トークン消費を削減）
            if cache_key:
                now = datetime.now()
                self.conversation_check_cache[cache_key] = (is_same, now)
                # 古いキャッシュを削除
                self._cleanup_cache(now)

            return is_same

        except Exception as e:
            logger.error(f"Error in same conversation check: {e}")
            # エラー時は安全側に倒して、同じ会話として扱う（介入回数をチェック）
            return True

    def _cleanup_cache(self, now: datetime) -> None:
        """古いキャッシュを削除

        Args:
            now: 現在時刻
        """
        cutoff_time = now - timedelta(minutes=self.cache_ttl_minutes * 2)
        keys_to_delete = [
            key
            for key, (_, cached_time) in self.conversation_check_cache.items()
            if cached_time < cutoff_time
        ]
        for key in keys_to_delete:
            del self.conversation_check_cache[key]

    async def _has_conversation_changed_after_intervention(
        self, channel_id: int, recent_messages: list[discord.Message]
    ) -> bool:
        """介入後の会話状況が変わったか判定

        Args:
            channel_id: チャンネル ID
            recent_messages: 直近のメッセージリスト

        Returns:
            会話状況が変わった場合 True
        """
        # 介入履歴がない場合は、変化があったとみなす（初回介入）
        if channel_id not in self.intervention_history:
            return True

        history = self.intervention_history[channel_id]
        if not history:
            return True

        # 最後の介入を取得
        last_intervention_time, last_intervention_log = max(history, key=lambda x: x[0])

        # 最後の介入からの経過時間を計算
        now = datetime.now()
        time_since_last = now - last_intervention_time
        minutes_since_last = int(time_since_last.total_seconds() / 60)

        # 最小間隔（設定から読み込む）
        min_interval_minutes = Config.EAVESDROP_MIN_INTERVENTION_INTERVAL_MINUTES
        if minutes_since_last < min_interval_minutes:
            logger.debug(
                f"Intervention blocked: minimum interval not met "
                f"({minutes_since_last} < {min_interval_minutes} minutes)"
            )
            return False

        # 現在の会話ログを取得（最新の5メッセージ）
        current_log = self._format_conversation_log(recent_messages[-5:])

        # 同じ会話かどうかを判定
        is_same = await self._is_same_conversation(
            previous_log=last_intervention_log,
            current_log=current_log,
            cache_key=(channel_id, hashlib.md5(current_log.encode()).hexdigest()),
        )

        if is_same:
            # 同じ会話の場合、会話の状況が変わったかをLLM判定で確認
            return await self._check_conversation_situation_changed(
                last_intervention_log=last_intervention_log, current_log=current_log
            )

        # 別の会話の場合は、変化があったとみなす
        return True

    async def _check_conversation_situation_changed(
        self, last_intervention_log: str, current_log: str
    ) -> bool:
        """会話の状況が変わったか判定（LLM判定）

        Args:
            last_intervention_log: 前回の介入時の会話ログ
            current_log: 現在の会話ログ

        Returns:
            会話状況が変わった場合 True
        """
        # プロンプトファイルから読み込む
        prompt = CONVERSATION_SITUATION_CHANGED_PROMPT_TEMPLATE.format(
            last_intervention_log=last_intervention_log,
            current_log=current_log,
        )

        try:
            # 判定用 AI に問い合わせ（軽量モデルを使用）
            judge_message = Message(role=MessageRole.USER, content=prompt)
            response = await self.ai_provider.generate_response(
                messages=[judge_message],
                system_prompt="",
                model=self.judge_model,
                max_tokens=20,  # CHANGED/UNCHANGED のみなので短く
            )

            # 応答を解析
            response_upper = response.strip().upper()
            has_changed = response_upper.startswith("CHANGED")

            logger.debug(
                f"Conversation situation changed check: {has_changed} "
                f"(response: {response_upper[:20]})"
            )

            return has_changed

        except Exception as e:
            logger.error(f"Error in conversation situation changed check: {e}")
            # エラー時は安全側に倒して、変化があったとみなす（介入を許可）
            return True

    async def _analyze_conversation_state(
        self, recent_messages: list[discord.Message]
    ) -> str:
        """会話の状態を分析（LLM判定を使用）

        Args:
            recent_messages: 直近のメッセージリスト

        Returns:
            会話の状態（"active", "ending", "misunderstanding", "conflict"）
        """
        if not recent_messages:
            return "active"

        # 会話ログをフォーマット（全体）
        # 会話ログの最後に最新のメッセージが含まれるため、LLMが優先的に確認できる
        conversation_log = self._format_conversation_log(recent_messages)

        # 判定用プロンプトを作成（最新のメッセージを強調）
        # プロンプトテンプレートは最新のメッセージを直接含めないが、
        # 会話ログの最後に最新のメッセージが含まれるため、LLMが優先的に確認できる
        state_prompt = CONVERSATION_STATE_PROMPT_TEMPLATE.format(
            conversation_log=conversation_log
        )

        try:
            # 判定用 AI に問い合わせ（軽量モデルを使用）
            judge_message = Message(role=MessageRole.USER, content=state_prompt)
            response = await self.ai_provider.generate_response(
                messages=[judge_message],
                system_prompt="",
                model=self.judge_model,
                max_tokens=20,  # ENDING/MISUNDERSTANDING/CONFLICT/ACTIVE のみなので短く
            )

            # 応答を解析
            response_upper = response.strip().upper()

            # 状態を判定
            if response_upper.startswith("ENDING"):
                return "ending"
            elif response_upper.startswith("MISUNDERSTANDING"):
                return "misunderstanding"
            elif response_upper.startswith("CONFLICT"):
                return "conflict"
            else:
                # デフォルトは active
                return "active"

        except Exception as e:
            logger.error(f"Error in conversation state analysis: {e}")
            # エラー時は安全側に倒して、active として扱う
            return "active"

    def _record_intervention(
        self, channel_id: int, recent_messages: list[discord.Message]
    ) -> None:
        """介入を記録

        Args:
            channel_id: チャンネル ID
            recent_messages: 直近のメッセージリスト（介入時の会話ログを保存）
        """
        now = datetime.now()
        if channel_id not in self.intervention_history:
            self.intervention_history[channel_id] = []

        # 介入時の会話ログを保存（最新の5メッセージ）
        conversation_log = self._format_conversation_log(recent_messages[-5:])
        self.intervention_history[channel_id].append((now, conversation_log))

        # 履歴が長くなりすぎないように、古い履歴を削除
        cutoff_time = now - timedelta(hours=1)
        self.intervention_history[channel_id] = [
            (t, log)
            for t, log in self.intervention_history[channel_id]
            if t > cutoff_time
        ]

    def _format_conversation_log(self, messages: list[discord.Message]) -> str:
        """会話ログをフォーマット

        Args:
            messages: メッセージリスト

        Returns:
            フォーマットされた会話ログ
        """
        log_lines = []
        for msg in messages:
            author_name = msg.author.display_name
            content = msg.content
            log_lines.append(f"{author_name}: {content}")

        return "\n".join(log_lines)

    def _create_judge_prompt(
        self, conversation_log: str, intervention_context: str | None = None
    ) -> str:
        """判定用プロンプトを作成

        Args:
            conversation_log: 会話ログ
            intervention_context: 介入履歴の情報（既に介入している場合）

        Returns:
            判定用プロンプト
        """
        # 介入履歴がない場合は空文字列
        context_str = intervention_context if intervention_context else ""

        return JUDGE_PROMPT_TEMPLATE.format(
            conversation_log=conversation_log,
            intervention_context=context_str,
        )

    def _create_response_prompt(self, conversation_log: str) -> str:
        """応答生成用プロンプトを作成

        Args:
            conversation_log: 会話ログ

        Returns:
            応答生成用プロンプト
        """
        return RESPONSE_PROMPT_TEMPLATE.format(conversation_log=conversation_log)
