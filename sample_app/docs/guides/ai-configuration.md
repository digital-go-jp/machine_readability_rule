# AI補完機能の設定ガイド

## 概要

Harunobuの採点エンジンは**決定論的なルールベースの採点**をコアとし、オプションでAI補完機能を利用できます。AI機能はすべて補完的に動作し、無効化されていても基本的な採点機能は動作します。

**マルチプロバイダー対応**: Gemini / OpenAI / Anthropic 等の複数AIプロバイダーに対応しています。`AIClient`（統一クライアント）がLiteLLMまたはgoogle.genaiをバックエンドとして使用します。

## 動作モード

| モード | AI機能 | 用途 |
|--------|--------|------|
| AI無効（デフォルト） | OFF | テスト、オフライン環境、CI |
| AI有効 | ON | 意味的チェックの精度向上 |

### AI無効モード

環境変数 `HARUNOBU_AI_DISABLED=1` を設定するか、`.env` に記載がない場合のデフォルト動作です。
すべてのルール判定は決定論的に動作し、AI依存の判定箇所では信頼度（confidence）が低めに設定されます。

### AI有効モード

`AIClient`（統一クライアント）経由で以下の意味的チェックを補完します:

| コンポーネント | 説明 | 必要な設定 |
|--------------|------|-----------|
| AISemanticChecker | 11種類の意味的チェック（項目省略検出、表記揺れ検出等） | いずれかのプロバイダーのAPIキー |
| AIVisualAnalyzer | Excel/CSVの視覚的分析（色・罫線・レイアウト） | いずれかのプロバイダーのAPIキー + LibreOffice |

## AIモードON時のルール別補完一覧

AIモードが有効な場合、以下のルールが決定論的チェックに加えてAI補完検出を実行します。

### カテゴリの定義

| カテゴリ | 説明 |
|---------|------|
| **AI専用** | AIなしでは `confidence=0` でスキップ。AI補完なしにはチェック不可 |
| **AI補完** | 決定論的チェックは常に動作。AI有効時は追加の検出を実行 |

### L1: 基礎チェック

| ルールID | ルール名 | カテゴリ | 決定論的チェック | AI補完 | 使用コンポーネント |
|---------|---------|---------|----------------|--------|-----------------|
| L1-05 | 列ヘッダーチェック | AI補完 | ヘッダー欠落・連番ヘッダー検出 | 複数行ヘッダーの結合問題等をビジュアルから補完検出 | AIVisualAnalyzer |
| L1-09 | 空白・ゼロ区別チェック | **AI専用** | なし | 数値列ごとに「ゼロが自然に発生しにくい列か」をLLMで判定し、空白・ゼロ混在を検出 | AISemanticChecker |
| L1-11 | 書式依存データ区別チェック | AI補完 | フォント色・背景色・太字・斜体の使用を検出 | Excel画像から書式による意味付けをより正確に確認 | AIVisualAnalyzer |

### L2: 意味チェック

| ルールID | ルール名 | カテゴリ | 決定論的チェック | AI補完 | 使用コンポーネント |
|---------|---------|---------|----------------|--------|-----------------|
| L2-01 | 数値データ純粋性 | AI補完 | 数値列に文字列が混在していないかを検出 | 「500千円」「約1,200名」等の単位混在パターンを検出 | AISemanticChecker |
| L2-02 | 項目名省略チェック | AI補完 | 「同」「〃」等の省略記号・空白省略を検出 | 「H28」「R3」等の和暦略称・文脈的省略を検出 | AISemanticChecker |
| L2-04 | 選択肢標準化 | AI補完 | 出現頻度の少ない外れ値を表記ゆれ候補として検出 | 「男」「男性」「M」等の意味的に同等な表記グループを検出 | AISemanticChecker |
| L2-05 | その他詳細分離 | AI補完 | 「その他_〇〇」等の文字列パターンで混在を検出 | パターンが曖昧なケースで「その他」と詳細の混在か判定 | AISemanticChecker |

### L3: 高度チェック

| ルールID | ルール名 | カテゴリ | 決定論的チェック | AI補完 | 使用コンポーネント |
|---------|---------|---------|----------------|--------|-----------------|
| L3-04 | データ単位記載 | AI補完 | 括弧内単位表記・単位暗示ヘッダー名をパターンマッチで検出 | 「人口」→人・「金額」→円等のヘッダー名から意味推論で単位を判定 | AISemanticChecker |
| L3-06 | 地域コード・名称 | AI補完 | 都道府県名・市区町村名の省略、標準地域コード列の有無を検出 | 曖昧なヘッダー名で地域データが隠れていないかを検出 | AISemanticChecker |
| L3-09 | 縦持ち形式 | AI補完 | 時間軸ヘッダー（年・月・期）の横持ち・連番列を検出 | 都道府県・性別・年齢区分等の非時間軸カテゴリが列名になっている横持ちを検出 | AISemanticChecker |

## プロバイダー設定

### 環境変数一覧

