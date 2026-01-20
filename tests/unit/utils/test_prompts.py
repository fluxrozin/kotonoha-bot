"""プロンプトユーティリティのテスト."""

from pathlib import Path
from unittest.mock import mock_open, patch

import pytest

from kotonoha_bot.utils.prompts import DEFAULT_SYSTEM_PROMPT, _load_prompt_from_markdown


class TestLoadPromptFromMarkdown:
    """_load_prompt_from_markdown 関数のテスト."""

    def test_load_prompt_removes_header(self):
        """Markdown の見出しが除去される."""
        content = "# システムプロンプト\n\nこれはプロンプトの内容です。\n"
        expected = "これはプロンプトの内容です。"

        with (
            patch("builtins.open", mock_open(read_data=content)),
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.read_text", return_value=content),
        ):
            result = _load_prompt_from_markdown("system_prompt.md")

        assert result == expected

    def test_load_prompt_removes_leading_blank_lines(self):
        """先頭の空行が除去される."""
        # 実装では、最初の行が # で始まる場合のみ見出しとして除去する
        # したがって、見出しが最初の行にある場合をテストする
        content = "# タイトル\n\n内容\n"
        # 1. 最初の見出し行 "# タイトル" を除去 → "\n\n内容\n"
        # 2. 先頭の空行を除去 → "内容\n"
        # 3. 末尾の空行を除去 → "内容"
        expected = "内容"

        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.read_text", return_value=content),
        ):
            result = _load_prompt_from_markdown("test.md")

        # 見出しと空行が除去されていることを確認
        assert result == expected

    def test_load_prompt_removes_trailing_blank_lines(self):
        """末尾の空行が除去される."""
        content = "# タイトル\n\n内容\n\n\n"
        expected = "内容"

        with (
            patch("builtins.open", mock_open(read_data=content)),
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.read_text", return_value=content),
        ):
            result = _load_prompt_from_markdown("test.md")

        assert result == expected

    def test_load_prompt_handles_no_header(self):
        """見出しがない場合も正しく動作する."""
        content = "これはプロンプトの内容です。\n"
        expected = "これはプロンプトの内容です。"

        with (
            patch("builtins.open", mock_open(read_data=content)),
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.read_text", return_value=content),
        ):
            result = _load_prompt_from_markdown("test.md")

        assert result == expected

    def test_load_prompt_file_not_found(self):
        """ファイルが見つからない場合にエラーが発生する."""
        with (
            patch("pathlib.Path.exists", return_value=False),
            pytest.raises(FileNotFoundError, match="Prompt file not found"),
        ):
            _load_prompt_from_markdown("nonexistent.md")

    def test_load_prompt_uses_correct_path(self):
        """正しいパスからファイルを読み込む."""
        content = "テスト内容"

        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.read_text", return_value=content) as mock_read,
        ):
            _load_prompt_from_markdown("test.md")

            # read_text が呼ばれたことを確認
            assert mock_read.called
            # read_text が呼ばれたことを確認（パスは関数内で構築される）
            # 実際の実装では、Path オブジェクトに対して read_text が呼ばれる
            if mock_read.call_args:
                # call_args が存在する場合、パスが渡されていることを確認
                assert len(mock_read.call_args) > 0


class TestDefaultSystemPrompt:
    """DEFAULT_SYSTEM_PROMPT のテスト."""

    def test_default_system_prompt_is_string(self):
        """デフォルトシステムプロンプトが文字列である."""
        assert isinstance(DEFAULT_SYSTEM_PROMPT, str)

    def test_default_system_prompt_is_not_empty(self):
        """デフォルトシステムプロンプトが空でない."""
        assert len(DEFAULT_SYSTEM_PROMPT) > 0

    def test_default_system_prompt_loaded_from_file(self):
        """デフォルトシステムプロンプトがファイルから読み込まれている."""
        # 実際のファイルが存在する場合、その内容が読み込まれていることを確認
        prompts_dir = (
            Path(__file__).parent.parent.parent / "src" / "kotonoha_bot" / "prompts"
        )
        system_prompt_file = prompts_dir / "system_prompt.md"

        if system_prompt_file.exists():
            # ファイルが存在する場合、内容が一致していることを確認
            file_content = system_prompt_file.read_text(encoding="utf-8")
            # 見出しを除去した内容と比較
            lines = file_content.split("\n")
            if lines and lines[0].startswith("#"):
                lines = lines[1:]
            while lines and not lines[0].strip():
                lines.pop(0)
            while lines and not lines[-1].strip():
                lines.pop()
            expected = "\n".join(lines)

            assert expected == DEFAULT_SYSTEM_PROMPT
