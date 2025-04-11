# AIカードゲームビジュアライザ

AIがカードゲームをプレイする様子を可視化するWebアプリケーションです。AIの行動、ゲームの状態、アニメーションなどをリアルタイムで表示します。

## 機能

- AIのカードゲームプレイを視覚的に表示
- カードの合成やスタックなどのアクションをアニメーションで表示
- AIの行動ログをサイドバーでリアルタイム表示
- WebSocketを使用したリアルタイム通信

## 技術スタック

### フロントエンド
- React 19
- TypeScript
- Tailwind CSS v3
- DaisyUI
- Socket.io-client
- Vite

### バックエンド
- Python
- Socket.IO (python-socketio)
- aiohttp
- Gymnasium (OpenAI Gym)

## セットアップ

### 前提条件
- Node.js 18以上
- Python 3.8以上
- npm または yarn

### フロントエンドのセットアップ

```bash
# プロジェクトディレクトリに移動
cd card-game-visualizer

# 依存関係のインストール
npm install

# 開発サーバーの起動
npm run dev
```

### バックエンドのセットアップ

```bash
# サーバーディレクトリに移動
cd card-game-visualizer/server

# 仮想環境の作成（オプション）
python -m venv venv
source venv/bin/activate  # Linuxの場合
# または
venv\Scripts\activate  # Windowsの場合

# 依存関係のインストール
pip install -r requirements.txt

# サーバーの起動
python server.py
```

## 使用方法

1. バックエンドサーバーを起動します
2. フロントエンド開発サーバーを起動します
3. ブラウザで http://localhost:5173 にアクセスします
4. 「サーバー接続」ボタンをクリックしてバックエンドに接続します
5. 「ゲーム開始」ボタンをクリックしてゲームを開始します
6. 「次のターン」ボタンをクリックするとAIが次の行動を選択します

## ゲームルール

- カード: 0から5までの数字
- 手札: 4枚
- ホールド: 1枚 (0のみホールド可能)
- スタック: 数字の昇順に積む (0は特殊ルールあり)
- 得点: 1, 2, 3, 4, 5 の順に積めたら +1000点
- 合成: 同じ数字を合成して1つ上の数字に (5は不可、4+4=4)。1ターン2回まで
- ターン: スタックをクリアすると1ターン終了。全20ターン
- 0カード特殊ルール: いつでも破棄可能、ホールド枠には0のみ置ける

## 開発者向け情報

### プロジェクト構造

```
card-game-visualizer/
├── src/                    # フロントエンドソースコード
│   ├── components/         # Reactコンポーネント
│   │   └── game/           # ゲーム関連コンポーネント
│   ├── services/           # サービス（WebSocketなど）
│   ├── App.tsx             # メインアプリケーション
│   └── main.tsx            # エントリーポイント
├── server/                 # バックエンドサーバー
│   ├── server.py           # WebSocketサーバー
│   └── requirements.txt    # Pythonの依存関係
└── public/                 # 静的ファイル
```

### カスタマイズ

- `src/components/game/Card.tsx`: カードの見た目をカスタマイズ
- `src/components/game/GameBoard.tsx`: ゲームボードのレイアウトをカスタマイズ
- `server/server.py`: AIの行動選択ロジックをカスタマイズ
