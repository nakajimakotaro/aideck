import { useState, useEffect, useCallback, useRef } from 'react'
import GameBoard, { GameState } from './components/game/GameBoard'
import ActionLog from './components/game/ActionLog'
import webSocketService, { WebSocketEvent } from './services/WebSocketService'

function App() {
  const [isConnected, setIsConnected] = useState(false);
  const [gameState, setGameState] = useState<GameState | null>(null);
  const [actionLog, setActionLog] = useState<string[]>([]);
  const [lastAction, setLastAction] = useState<string>('');
  const [isAutoPlaying, setIsAutoPlaying] = useState(false);
  const [autoPlaySpeed, setAutoPlaySpeed] = useState(1.5);
  const [isRandomMode, setIsRandomMode] = useState(false); // デフォルトはAIモード

  // アニメーション状態を管理するためのref
  const isAnimatingRef = useRef<boolean>(false);
  // アニメーション完了後に状態を更新するためのタイマーID
  const animationTimerRef = useRef<number | null>(null);
  // 保留中のゲーム状態を保存するためのref
  const pendingGameStateRef = useRef<GameState | null>(null);
  // 保留中のアクションを保存するためのref
  const pendingActionRef = useRef<string | null>(null);

  // WebSocketイベントハンドラ
  const handleWebSocketEvent = useCallback((event: WebSocketEvent) => {
    switch (event.type) {
      case 'connect':
        setIsConnected(true);
        break;
      case 'disconnect':
        setIsConnected(false);
        break;
      case 'gameState':
        // ゲーム状態は常に即時更新する
        setGameState(event.state);
        
        // 保留中のアクションがあれば処理
        if (!isAnimatingRef.current && pendingActionRef.current) {
          processAction(pendingActionRef.current);
          pendingActionRef.current = null;
        }
        break;
      case 'action':
        // アクションログを即時更新
        setActionLog(prev => [...prev, event.description]);
        
        // アニメーション中でなければアクションを処理
        if (!isAnimatingRef.current) {
          processAction(event.description);
        } else {
          // アニメーション中なら保留
          pendingActionRef.current = event.description;
        }
        break;
      case 'reward':
        setActionLog(prev => [...prev, `報酬: ${event.value}点`]);
        break;
      case 'error':
        setActionLog(prev => [...prev, `エラー: ${event.message}`]);
        break;
    }
  }, []);

  // アクションを処理する関数
  const processAction = useCallback((actionDescription: string) => {
    // アニメーション中フラグを設定
    isAnimatingRef.current = true;
    
    // 最後のアクションを設定してアニメーションを開始
    setLastAction(actionDescription);
    
    // 既存のタイマーをクリア
    if (animationTimerRef.current !== null) {
      clearTimeout(animationTimerRef.current);
    }
    
    // アニメーション完了後にアニメーションをリセットするタイマーを設定
    animationTimerRef.current = window.setTimeout(() => {
      // アニメーションをリセット
      setLastAction('');
      isAnimatingRef.current = false;
      animationTimerRef.current = null;
      
      // 保留中のアクションがあれば処理
      if (pendingActionRef.current) {
        processAction(pendingActionRef.current);
        pendingActionRef.current = null;
      }
    }, 400); // Card.tsxのアニメーション時間に合わせる
  }, []);

  // WebSocket接続の初期化
  useEffect(() => {
    webSocketService.addListener(handleWebSocketEvent);
    
    // 自動接続
    webSocketService.connect();
    
    return () => {
      webSocketService.removeListener(handleWebSocketEvent);
      webSocketService.disconnect();
      
      // クリーンアップ: タイマーをクリア
      if (animationTimerRef.current !== null) {
        clearTimeout(animationTimerRef.current);
      }
    };
  }, [handleWebSocketEvent]);

  // 接続/切断の処理
  const toggleConnection = () => {
    if (isConnected) {
      webSocketService.disconnect();
    } else {
      webSocketService.connect();
    }
  };

  // ゲーム開始コマンド
  const startGame = () => {
    webSocketService.sendCommand('start');
    setActionLog(prev => [...prev, 'ゲームを開始しました']);
  };

  // リセットコマンド
  const resetGame = () => {
    webSocketService.sendCommand('reset');
    setActionLog(prev => [...prev, 'ゲームをリセットしました']);
    setGameState(null);
  };

  // 次のターンコマンド
  const nextTurn = () => {
    // アニメーション中は次のターンコマンドを無視
    if (isAnimatingRef.current) {
      return;
    }
    
    webSocketService.sendCommand('next');
    setActionLog(prev => [...prev, '次のターンに進みます']);
  };

  // 自動プレイの切り替え
  const toggleAutoPlay = () => {
    if (isAutoPlaying) {
      webSocketService.stopAutoPlay();
      setIsAutoPlaying(false);
    } else {
      webSocketService.startAutoPlay();
      setIsAutoPlaying(true);
    }
  };

  // 自動プレイ速度の変更
  const handleSpeedChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newSpeed = parseFloat(e.target.value);
    setAutoPlaySpeed(newSpeed);
    webSocketService.setAutoPlaySpeed(newSpeed);
  };

  // ランダムモードの切り替え
  const toggleRandomMode = () => {
    webSocketService.toggleRandomMode();
    setIsRandomMode(!isRandomMode);
  };

  return (
    <div className="min-h-screen bg-base-200">
      <div className="navbar bg-base-100 shadow-md">
        <div className="flex-1">
          <a className="btn btn-ghost text-xl">AIカードゲームビジュアライザ</a>
        </div>
        <div className="flex-none">
          <div className="indicator">
            <span className={`indicator-item badge ${isConnected ? 'badge-success' : 'badge-error'}`}></span>
            <button className="btn btn-sm">
              {isConnected ? '接続中' : '未接続'}
            </button>
          </div>
        </div>
      </div>

      <div className="container mx-auto p-2">
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-2">
          {/* 左側エリア（ゲームボードとコントロールパネル） - 3/4幅 */}
          <div className="lg:col-span-3 flex flex-col gap-4">
            {/* ゲームボード */}
            <div className="bg-base-100 rounded-box shadow-lg p-2">
              <h2 className="text-xl font-bold mb-2">ゲームボード</h2>
              <div className="card-game-board flex flex-col items-center justify-between">
                <GameBoard gameState={gameState} lastAction={lastAction} />
              </div>
            </div>
            
            {/* コントロールパネル */}
            <div className="bg-base-100 rounded-box shadow-lg p-2">
              <h2 className="text-xl font-bold mb-2">コントロール</h2>
              <div className="flex flex-wrap gap-2 mb-4">
                <button 
                  className="btn btn-primary" 
                  onClick={startGame}
                  disabled={!isConnected}
                >
                  ゲーム開始
                </button>
                <button 
                  className="btn btn-secondary" 
                  onClick={resetGame}
                  disabled={!isConnected}
                >
                  リセット
                </button>
                <button 
                  className="btn btn-accent" 
                  onClick={nextTurn}
                  disabled={!isConnected || isAutoPlaying}
                >
                  次のターン
                </button>
                <button 
                  className={`btn ${isAutoPlaying ? 'btn-error' : 'btn-success'}`}
                  onClick={toggleAutoPlay}
                  disabled={!isConnected}
                >
                  {isAutoPlaying ? '自動プレイ停止' : '自動プレイ開始'}
                </button>
              </div>
              
              {/* 速度調整スライダー */}
              <div className="form-control w-full max-w-xs mb-4">
                <label className="label">
                  <span className="label-text">自動プレイ速度: {autoPlaySpeed.toFixed(1)}秒</span>
                </label>
                <input 
                  type="range" 
                  min="0.1" 
                  max="3.0" 
                  step="0.1" 
                  value={autoPlaySpeed} 
                  onChange={handleSpeedChange}
                  className="range range-primary" 
                  disabled={!isConnected}
                />
                <div className="w-full flex justify-between text-xs px-2">
                  <span>速い</span>
                  <span>遅い</span>
                </div>
              </div>

              {/* AIモード切り替え */}
              <div className="form-control">
                <label className="label cursor-pointer">
                  <span className="label-text">AIモード</span>
                  <div className="flex items-center gap-2">
                    <span className="label-text">ランダム</span>
                    <input 
                      type="checkbox" 
                      className="toggle toggle-primary" 
                      checked={!isRandomMode}
                      onChange={toggleRandomMode}
                      disabled={!isConnected}
                    />
                    <span className="label-text">学習済みAI</span>
                  </div>
                </label>
              </div>
            </div>
          </div>

          {/* 行動ログサイドバー - 1/4幅 */}
          <div className="bg-base-100 rounded-box shadow-lg p-2 h-full">
            <h2 className="text-xl font-bold mb-2">AIの行動ログ</h2>
            <div className="h-[calc(100vh-20rem)]">
              <ActionLog logs={actionLog} />
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default App
