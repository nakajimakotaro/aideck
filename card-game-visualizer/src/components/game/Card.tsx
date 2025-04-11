import { CSSProperties, useEffect, useState } from 'react';

export interface CardProps {
  value: number;
  position?: 'hand' | 'hold' | 'stack' | 'next';
  index?: number;
  onClick?: () => void;
  style?: CSSProperties;
  className?: string;
  isAnimating?: boolean;
  animationType?: 'stack' | 'source' | 'target' | 'hold' | 'play' | 'clear';
  animationText?: string;
}

const Card = ({ 
  value, 
  position = 'hand', 
  index = 0, 
  onClick, 
  style, 
  className = '',
  isAnimating = false,
  animationType,
  animationText
}: CardProps) => {
  // 内部でアニメーション状態を管理
  const [internalAnimating, setInternalAnimating] = useState(isAnimating);
  const [showTip, setShowTip] = useState(isAnimating);
  const [showFlash, setShowFlash] = useState(false);

  // 外部のisAnimatingプロパティが変更されたときに内部状態を更新
  useEffect(() => {
    setInternalAnimating(isAnimating);
    setShowTip(isAnimating);
    
    // アニメーションが開始されたら、一定時間後に自動的に終了する
    if (isAnimating) {
      // アニメーション自体は200ms後に終了
      const animationTimer = setTimeout(() => {
        setInternalAnimating(false);
        // アニメーション終了時にフラッシュエフェクトを表示
        setShowFlash(true);
        
        // フラッシュエフェクトは100ms後に非表示
        setTimeout(() => {
          setShowFlash(false);
        }, 100);
      }, 200);
      
      // ツールチップは400ms後に非表示にする（アニメーションが終わった後も少し表示しておく）
      const tipTimer = setTimeout(() => {
        setShowTip(false);
      }, 400);
      
      return () => {
        clearTimeout(animationTimer);
        clearTimeout(tipTimer);
      };
    }
  }, [isAnimating]);
  // カードの色を値に基づいて決定
  const getCardColor = () => {
    switch (value) {
      case 0: return 'bg-gray-200 text-gray-800'; // 0は灰色
      case 1: return 'bg-blue-200 text-blue-800'; // 1は青
      case 2: return 'bg-green-200 text-green-800'; // 2は緑
      case 3: return 'bg-yellow-200 text-yellow-800'; // 3は黄
      case 4: return 'bg-orange-200 text-orange-800'; // 4はオレンジ
      case 5: return 'bg-red-200 text-red-800'; // 5は赤
      default: return 'bg-gray-100 text-gray-500'; // デフォルト
    }
  };

  // 位置に基づいたスタイルの調整
  const getPositionStyle = (): CSSProperties => {
    switch (position) {
      case 'hand':
        return { 
          zIndex: index
        };
      case 'stack':
        return { 
          zIndex: index
        };
      case 'hold':
        return {};
      case 'next':
        return {};
      default:
        return {};
    }
  };

  // アニメーション用のクラス
  const getAnimationClass = () => {
    // アニメーションがアクティブでない場合は、トランジションのみを適用して元の状態に戻るようにする
    if (!internalAnimating) return 'transition-all duration-150 ease-in transform-none scale-100 rotate-0 shadow-md';
    
    switch (animationType) {
      case 'stack':
        return 'transition-all duration-100 ease-out scale-110 shadow-lg shadow-blue-500/70 translate-y-[-3px]';
      case 'source':
        return 'transition-all duration-100 ease-out translate-y-[-8px] shadow-lg shadow-green-500/70 scale-105';
      case 'target':
        return 'transition-all duration-100 ease-out scale-115 shadow-lg shadow-green-500/70 rotate-3';
      case 'hold':
        return 'transition-all duration-100 ease-out scale-110 shadow-lg shadow-yellow-500/70 translate-y-[-3px]';
      case 'play':
        return 'transition-all duration-100 ease-out translate-y-[-8px] shadow-lg shadow-blue-500/70 scale-105';
      case 'clear':
        return 'transition-all duration-100 ease-out rotate-12 shadow-lg shadow-purple-500/70 scale-110';
      default:
        return 'transition-all duration-100 ease-out';
    }
  };

  return (
    <div 
      className={`
        card w-24 h-32 shadow-md cursor-pointer relative
        ${getCardColor()}
        ${getAnimationClass()}
        ${className}
      `}
      style={{
        ...getPositionStyle(),
        ...style
      }}
      onClick={onClick}
    >
      <div className="card-body items-center justify-center p-2">
        <div className="text-4xl font-bold">{value}</div>
      </div>
      
      {/* アニメーションテキスト - 小さく表示 */}
      {showTip && animationText && (
        <div className="absolute -top-6 left-0 right-0 text-center">
          <div className="inline-block bg-black bg-opacity-80 text-white px-1.5 py-0.5 rounded-md text-xs font-bold">
            {animationText}
          </div>
        </div>
      )}
      
      {/* フラッシュエフェクト - ピカーンとした光るエフェクト */}
      {showFlash && (
        <div className="absolute inset-0 bg-white bg-opacity-60 rounded-md animate-pulse z-10 transition-opacity duration-100"></div>
      )}
    </div>
  );
};

export default Card;
