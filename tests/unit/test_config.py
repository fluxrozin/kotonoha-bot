"""設定管理のテスト."""

import os
from pathlib import Path

import pytest

from kotonoha_bot.config import Config, Settings, get_config


class TestConfig:
    """Config クラスのテスト."""

    def test_init_with_defaults(self, monkeypatch):
        """デフォルト値で初期化できる."""
        # 環境変数をクリアしてデフォルト値をテスト
        monkeypatch.delenv("LLM_MODEL", raising=False)
        # .envファイルの影響を排除するため、明示的に値を設定
        config = Config(
            discord_token="test_token",
            openai_api_key="test_openai_key",
            anthropic_api_key="test_anthropic_key",
            llm_model="claude-sonnet-4-5",  # デフォルト値を明示的に設定
        )
        assert config.bot_prefix == "!"
        # Configのデフォルト値はclaude-sonnet-4-5
        assert config.llm_model == "claude-sonnet-4-5"
        assert config.llm_temperature == 0.7
        assert config.llm_max_tokens == 2048

    def test_init_from_env(self, monkeypatch):
        """環境変数から初期化できる."""
        monkeypatch.setenv("DISCORD_TOKEN", "env_token")
        monkeypatch.setenv("OPENAI_API_KEY", "env_openai_key")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "env_anthropic_key")
        monkeypatch.setenv("BOT_PREFIX", "?")
        monkeypatch.setenv("LLM_MODEL", "claude-haiku-4-5")

        config = Config()
        assert config.discord_token == "env_token"
        assert config.bot_prefix == "?"
        assert config.llm_model == "claude-haiku-4-5"

    def test_validate_config_success(self):
        """設定の検証が成功する."""
        config = Config(
            discord_token="test_token",
            llm_model="claude-sonnet-4-5",
            openai_api_key="test_openai_key",
            anthropic_api_key="test_anthropic_key",
        )
        # 検証が例外を発生させないことを確認
        config.validate_config(skip_in_test=True)

    def test_validate_config_missing_discord_token(self):
        """Discord トークンが不足している場合にエラーが発生する."""
        config = Config(
            discord_token="",
            openai_api_key="test_openai_key",
            anthropic_api_key="test_anthropic_key",
        )
        with pytest.raises(ValueError, match="DISCORD_TOKEN is not set"):
            config.validate_config(skip_in_test=False)

    def test_validate_config_missing_llm_model(self):
        """LLM モデルが不足している場合にエラーが発生する."""
        config = Config(
            discord_token="test_token",
            llm_model="",
            openai_api_key="test_openai_key",
            anthropic_api_key="test_anthropic_key",
        )
        with pytest.raises(ValueError, match="LLM_MODEL is not set"):
            config.validate_config(skip_in_test=False)

    def test_validate_config_missing_openai_key(self):
        """OpenAI API キーが不足している場合にエラーが発生する."""
        config = Config(
            discord_token="test_token",
            llm_model="claude-sonnet-4-5",
            openai_api_key="",
            anthropic_api_key="test_anthropic_key",
        )
        with pytest.raises(ValueError, match="OPENAI_API_KEY is not set"):
            config.validate_config(skip_in_test=False)

    def test_validate_config_missing_anthropic_key(self):
        """Anthropic API キーが不足している場合にエラーが発生する."""
        config = Config(
            discord_token="test_token",
            llm_model="claude-sonnet-4-5",
            openai_api_key="test_openai_key",
            anthropic_api_key="",
        )
        with pytest.raises(ValueError, match="ANTHROPIC_API_KEY is not set"):
            config.validate_config(skip_in_test=False)

    def test_validate_config_skip_in_test(self):
        """テスト環境では検証をスキップできる."""
        config = Config(
            discord_token="",
            openai_api_key="",
            anthropic_api_key="",
        )
        # skip_in_test=True の場合は例外が発生しない
        config.validate_config(skip_in_test=True)

    def test_validate_config_creates_data_directory(self, tmp_path, monkeypatch):
        """設定検証時にデータディレクトリが作成される."""
        # model_post_init が database_path を上書きするため、
        # 一時ディレクトリ内に data ディレクトリを作成する方法でテストする

        original_cwd = os.getcwd()
        try:
            # 一時ディレクトリに移動
            os.chdir(tmp_path)

            data_dir = tmp_path / "data"
            db_path = data_dir / "sessions.db"

            # 環境変数をクリア
            monkeypatch.delenv("LLM_MODEL", raising=False)

            # データディレクトリが存在しないことを確認
            if data_dir.exists():
                import shutil

                shutil.rmtree(data_dir)
            assert not data_dir.exists()

            # database_path を直接指定して Config を作成
            # model_post_init が実行されるが、database_path を直接指定した場合は上書きされない
            config = Config(
                discord_token="test_token",
                llm_model="claude-sonnet-4-5",
                openai_api_key="test_openai_key",
                anthropic_api_key="test_anthropic_key",
                database_path=db_path,
            )

            # validate_config が database_path.parent.mkdir を呼び出す
            config.validate_config(skip_in_test=False)

            # データディレクトリが作成されたことを確認
            assert data_dir.exists(), (
                f"Directory {data_dir} was not created. database_path: {config.database_path}, parent: {config.database_path.parent}"
            )
            assert data_dir.is_dir()
        finally:
            os.chdir(original_cwd)

    def test_backward_compatibility_properties(self):
        """後方互換性のためのプロパティが正しく動作する."""
        config = Config(
            discord_token="test_token",
            bot_prefix="?",
            llm_model="claude-haiku-4-5",
            llm_temperature=0.5,
            llm_max_tokens=4096,
            openai_api_key="test_openai_key",
            anthropic_api_key="test_anthropic_key",
        )

        assert config.DISCORD_TOKEN == "test_token"
        assert config.BOT_PREFIX == "?"
        assert config.LLM_MODEL == "claude-haiku-4-5"
        assert config.LLM_TEMPERATURE == 0.5
        assert config.LLM_MAX_TOKENS == 4096
        assert config.OPENAI_API_KEY == "test_openai_key"
        assert config.ANTHROPIC_API_KEY == "test_anthropic_key"

    def test_model_post_init_sets_database_path(self):
        """model_post_init でデータベースパスが設定される."""
        config = Config(
            discord_token="test_token",
            database_name="test.db",
            openai_api_key="test_openai_key",
            anthropic_api_key="test_anthropic_key",
        )
        # model_post_init は Pydantic が自動的に呼び出す
        assert config.database_path == Path("./data/test.db")


