import { useRef, useEffect } from 'react';

interface ActionLogProps {
  logs: string[];
}

const ActionLog = ({ logs }: ActionLogProps) => {
  const logEndRef = useRef<HTMLDivElement>(null);

  // 新しいログが追加されたときに自動スクロール
  useEffect(() => {
    if (logEndRef.current) {
      logEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs]);

  // ログの種類に基づいてスタイルを適用
  const getLogStyle = (log: string) => {
    if (log.includes('合成')) {
      return 'bg-green-100 border-l-4 border-green-500';
    } else if (log.includes('クリア')) {
      return 'bg-purple-100 border-l-4 border-purple-500';
    } else if (log.includes('プレイ')) {
      return 'bg-blue-100 border-l-4 border-blue-500';
    } else if (log.includes('ホールド')) {
      return 'bg-yellow-100 border-l-4 border-yellow-500';
    } else if (log.includes('報酬')) {
      return 'bg-red-100 border-l-4 border-red-500 font-bold';
    } else {
      return 'bg-gray-100 border-l-4 border-gray-500';
    }
  };

  // タイムスタンプを追加
  const formatLog = (log: string, index: number) => {
    // 最新の10件のログには「新規」バッジを表示
    const isNew = index >= logs.length - 10;
    
    return (
      <div className={`p-3 rounded-r mb-2 ${getLogStyle(log)}`}>
        <div className="flex justify-between items-start">
          <span>{log}</span>
          {isNew && <span className="badge badge-sm badge-accent ml-2">新規</span>}
        </div>
      </div>
    );
  };

  return (
    <div className="action-log h-full overflow-y-auto p-2">
      {logs.length === 0 ? (
        <div className="text-center text-gray-500 p-4">
          ログはまだありません
        </div>
      ) : (
        <>
          {logs.map((log, index) => (
            <div key={index}>
              {formatLog(log, index)}
            </div>
          ))}
          <div ref={logEndRef} />
        </>
      )}
    </div>
  );
};

export default ActionLog;