| 環境変数 | 説明 | デフォルト |
|---------|------|-----------|
| `HARUNOBU_AI_PROVIDER` | AIプロバイダー（`gemini` / `openai` / `anthropic`） | `gemini` |
| `HARUNOBU_AI_MODEL` | モデル名オーバーライド | プロバイダーのデフォルト |
| `HARUNOBU_AI_FALLBACK_MODEL` | フォールバックモデル | `gemini` プロバイダー時は "gemini-3.5-flash" |
| `HARUNOBU_AI_DISABLED` | `1` でAI機能を無効化 | — |
| `GOOGLE_API_KEY` | Google AI Studio APIキー | — |
| `GOOGLE_GENAI_USE_VERTEXAI` | Vertex AI使用フラグ | — |
| `GOOGLE_CLOUD_PROJECT` | GCPプロジェクトID | — |
| `GOOGLE_CLOUD_LOCATION` | GCPリージョン | `asia-northeast1` |
| `OPENAI_API_KEY` | OpenAI APIキー | — |
| `ANTHROPIC_API_KEY` | Anthropic APIキー | — |

### セットアップ

#### 1. 環境変数ファイルの作成

```bash
cd sample_app
cp .env.example .env
```

#### 2a. Gemini（Google AI Studio）を使用する場合

[Google AI Studio](https://aistudio.google.com/) でAPIキーを取得し、`.env` に設定:

```
HARUNOBU_AI_PROVIDER=gemini
GOOGLE_API_KEY=your-api-key-here
```

#### 2b. Gemini（Vertex AI）を使用する場合

Google Cloud プロジェクトの認証を設定:

```bash
gcloud auth application-default login
```

`.env` に以下を設定:

```
HARUNOBU_AI_PROVIDER=gemini
GOOGLE_GENAI_USE_VERTEXAI=true
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=asia-northeast1
```

#### 2c. OpenAI を使用する場合

```
HARUNOBU_AI_PROVIDER=openai
OPENAI_API_KEY=your-api-key-here
# HARUNOBU_AI_MODEL=gpt-4o  # デフォルト: gpt-4o
```

#### 2d. Anthropic を使用する場合

```
HARUNOBU_AI_PROVIDER=anthropic
ANTHROPIC_API_KEY=your-api-key-here
# HARUNOBU_AI_MODEL=claude-sonnet-4-20250514  # デフォルト
```

### 3. AI機能の確認

```bash
cd sample_app
uv run harunobu analyze sample.xlsx --mode thorough
```

## バックエンド選択ロジック

`AIClient` は以下のロジックでバックエンドを自動選択します:

1. **非Geminiプロバイダー** → LiteLLM必須（未インストールの場合はエラー）
2. **Geminiプロバイダー** → LiteLLMがあればLiteLLM、なければgoogle.genaiにフォールバック

```
HARUNOBU_AI_PROVIDER=openai  → LiteLLM (必須)
HARUNOBU_AI_PROVIDER=anthropic → LiteLLM (必須)
HARUNOBU_AI_PROVIDER=gemini  → LiteLLM (優先) or google.genai (フォールバック)
```

## リソース要件

| 項目 | 目安 |
|------|------|
| APIコール数 | ファイルあたり10〜30回（ルール数・テーブル数に依存） |
| 処理時間増加 | AI有効時 +5〜15秒/ファイル |
| 費用 | Google AI Studio / OpenAI / Anthropic の無料枠で開発・テストは十分対応可能 |

## AIVisualAnalyzer の追加要件

AIVisualAnalyzerはExcel/CSVを画像化するためにLibreOfficeが必要です:

```bash
# macOS
brew install --cask libreoffice

# Ubuntu/Debian
sudo apt install libreoffice-calc

# Windows
# LibreOfficeをインストーラーからインストール
```

LibreOfficeがインストールされていない場合、AIVisualAnalyzerはスキップされ、他のAI機能は正常に動作します。

## トラブルシューティング

### AI機能が動作しない

1. `.env` ファイルが `sample_app/` ディレクトリにあることを確認
2. `HARUNOBU_AI_DISABLED` が設定されていないことを確認
3. `HARUNOBU_AI_PROVIDER` に対応するAPIキーが正しく設定されていることを確認
4. 非Geminiプロバイダーの場合、`litellm` がインストールされていることを確認

### API呼び出しエラー

AI機能はgraceful fallbackを実装しており、API呼び出しに失敗した場合:
- エラーはログに記録されます
- 該当チェックの信頼度（confidence）が低下します
- 採点自体は決定論的ルールのみで完了します

### LibreOfficeが見つからない

AIVisualAnalyzerのみスキップされます。他のAI機能（AISemanticChecker）は影響を受けません。

### LiteLLMがインストールされていない

- Geminiプロバイダーの場合: google.genaiにフォールバックします（動作に影響なし）
- 非Geminiプロバイダーの場合: AI機能が利用不可になります。`uv add litellm` でインストールしてください
