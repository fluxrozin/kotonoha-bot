# 管理者ダッシュボード実装選択肢

監査ログ、コンプライアンスログ、コスト管理などの管理者ダッシュボードを実装する際の選択肢を整理します。

## 要件

- **監査ログ**: すべての応答生成箇所でのログ記録、月次集計
- **コンプライアンスログ**: データアクセス、設定変更の記録
- **コスト管理**: トークン使用量、コスト計算、レポート
- **モニタリング**: メトリクス可視化、リアルタイム監視
- **設定管理**: グローバル/チャンネル/ユーザー設定の管理

## 選択肢の比較

### 選択肢 1: 既存 HTTP サーバーを拡張（シンプル HTML + JavaScript）

**概要**: 既存の `health.py` の HTTP サーバーを拡張し、シンプルな HTML + JavaScript でダッシュボードを実装

**技術スタック**:
- Python 標準ライブラリの `http.server`（既存）
- HTML + CSS + JavaScript（Vanilla JS または軽量ライブラリ）
- Chart.js や D3.js などの可視化ライブラリ

**メリット**:
- ✅ 追加の依存関係が最小限（Chart.js など軽量ライブラリのみ）
- ✅ 既存の HTTP サーバーを活用できる
- ✅ シンプルで理解しやすい
- ✅ セキュリティ設定が比較的簡単（基本認証、IP 制限など）
- ✅ 軽量で高速

**デメリット**:
- ❌ フロントエンド開発の工数が大きい
- ❌ 認証・認可の実装が必要（Discord OAuth2 は別途実装が必要）
- ❌ リアルタイム更新の実装が複雑（ポーリングまたは WebSocket）
- ❌ モダンな UI/UX の実装に時間がかかる

**実装工数**: 約 5-8 日

**推奨度**: ⭐⭐⭐☆☆（シンプルな要件向け）

---

### 選択肢 2: FastAPI + React/Vue（SPA）

**概要**: FastAPI で REST API を構築し、React または Vue で SPA を実装

**技術スタック**:
- FastAPI（Python Web フレームワーク）
- React または Vue.js（フロントエンド）
- Discord OAuth2（認証）
- SQLAlchemy または aiosqlite（データベースアクセス）

**メリット**:
- ✅ モダンな UI/UX を実装しやすい
- ✅ REST API として分離できる（将来の拡張性）
- ✅ リアルタイム更新（WebSocket または Server-Sent Events）
- ✅ 豊富な UI コンポーネントライブラリ（Material-UI、Vuetify など）
- ✅ TypeScript による型安全性

**デメリット**:
- ❌ 追加の依存関係が多い（FastAPI、フロントエンドビルドツール）
- ❌ ビルドプロセスの追加が必要
- ❌ セキュリティ設定が複雑（CORS、CSRF 対策など）
- ❌ 開発環境のセットアップが複雑

**実装工数**: 約 10-15 日

**推奨度**: ⭐⭐⭐⭐☆（本格的なダッシュボード向け）

---

### 選択肢 3: Streamlit（Python のみ）

**概要**: Streamlit を使用して Python のみでダッシュボードを実装

**技術スタック**:
- Streamlit（Python Web フレームワーク）
- Plotly または Altair（可視化）
- Discord OAuth2（認証、外部ライブラリ使用）

**メリット**:
- ✅ Python のみで実装可能（フロントエンド知識不要）
- ✅ 迅速なプロトタイピング
- ✅ 豊富な可視化コンポーネント
- ✅ 自動的なリアルタイム更新
- ✅ 認証機能の実装が比較的簡単

**デメリット**:
- ❌ カスタマイズ性が限定的
- ❌ パフォーマンスが他の選択肢より劣る可能性
- ❌ 複雑な UI の実装が難しい
- ❌ 追加の依存関係（Streamlit は比較的大きい）

**実装工数**: 約 3-5 日

**推奨度**: ⭐⭐⭐⭐☆（迅速な実装向け）

---

### 選択肢 4: Gradio（Python のみ、軽量）

**概要**: Gradio を使用して Python のみでダッシュボードを実装

**技術スタック**:
- Gradio（Python Web フレームワーク）
- Plotly または Matplotlib（可視化）
- Discord OAuth2（認証、外部ライブラリ使用）

**メリット**:
- ✅ Python のみで実装可能
- ✅ Streamlit より軽量
- ✅ 迅速なプロトタイピング
- ✅ 自動的なリアルタイム更新

**デメリット**:
- ❌ カスタマイズ性が限定的
- ❌ 複雑な UI の実装が難しい
- ❌ 認証機能の実装がやや複雑

**実装工数**: 約 3-5 日

**推奨度**: ⭐⭐⭐☆☆（軽量な要件向け）

---

### 選択肢 5: Flask + Jinja2（サーバーサイドレンダリング）

**概要**: Flask でサーバーサイドレンダリングを使用し、Jinja2 テンプレートで HTML を生成

**技術スタック**:
- Flask（Python Web フレームワーク）
- Jinja2（テンプレートエンジン）
- Chart.js または Plotly（可視化）
- Discord OAuth2（認証）

**メリット**:
- ✅ シンプルな実装
- ✅ サーバーサイドレンダリングで SEO 対応（不要だが）
- ✅ 認証・認可の実装が比較的簡単
- ✅ 追加の依存関係が少ない

**デメリット**:
- ❌ リアルタイム更新の実装が複雑
- ❌ モダンな UI/UX の実装に時間がかかる
- ❌ フロントエンドとバックエンドの分離が難しい

**実装工数**: 約 6-10 日

**推奨度**: ⭐⭐⭐☆☆（中規模な要件向け）

---

### 選択肢 6: 外部サービス連携（Grafana、Metabase など）