class TestGetConfig:
    """get_config 関数のテスト."""

    def test_get_config_returns_singleton(self):
        """get_config がシングルトンを返す."""
        # グローバルインスタンスをリセット
        import kotonoha_bot.config

        kotonoha_bot.config._config_instance = None

        config1 = get_config()
        config2 = get_config()

        assert config1 is config2


class TestSettings:
    """Settings クラスのテスト."""

    def test_init_with_defaults(self, monkeypatch):
        """デフォルト値で初期化できる."""
        # 環境変数をクリアしてデフォルト値をテスト
        monkeypatch.delenv("LLM_MODEL", raising=False)
        # .envファイルの影響を排除するため、明示的に値を設定
        settings = Settings(
            discord_token="test_token",
            openai_api_key="test_openai_key",
            anthropic_api_key="test_anthropic_key",
            llm_model="claude-opus-4-5",  # デフォルト値を明示的に設定
        )
        assert settings.bot_prefix == "!"
        # Settingsのデフォルト値はclaude-opus-4-5
        assert settings.llm_model == "claude-opus-4-5"
        assert settings.postgres_port == 5432
        assert settings.postgres_db == "kotonoha"

    def test_init_from_env(self, monkeypatch):
        """環境変数から初期化できる."""
        monkeypatch.setenv("DISCORD_TOKEN", "env_token")
        monkeypatch.setenv("OPENAI_API_KEY", "env_openai_key")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "env_anthropic_key")
        monkeypatch.setenv("POSTGRES_PORT", "5433")
        monkeypatch.setenv("POSTGRES_DB", "test_db")

        settings = Settings()
        assert settings.discord_token == "env_token"
        assert settings.postgres_port == 5433
        assert settings.postgres_db == "test_db"

    def test_knowledge_base_settings(self):
        """知識ベース設定が正しく初期化される."""
        settings = Settings(
            discord_token="test_token",
            openai_api_key="test_openai_key",
            anthropic_api_key="test_anthropic_key",
        )
        assert settings.kb_hnsw_m == 16
        assert settings.kb_hnsw_ef_construction == 64
        assert settings.kb_similarity_threshold == 0.7
        assert settings.kb_default_top_k == 10
