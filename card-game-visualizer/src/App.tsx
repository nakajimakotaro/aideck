import { useState, useEffect, useCallback, useRef } from 'react'
import GameBoard, { GameState } from './components/game/GameBoard'
import ActionLog from './components/game/ActionLog'

type CardGameObs = {
  hand: number[]
  hold: number
  next: number
  stack: number[]
  current_turn: number
  merges_this_turn: number
  score: number
  fullchain_count: number
}

type CardGameInfo = {
  [key: string]: any
}

type ResetResponse = {
  obs: CardGameObs
  info: CardGameInfo
}

type NextTurnResponse = {
  obs: CardGameObs
  info: CardGameInfo
  action: number
  action_desc: string
  reward: number
  terminated: boolean
  truncated: boolean
}

function App() {
  const [gameState, setGameState] = useState<GameState | null>(null) // 初期状態をnullに
  const [info, setInfo] = useState<CardGameInfo>({})
  const [actionLog, setActionLog] = useState<string[]>([])
  const [lastAction, setLastAction] = useState<string>('')
  const [isAutoPlaying, setIsAutoPlaying] = useState(false)
  const [autoPlaySpeed, setAutoPlaySpeed] = useState(1.5)
  const [isRandomMode, setIsRandomMode] = useState(false)
  const [terminated, setTerminated] = useState(false)
  const [truncated, setTruncated] = useState(false)
  const [isLoading, setIsLoading] = useState(true) // ローディング状態を追加
  const [error, setError] = useState<string | null>(null) // エラー状態を追加
  const autoPlayTimerRef = useRef<number | null>(null)
  const isAnimatingRef = useRef<boolean>(false)
  const animationTimerRef = useRef<number | null>(null)
  const pendingActionRef = useRef<string | null>(null)

  // サーバーから初期状態を取得する関数
  const fetchInitialState = async (logMessage: string) => {
    setIsLoading(true)
    setError(null)
    try {
      const res = await fetch('/api/reset')
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.error || 'Failed to fetch initial state')
      }
      const data: ResetResponse = await res.json()
      setGameState({
        ...data.obs,
      })
      setInfo(data.info)
      setActionLog([logMessage])
      setLastAction('')
      setTerminated(false)
      setTruncated(false)
      stopAutoPlay() // リセット時に自動プレイ停止
    } catch (e) {
      const errorMessage = e instanceof Error ? e.message : String(e)
      setError(`初期状態の取得に失敗しました: ${errorMessage}`)
      setActionLog(prev => [...prev, `エラー: ${errorMessage}`])
      setGameState(null) // エラー時はnullに戻す
    } finally {
      setIsLoading(false)
    }
  }

  // ゲーム開始（初期化）
  const startGame = () => {
    fetchInitialState('ゲームを開始しました')
  }

  // リセット
  const resetGame = () => {
    fetchInitialState('ゲームをリセットしました')
  }

  // コンポーネントマウント時に初期状態を取得
  useEffect(() => {
    fetchInitialState('初期状態を読み込み中...')
  }, [])

  // サーバーにnext_turnリクエスト
  const nextTurn = async () => {
    if (isAnimatingRef.current || terminated || truncated || !gameState) return

    setActionLog(prev => [...prev, '次のターンに進みます'])
    setError(null) // APIコール前にエラーをクリア
    try {
      const res = await fetch('/api/next_turn', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          obs: {
            hand: gameState.hand,
            hold: gameState.hold,
            next: gameState.next,
            stack: gameState.stack,
            current_turn: gameState.current_turn,
            merges_this_turn: gameState.merges_this_turn,
            score: gameState.score,
            fullchain_count: gameState.fullchain_count,
          },
          info: info,
          use_random: isRandomMode,
        }),
      })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.error || 'Next turn request failed')
      }
      const data: NextTurnResponse = await res.json()
      setGameState(prev => ({
        ...(prev as GameState), // nullでないことを保証
        ...data.obs,
      }))
      setInfo(data.info)
      setActionLog(prev => [...prev, data.action_desc])
      setLastAction(data.action_desc)
      if (data.reward !== 0) {
        setActionLog(prev => [...prev, `報酬: ${data.reward}点`])
      }
      setTerminated(data.terminated)
      setTruncated(data.truncated)
      if (data.terminated || data.truncated) {
        setActionLog(prev => [...prev, 'ゲームが終了しました'])
        stopAutoPlay()
      }
      // アニメーション処理
      isAnimatingRef.current = true
      if (animationTimerRef.current !== null) {
        clearTimeout(animationTimerRef.current)
      }
      animationTimerRef.current = window.setTimeout(() => {
        setLastAction('')
        isAnimatingRef.current = false
        animationTimerRef.current = null
        if (pendingActionRef.current) {
          setLastAction(pendingActionRef.current)
          pendingActionRef.current = null
        }
      }, 400)
    } catch (e) {
      const errorMessage = e instanceof Error ? e.message : String(e)
      setError(`次のターンの処理に失敗しました: ${errorMessage}`)
      setActionLog(prev => [...prev, `エラー: ${errorMessage}`])
    }
  }

  // 自動プレイ
  const autoPlayLoop = useCallback(() => {
    if (!isAutoPlaying || terminated || truncated || !gameState) return
    nextTurn()
    autoPlayTimerRef.current = window.setTimeout(autoPlayLoop, autoPlaySpeed * 1000)
  }, [isAutoPlaying, autoPlaySpeed, terminated, truncated, gameState]) // gameStateを追加

  const startAutoPlay = () => {
    if (isAutoPlaying || terminated || truncated || !gameState) return
    setIsAutoPlaying(true)
  }

  const stopAutoPlay = () => {
    setIsAutoPlaying(false)
    if (autoPlayTimerRef.current !== null) {
      clearTimeout(autoPlayTimerRef.current)
      autoPlayTimerRef.current = null
    }
  }

  useEffect(() => {
    if (isAutoPlaying && !terminated && !truncated && gameState) { // 条件追加
      autoPlayLoop()
    } else {
      if (autoPlayTimerRef.current !== null) {
        clearTimeout(autoPlayTimerRef.current)
        autoPlayTimerRef.current = null
      }
    }
    return () => {
      if (autoPlayTimerRef.current !== null) {
        clearTimeout(autoPlayTimerRef.current)
        autoPlayTimerRef.current = null
      }
    }
  }, [isAutoPlaying, autoPlayLoop, terminated, truncated, gameState]) // 依存配列に gameState を追加

  // 速度変更
  const handleSpeedChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newSpeed = parseFloat(e.target.value)
    setAutoPlaySpeed(newSpeed)
  }

  // ランダム/AIモード切り替え
  const toggleRandomMode = () => {
    setIsRandomMode(v => !v)
  }

  return (
    <div className="min-h-screen bg-base-200">
      <div className="navbar bg-base-100 shadow-md">
        <div className="flex-1">
          <a className="btn btn-ghost text-xl">AIカードゲームビジュアライザ</a>
        </div>
        <div className="flex-none">
          <div className="indicator">
            <span className={`indicator-item badge ${error ? 'badge-error' : 'badge-success'}`}></span>
            <button className="btn btn-sm" disabled>
              {error ? 'エラー' : isLoading ? '読込中' : 'オフライン動作'}
            </button>
          </div>
        </div>
      </div>

      <div className="container mx-auto p-2">
        {/* エラー表示 */}
        {error && (
          <div role="alert" className="alert alert-error mb-4">
            <svg xmlns="http://www.w3.org/2000/svg" className="stroke-current shrink-0 h-6 w-6" fill="none" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
            <span>{error}</span>
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-4 gap-2">
          {/* 左側エリア（ゲームボードとコントロールパネル） - 3/4幅 */}
          <div className="lg:col-span-3 flex flex-col gap-4">
            {/* ゲームボード */}
            <div className="bg-base-100 rounded-box shadow-lg p-2 min-h-[300px]"> {/* 高さを確保 */}
              <h2 className="text-xl font-bold mb-2">ゲームボード</h2>
              <div className="card-game-board flex flex-col items-center justify-between">
                {isLoading ? (
                  <div className="flex items-center justify-center h-full">
                    <span className="loading loading-spinner loading-lg"></span>
                  </div>
                ) : gameState ? (
                  <GameBoard gameState={gameState} lastAction={lastAction} />
                ) : (
                  <div className="flex items-center justify-center h-full">
                    <p className="text-xl text-error">ゲーム状態の読み込みに失敗しました。</p>
                  </div>
                )}
              </div>
            </div>

            {/* コントロールパネル */}
            <div className="bg-base-100 rounded-box shadow-lg p-2">
              <h2 className="text-xl font-bold mb-2">コントロール</h2>
              <div className="flex flex-wrap gap-2 mb-4">
                <button
                  className="btn btn-primary"
                  onClick={startGame}
                  disabled={isLoading || isAutoPlaying}
                >
                  ゲーム開始
                </button>
                <button
                  className="btn btn-secondary"
                  onClick={resetGame}
                  disabled={isLoading || isAutoPlaying}
                >
                  リセット
                </button>
                <button
                  className="btn btn-accent"
                  onClick={nextTurn}
                  disabled={isLoading || isAutoPlaying || terminated || truncated || !gameState}
                >
                  次のターン
                </button>
                <button
                  className={`btn ${isAutoPlaying ? 'btn-error' : 'btn-success'}`}
                  onClick={isAutoPlaying ? stopAutoPlay : startAutoPlay}
                  disabled={isLoading || terminated || truncated || !gameState}
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
                  disabled={!isAutoPlaying} // 自動プレイ中のみ有効
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
                      disabled={isLoading} // ロード中は無効
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
            <div className="h-[calc(100vh-20rem)]"> {/* 高さを調整 */}
              <ActionLog logs={actionLog} />
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default App
