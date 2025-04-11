import { io, Socket } from 'socket.io-client';
import { GameState } from '../components/game/GameBoard';

// WebSocketイベントの型定義
export type WebSocketEvent = 
  | { type: 'connect' }
  | { type: 'disconnect', reason: string }
  | { type: 'error', message: string }
  | { type: 'gameState', state: GameState }
  | { type: 'action', description: string }
  | { type: 'reward', value: number };

// イベントリスナーの型
export type WebSocketEventListener = (event: WebSocketEvent) => void;

class WebSocketService {
  private socket: Socket | null = null;
  private listeners: WebSocketEventListener[] = [];
  private reconnectTimer: number | null = null;
  private url: string;

  constructor(url: string = 'http://localhost:5000') {
    this.url = url;
  }

  // WebSocketに接続
  connect(): void {
    if (this.socket) {
      return;
    }

    this.socket = io(this.url, {
      reconnectionAttempts: 5,
      reconnectionDelay: 1000,
      timeout: 10000,
    });

    // 接続イベント
    this.socket.on('connect', () => {
      console.log('WebSocket connected');
      this.notifyListeners({ type: 'connect' });
      
      // 再接続タイマーをクリア
      if (this.reconnectTimer) {
        clearTimeout(this.reconnectTimer);
        this.reconnectTimer = null;
      }
    });

    // 切断イベント
    this.socket.on('disconnect', (reason) => {
      console.log(`WebSocket disconnected: ${reason}`);
      this.notifyListeners({ type: 'disconnect', reason });
      
      // 自動再接続を試みる
      if (!this.reconnectTimer) {
        this.reconnectTimer = window.setTimeout(() => {
          this.reconnect();
        }, 3000);
      }
    });

    // エラーイベント
    this.socket.on('error', (error) => {
      console.error('WebSocket error:', error);
      this.notifyListeners({ type: 'error', message: error.message });
    });

    // ゲーム状態イベント
    this.socket.on('gameState', (state: GameState) => {
      console.log('Received game state:', state);
      this.notifyListeners({ type: 'gameState', state });
    });

    // アクションイベント
    this.socket.on('action', (description: string) => {
      console.log('Received action:', description);
      this.notifyListeners({ type: 'action', description });
    });

    // 報酬イベント
    this.socket.on('reward', (value: number) => {
      console.log('Received reward:', value);
      this.notifyListeners({ type: 'reward', value });
    });
  }

  // 再接続
  reconnect(): void {
    if (this.socket) {
      this.socket.connect();
    } else {
      this.connect();
    }
  }

  // 切断
  disconnect(): void {
    if (this.socket) {
      this.socket.disconnect();
      this.socket = null;
    }
    
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }

  // イベントリスナーを追加
  addListener(listener: WebSocketEventListener): void {
    this.listeners.push(listener);
  }

  // イベントリスナーを削除
  removeListener(listener: WebSocketEventListener): void {
    this.listeners = this.listeners.filter(l => l !== listener);
  }

  // リスナーに通知
  private notifyListeners(event: WebSocketEvent): void {
    this.listeners.forEach(listener => {
      try {
        listener(event);
      } catch (error) {
        console.error('Error in WebSocket event listener:', error);
      }
    });
  }

  // コマンドを送信
  sendCommand(command: string): void {
    if (this.socket && this.socket.connected) {
      this.socket.emit('command', command);
    } else {
      console.error('Cannot send command: WebSocket not connected');
    }
  }

  // 自動プレイを開始
  startAutoPlay(): void {
    this.sendCommand('auto:start');
  }

  // 自動プレイを停止
  stopAutoPlay(): void {
    this.sendCommand('auto:stop');
  }

  // 自動プレイの速度を設定
  setAutoPlaySpeed(speed: number): void {
    this.sendCommand(`speed:${speed}`);
  }

  // ランダムモードの切り替え
  toggleRandomMode(): void {
    this.sendCommand('random');
  }

  // 接続状態を取得
  isConnected(): boolean {
    return this.socket !== null && this.socket.connected;
  }
}

// シングルトンインスタンス
const webSocketService = new WebSocketService();
export default webSocketService;
