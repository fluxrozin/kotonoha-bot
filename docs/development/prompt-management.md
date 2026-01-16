# プロンプト管理ガイド

このドキュメントでは、Kotonoha Bot のプロンプトファイルの管理方法について説明します。

## プロンプトファイルの構成

すべてのプロンプトファイルは、プロジェクトルートの `prompts/` フォルダに集約されています。

```txt
prompts/
├── system_prompt.md                                    # システムプロンプト
├── eavesdrop_judge_prompt.md                          # 聞き耳型判定用プロンプト
├── eavesdrop_response_prompt.md                       # 聞き耳型応答生成用プロンプト
├── eavesdrop_same_conversation_prompt.md              # 同じ会話判定用プロンプト
├── eavesdrop_conversation_state_prompt.md             # 会話状態分析用プロンプト
└── eavesdrop_conversation_situation_changed_prompt.md # 会話状況変化判定用プロンプト
```

## プロンプトファイルの説明

### system_prompt.md

Bot の基本的な動作を定義するシステムプロンプトです。

- Bot の役割とキャラクター設定
- コミュニケーションのガイドライン
- 禁止事項
- メッセージの文脈理解に関する注意事項

**使用箇所**: すべての AI 応答生成時に使用されます。

### eavesdrop_judge_prompt.md

聞き耳型機能で、会話に参加すべきかどうかを判定するためのプロンプトです。

- 判定基準（YES/NO）
- 会話の雰囲気を理解するための指示
- 店側スタッフからの注意喚起を検出するための条件

**使用箇所**: 聞き耳型機能の判定フェーズで使用されます。

### eavesdrop_response_prompt.md

聞き耳型機能で、実際の応答を生成するためのプロンプトです。

- 会話の雰囲気に応じた応答方法
- 重要な注意事項
- 抽象的な応答を避けるための指示

**使用箇所**: 聞き耳型機能の応答生成フェーズで使用されます。

### eavesdrop_same_conversation_prompt.md

聞き耳型機能で、会話が同じ会話の続きかどうかを判定するためのプロンプトです。

- 会話の継続性を判定する基準
- 新しい会話と判断する条件

**使用箇所**: 聞き耳型機能の同じ会話判定フェーズで使用されます。

### eavesdrop_conversation_state_prompt.md

聞き耳型機能で、会話の状態を分析するためのプロンプトです。

- 会話の状態（ENDING/MISUNDERSTANDING/CONFLICT/ACTIVE）を判定
- 各状態の特徴と判定基準

**使用箇所**: 聞き耳型機能の会話状態分析フェーズで使用されます。

### eavesdrop_conversation_situation_changed_prompt.md

聞き耳型機能で、会話状況が変化したかどうかを判定するためのプロンプトです。

- 会話状況の変化を検出する基準
- 変化があった場合とない場合の判定

**使用箇所**: 聞き耳型機能の会話状況変化判定フェーズで使用されます。

## プロンプトファイルの編集方法

### ローカル環境での編集

1. `prompts/` フォルダ内の Markdown ファイルを直接編集します
2. Bot を再起動すると、変更が反映されます

```bash
# プロンプトファイルを編集
vim prompts/system_prompt.md

# Bot を再起動
docker compose restart kotonoha-bot
```

### Docker 環境での編集

`docker-compose.yml` で `prompts/` フォルダがマウントされているため、ホスト側から編集できます。

**重要**: プロンプトファイルは起動時に読み込まれるため、変更を反映するには Bot を再起動する必要があります。

1. ホスト側の `prompts/` フォルダ内の Markdown ファイルを編集します
2. Bot を再起動して変更を反映します

```bash
# プロンプトファイルを編集（ホスト側）
vim prompts/system_prompt.md

# Bot を再起動して変更を反映
docker compose restart kotonoha-bot
```

## プロンプトファイルの読み込み方法

プロンプトファイルは、以下のコードで読み込まれます：

- `src/kotonoha_bot/ai/prompts.py` - システムプロンプト（`system_prompt.md`）の読み込み
- `src/kotonoha_bot/eavesdrop/llm_judge.py` - 聞き耳型プロンプトの読み込み
  - `eavesdrop_judge_prompt.md` - 介入判定用
  - `eavesdrop_response_prompt.md` - 応答生成用
  - `eavesdrop_same_conversation_prompt.md` - 同じ会話判定用
  - `eavesdrop_conversation_state_prompt.md` - 会話状態分析用
  - `eavesdrop_conversation_situation_changed_prompt.md` - 会話状況変化判定用

すべてのプロンプトファイルは、プロジェクトルートの `prompts/` フォルダから
読み込まれます。読み込みは起動時に一度だけ実行されるため、
変更を反映するには Bot の再起動が必要です。

**再起動方法**:

プロンプトファイルを変更した後、Bot を再起動して変更を反映します。

```bash
# Docker 環境の場合: コンテナを再起動
docker compose restart kotonoha-bot
```

**読み込み処理の詳細**:

- プロンプトファイルは UTF-8 エンコーディングで読み込まれます
- Markdown の見出し（`#` で始まる最初の行）は自動的に除去されます
- 先頭と末尾の空行も自動的に除去されます

## プロンプトファイルのベストプラクティス

### 1. バージョン管理

プロンプトファイルは Git で管理されています。変更をコミットする際は、変更内容と理由を明確に記載してください。

### 2. テスト

プロンプトを変更した後は、必ず動作確認を行ってください。

```bash
# 開発環境でテスト
python -m src.kotonoha_bot.main

# または Docker でテスト
docker compose up
```

### 3. 段階的な変更

大きな変更を行う場合は、段階的に変更し、各段階で動作確認を行ってください。

### 4. ドキュメント化

プロンプトに重要な変更を加えた場合は、このドキュメントや関連するドキュメントを更新してください。

## トラブルシューティング

### プロンプトファイルが見つからないエラー

```txt
FileNotFoundError: Prompt file not found: /app/prompts/system_prompt.md
```

**原因**: プロンプトファイルが存在しない、またはパスが間違っている

**解決方法**:

1. `prompts/` フォルダがプロジェクトルートに存在することを確認
2. 必要なプロンプトファイルが存在することを確認
3. Docker を使用している場合、`docker-compose.yml` でマウントされていることを確認

### プロンプトの変更が反映されない

**原因**: プロンプトファイルは起動時に一度だけ読み込まれるため、変更を反映するには再起動が必要です

**解決方法**:

1. Bot を再起動する
2. Docker を使用している場合、コンテナを再起動する

```bash
# ローカル環境の場合
# Ctrl+C で停止後、再度起動
python -m src.kotonoha_bot.main

# Docker 環境の場合
docker compose restart kotonoha-bot
```

**注意**: `docker-compose.yml` で `prompts/` フォルダがマウントされていても、プロンプトファイルは起動時に読み込まれるため、変更を反映するには再起動が必要です。

## 関連ドキュメント

- [システムアーキテクチャ](../architecture/system-architecture.md) - システム構成の詳細
- [Phase 5 実装計画](../implementation/phases/phase5.md) - 聞き耳型機能の実装詳細
