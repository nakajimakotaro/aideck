import { useState, useEffect } from 'react';
import Card from './Card';

// ゲーム状態の型定義
export interface GameState {
  hand: number[];
  hold: number; // 0: ホールドなし, 1: 0をホールド
  next: number; // 0: 空, 1-6: カード (1が0カード、2が1カード...)
  stack_top: number; // 0: 空, 1-6: カード
  stacked_zeros: number;
  remaining_turns: number;
  remaining_merges: number;
  current_stack?: number[]; // スタック全体（情報として提供される場合）
  full_chain_count: number; // フルチェインの回数
}

// アニメーション状態の型定義
interface AnimationState {
  type: 'play' | 'merge' | 'hold' | 'clear';
  sourceIndex?: number;
  targetIndex?: number;
  value?: number;
  isActive: boolean;
  sourceText?: string;
  targetText?: string;
  stackText?: string;
}

interface GameBoardProps {
  gameState: GameState | null;
  lastAction?: string;
}

const GameBoard = ({ gameState, lastAction }: GameBoardProps) => {
  const [animation, setAnimation] = useState<AnimationState>({
    type: 'play',
    isActive: false
  });

  // アクションが変更されたときにアニメーションを設定
  useEffect(() => {
    if (lastAction) {
      // アクションに基づいてアニメーションを設定
      if (lastAction.includes('プレイ')) {
        const sourceIndex = parseInt(lastAction.match(/(\d+)番目/)?.[1] || '0') - 1;
        setAnimation({
          type: 'play',
          sourceIndex: sourceIndex,
          isActive: true,
          sourceText: 'プレイ'
        });
      } else if (lastAction.includes('合成')) {
        const matches = lastAction.match(/(\d+)番目.*?(\d+)番目/);
        if (matches) {
          const sourceIndex = parseInt(matches[1]) - 1;
          const targetIndex = parseInt(matches[2]) - 1;
          setAnimation({
            type: 'merge',
            sourceIndex: sourceIndex,
            targetIndex: targetIndex,
            isActive: true,
            sourceText: '合成元',
            targetText: '合成先',
            stackText: '合成'
          });
        }
      } else if (lastAction.includes('ホールド')) {
        const sourceIndex = parseInt(lastAction.match(/(\d+)番目/)?.[1] || '0') - 1;
        setAnimation({
          type: 'hold',
          sourceIndex: sourceIndex,
          isActive: true,
          sourceText: 'ホールド'
        });
      } else if (lastAction.includes('クリア')) {
        setAnimation({
          type: 'clear',
          isActive: true,
          stackText: 'クリア'
        });
      }
      
      // アニメーション中に自動的にアニメーションを無効化するタイマーを設定
      const timer = setTimeout(() => {
        setAnimation(prev => ({ ...prev, isActive: false }));
      }, 150); // アニメーション途中で無効化（Card.tsxのアニメーション時間は400ms）
      
      // コンポーネントがアンマウントされたときにタイマーをクリア
      return () => clearTimeout(timer);
    } else {
      // lastActionが空の場合、アニメーションをリセット
      setAnimation(prev => ({ ...prev, isActive: false }));
    }
  }, [lastAction]);

  if (!gameState) {
    return (
      <div className="flex items-center justify-center h-full">
        <p className="text-xl">ゲーム状態を読み込み中...</p>
      </div>
    );
  }

  // 内部表現から実際の値に変換
  const holdCard = gameState.hold === 1 ? 0 : -1; // 1 -> 0をホールド, 0 -> ホールドなし
  const nextCard = gameState.next === 0 ? -1 : gameState.next - 1; // 0 -> 空, 1-6 -> 0-5
  const stackTop = gameState.stack_top === 0 ? -1 : gameState.stack_top - 1; // 0 -> 空, 1-6 -> 0-5

  // スタックの再構築（完全なスタック情報がない場合）
  const stack = gameState.current_stack || 
    (stackTop >= 0 ? [stackTop] : []);

  return (
    <div className="game-board flex flex-col items-center justify-between h-full py-4">
      {/* ゲーム情報 */}
      <div className="game-info flex justify-between w-full px-2 mb-2">
        <div className="stats shadow">
          <div className="stat">
            <div className="stat-title">ターン</div>
            <div className="stat-value">{21 - gameState.remaining_turns}/20</div>
          </div>
          <div className="stat">
            <div className="stat-title">残り合成</div>
            <div className="stat-value">{gameState.remaining_merges}</div>
          </div>
          <div className="stat">
            <div className="stat-title">フルチェイン</div>
            <div className="stat-value text-success">{gameState.full_chain_count}回</div>
          </div>
        </div>
      </div>

      {/* スタック領域 */}
      <div className="stack-area h-32 w-full flex justify-end mb-2 pr-2">
        <div className="flex flex-row-reverse gap-2">
          {stack.length > 0 ? (
            stack.map((card, index) => (
              <Card
                key={`stack-${index}`}
                value={card}
                position="stack"
                index={index}
                isAnimating={
                  (animation.type === 'clear' && animation.isActive) ||
                  (animation.type === 'merge' && animation.isActive && index === 0)
                }
                animationType={
                  animation.type === 'clear' ? 'clear' : 
                  (animation.type === 'merge' && index === 0) ? 'stack' : undefined
                }
                animationText={
                  animation.type === 'clear' ? animation.stackText :
                  (animation.type === 'merge' && index === 0) ? animation.stackText : undefined
                }
              />
            ))
          ) : (
            <div className="w-24 h-32"></div> // スタックが空の場合のスペース確保
          )}
        </div>
      </div>

      {/* 手札、Next、ホールド領域 */}
      <div className="hand-area w-full">
        <div className="flex justify-between mb-4">
          {/* 手札 */}
          <div className="hand-cards h-32 flex-grow mr-2">
            <div className="text-sm text-gray-500 mb-1">手札</div>
            <div className="flex flex-row">
              {gameState.hand.map((card, index) => (
                <Card
                  key={`hand-${index}`}
                  value={card}
                  position="hand"
                  index={index}
                  className="mr-2"
                  isAnimating={
                    (animation.type === 'play' && animation.sourceIndex === index) ||
                    (animation.type === 'merge' && (animation.sourceIndex === index || animation.targetIndex === index)) ||
                    (animation.type === 'hold' && animation.sourceIndex === index)
                  }
                  animationType={
                    animation.type === 'play' && animation.sourceIndex === index ? 'play' :
                    animation.type === 'merge' && animation.sourceIndex === index ? 'source' :
                    animation.type === 'merge' && animation.targetIndex === index ? 'target' :
                    animation.type === 'hold' && animation.sourceIndex === index ? 'hold' : undefined
                  }
                  animationText={
                    animation.type === 'play' && animation.sourceIndex === index ? animation.sourceText :
                    animation.type === 'merge' && animation.sourceIndex === index ? animation.sourceText :
                    animation.type === 'merge' && animation.targetIndex === index ? animation.targetText :
                    animation.type === 'hold' && animation.sourceIndex === index ? animation.sourceText : undefined
                  }
                />
              ))}
            </div>
          </div>

          {/* ネクストカード */}
          <div className="next-area mx-2">
            <div className="text-sm text-gray-500 mb-1">Next</div>
            <div className="flex justify-center">
              {nextCard === -1 ? (
                <div className="border-2 border-dashed border-gray-300 rounded-lg w-24 h-32 flex items-center justify-center">
                  <span className="text-gray-400">空</span>
                </div>
              ) : (
                <Card
                  value={nextCard}
                  position="next"
                />
              )}
            </div>
          </div>

          {/* ホールド枠 */}
          <div className="hold-area ml-2">
            <div className="text-sm text-gray-500 mb-1">ホールド</div>
            <div className="flex justify-center">
              {holdCard === -1 ? (
                <div className="border-2 border-dashed border-gray-300 rounded-lg w-24 h-32 flex items-center justify-center">
                  <span className="text-gray-400">空</span>
                </div>
              ) : (
                <Card
                  value={holdCard}
                  position="hold"
                  isAnimating={animation.type === 'hold' && animation.isActive}
                  animationType="hold"
                  animationText={animation.type === 'hold' && animation.isActive ? 'ホールド中' : undefined}
                />
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default GameBoard;