**概要**: 既存のダッシュボードツール（Grafana、Metabase など）と連携

**技術スタック**:
- Grafana または Metabase（ダッシュボードツール）
- データベース（aiosqlite または PostgreSQL に移行）
- API エンドポイント（メトリクスエクスポート）

**メリット**:
- ✅ 高機能なダッシュボードをすぐに利用可能
- ✅ 豊富な可視化オプション
- ✅ 認証・認可機能が充実
- ✅ メンテナンスが不要（ツール側で管理）

**デメリット**:
- ❌ 追加のインフラが必要（別コンテナ、データベース移行の可能性）
- ❌ カスタマイズ性が限定的
- ❌ コストがかかる可能性（有料プラン）
- ❌ プロジェクトの依存関係が増える

**実装工数**: 約 5-8 日（インフラ設定含む）

**推奨度**: ⭐⭐☆☆☆（大規模運用向け）

---

## 推奨選択肢

### 短期実装（Phase 9 の初期実装）

**推奨: 選択肢 3（Streamlit）**

- 迅速な実装が可能（3-5 日）
- Python のみで実装可能
- プロトタイプとして十分な機能
- 将来的に他の選択肢に移行可能

### 本格実装（Phase 9 の拡張）

**推奨: 選択肢 2（FastAPI + React/Vue）**

- モダンな UI/UX
- 拡張性が高い
- REST API として分離可能
- 長期的なメンテナンス性が高い

### 軽量実装（最小限の要件）

**推奨: 選択肢 1（既存 HTTP サーバー拡張）**

- 追加の依存関係が最小限
- 既存のインフラを活用
- シンプルで理解しやすい

---

## 実装フェーズの推奨

### Phase 9.1: 基本ダッシュボード（Streamlit）

1. Streamlit の導入
2. 基本的なメトリクス表示
3. 監査ログの表示
4. コスト管理の表示
5. 基本認証の実装

**期間**: 約 3-5 日

### Phase 9.2: 本格ダッシュボード（FastAPI + React/Vue）

1. FastAPI の導入
2. REST API の実装
3. React/Vue の実装
4. Discord OAuth2 の実装
5. リアルタイム更新の実装

**期間**: 約 10-15 日

---

## セキュリティ考慮事項

### 認証・認可

- **Discord OAuth2**: Discord アカウントでログイン
- **管理者権限の確認**: Discord サーバーの管理者権限を確認
- **セッション管理**: セキュアなセッション管理

### データ保護

- **HTTPS**: リバースプロキシ（Nginx、Traefik など）で HTTPS 化
- **IP 制限**: 管理者の IP アドレスのみアクセス可能にする
- **CSRF 対策**: CSRF トークンの実装

### ログ・監査

- **アクセスログ**: ダッシュボードへのアクセスを記録
- **操作ログ**: 設定変更などの操作を記録

---

## 実装例（Streamlit）

```python
# src/kotonoha_bot/features/monitoring/dashboard.py
import streamlit as st
import plotly.express as px
from datetime import datetime, timedelta

def main():
    st.set_page_config(page_title="KOTONOHA 管理者ダッシュボード", layout="wide")
    
    # 認証チェック
    if not check_auth():
        st.error("認証が必要です")
        return
    
    # サイドバー
    st.sidebar.title("メニュー")
    page = st.sidebar.selectbox("ページ", ["ダッシュボード", "監査ログ", "コスト管理", "設定"])
    
    if page == "ダッシュボード":
        show_dashboard()
    elif page == "監査ログ":
        show_audit_logs()
    elif page == "コスト管理":
        show_cost_management()
    elif page == "設定":
        show_settings()

def show_dashboard():
    st.title("ダッシュボード")
    # メトリクスの表示
    # ...

def show_audit_logs():
    st.title("監査ログ")
    # 監査ログの表示
    # ...

def show_cost_management():
    st.title("コスト管理")
    # コスト管理の表示
    # ...

def show_settings():
    st.title("設定管理")
    # 設定管理の表示
    # ...
```

---

## 実装例（FastAPI + React）

```python
# src/kotonoha_bot/features/monitoring/api.py
from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel

app = FastAPI()

@app.get("/api/metrics")
async def get_metrics():
    # メトリクスの取得
    return {"requests": 1000, "errors": 10}

@app.get("/api/audit-logs")
async def get_audit_logs():
    # 監査ログの取得
    return []

@app.get("/api/cost")
async def get_cost():
    # コスト情報の取得
    return {"total": 100.0, "monthly": 50.0}
```

```typescript
// frontend/src/components/Dashboard.tsx
import React, { useEffect, useState } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend } from 'recharts';

export const Dashboard: React.FC = () => {
  const [metrics, setMetrics] = useState([]);
  
  useEffect(() => {
    fetch('/api/metrics')
      .then(res => res.json())
      .then(data => setMetrics(data));
  }, []);
  
  return (
    <div>
      <h1>ダッシュボード</h1>
      <LineChart data={metrics}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="time" />
        <YAxis />
        <Tooltip />
        <Legend />
        <Line type="monotone" dataKey="requests" stroke="#8884d8" />
      </LineChart>
    </div>
  );
};
```

---

## 結論

**推奨実装順序**:

1. **Phase 9.1**: Streamlit で基本ダッシュボードを実装（迅速な実装）
2. **Phase 9.2**: 必要に応じて FastAPI + React/Vue に移行（本格実装）

**選択基準**:
- **迅速な実装が必要**: Streamlit
- **本格的な UI/UX が必要**: FastAPI + React/Vue
- **最小限の依存関係**: 既存 HTTP サーバー拡張
- **外部ツールの活用**: Grafana、Metabase
