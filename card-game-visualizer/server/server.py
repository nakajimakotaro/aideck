import asyncio
import json
import os
import sys
import time
import random
import numpy as np
from typing import Dict, List, Any, Optional

import socketio
from aiohttp import web
from sb3_contrib import MaskablePPO
from sb3_contrib.common.wrappers import ActionMasker

# myenvディレクトリをパスに追加
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../myenv')))

# カードゲーム環境をインポート
from card_game_env import (
    CardGameEnv, 
    ACTION_PLAY_HAND_OFFSET, 
    ACTION_PLAY_HOLD, 
    ACTION_MERGE_OFFSET, 
    ACTION_HOLD_CARD_OFFSET, 
    ACTION_CLEAR_STACK
)

# アクションをテキスト説明に変換する関数
def action_to_description(action_id: int, env: CardGameEnv) -> str:
    """アクションIDを人間が読める説明に変換する"""
    if ACTION_PLAY_HAND_OFFSET <= action_id < ACTION_PLAY_HOLD:
        hand_idx = action_id - ACTION_PLAY_HAND_OFFSET
        card = env.hand[hand_idx]
        return f"手札の{hand_idx+1}番目のカード({card})をプレイ"
    
    elif action_id == ACTION_PLAY_HOLD:
        card = env.hold_slot
        return f"ホールド枠のカード({card})をプレイ"
    
    elif ACTION_MERGE_OFFSET <= action_id < ACTION_HOLD_CARD_OFFSET:
        idx_pair = env._action_to_merge_pair.get(action_id)
        if idx_pair:
            idx1, idx2 = idx_pair
            card1, card2 = env.hand[idx1], env.hand[idx2]
            return f"手札の{idx1+1}番目({card1})と{idx2+1}番目({card2})のカードを合成"
    
    elif ACTION_HOLD_CARD_OFFSET <= action_id < ACTION_CLEAR_STACK:
        hand_idx = action_id - ACTION_HOLD_CARD_OFFSET
        card = env.hand[hand_idx]
        return f"手札の{hand_idx+1}番目のカード({card})をホールド"
    
    elif action_id == ACTION_CLEAR_STACK:
        return "スタックをクリア"
    
    return f"不明なアクション: {action_id}"

class GameServer:
    def __init__(self):
        # Socket.IOサーバーの設定
        self.sio = socketio.AsyncServer(
            async_mode='aiohttp',
            cors_allowed_origins='*'
        )
        self.app = web.Application()
        self.sio.attach(self.app)
        
        # ゲーム環境の初期化
        self.env = CardGameEnv()
        self.obs = None
        self.info = None
        self.running = False
        self.auto_play = False
        self.auto_play_speed = 1.5  # 自動プレイの速度（秒）
        self.full_chain_count = 0  # フルチェインの回数を追跡
        self.use_random_action = False  # デバッグ用：ランダムアクション選択モード
        
        # AIモデルの読み込み
        model_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../myenv/2ppo_cardgame_model.zip'))
        print(f"Loading AI model from: {model_path}")
            
        # モデルの読み込みを試みる
        self.model = MaskablePPO.load(model_path)
        print("AI model loaded successfully")
        self.use_ai = True
        
        # イベントハンドラの設定
        self.setup_event_handlers()
    
    def setup_event_handlers(self):
        @self.sio.event
        async def connect(sid, environ):
            print(f"Client connected: {sid}")
            # 接続時に現在の状態を送信
            if self.obs is not None:
                await self.send_game_state(sid)
        
        @self.sio.event
        async def disconnect(sid):
            print(f"Client disconnected: {sid}")
        
        @self.sio.event
        async def command(sid, data):
            print(f"Received command: {data}")
            if data == 'start':
                await self.start_game(sid)
            elif data == 'reset':
                await self.reset_game(sid)
            elif data == 'next':
                await self.next_turn(sid)
            elif data.startswith('auto:'):
                # auto:start または auto:stop
                command = data.split(':')[1]
                if command == 'start':
                    self.auto_play = True
                    await self.sio.emit('action', "自動プレイを開始しました", room=sid)
                    if self.running:
                        asyncio.create_task(self.auto_play_loop(sid))
                elif command == 'stop':
                    self.auto_play = False
                    await self.sio.emit('action', "自動プレイを停止しました", room=sid)
            elif data.startswith('speed:'):
                # speed:1.0 のような形式
                try:
                    speed_value = float(data.split(':')[1])
                    # 速度は0.1秒から3.0秒の範囲に制限
                    self.auto_play_speed = max(0.1, min(3.0, speed_value))
                    await self.sio.emit('action', f"自動プレイ速度を{self.auto_play_speed:.1f}秒に設定しました", room=sid)
                except ValueError:
                    await self.sio.emit('action', "無効な速度値です", room=sid)
            elif data == 'random':
                self.use_random_action = not self.use_random_action
                await self.sio.emit('action', f"ランダムアクションモードを{'有効' if self.use_random_action else '無効'}にしました", room=sid)
    
    async def start_game(self, sid):
        """ゲームを開始する"""
        self.obs, self.info = self.env.reset()
        self.running = True
        self.full_chain_count = 0  # フルチェインカウントをリセット
        await self.send_game_state(sid)
        await self.sio.emit('action', "ゲームを開始しました", room=sid)
        
        if self.auto_play:
            asyncio.create_task(self.auto_play_loop(sid))
    
    async def reset_game(self, sid):
        """ゲームをリセットする"""
        self.obs, self.info = self.env.reset()
        self.running = True
        self.full_chain_count = 0  # フルチェインカウントをリセット
        await self.send_game_state(sid)
        await self.sio.emit('action', "ゲームをリセットしました", room=sid)
    
    async def next_turn(self, sid):
        """次のターンに進む（AIが行動を選択）"""
        if not self.running:
            await self.sio.emit('action', "ゲームが開始されていません", room=sid)
            return
        
        await self.perform_ai_action(sid)
    
    async def auto_play_loop(self, sid):
        """自動プレイループ"""
        while self.auto_play and self.running:
            await self.perform_ai_action(sid)
            await asyncio.sleep(self.auto_play_speed)  # 設定された速度で遅延
    
    async def perform_ai_action(self, sid):
        """AIが行動を選択して実行する"""
        if not self.running:
            return
        
        # 有効なアクションを取得
        action_masks = self.env.action_masks()
        valid_actions = [i for i, valid in enumerate(action_masks) if valid]
        
        if not valid_actions:
            await self.sio.emit('action', "有効なアクションがありません", room=sid)
            self.running = False
            return
        
        # 現在の観測を取得
        action_mask_array = np.array(action_masks)
        
        if self.use_random_action:
            # デバッグモード：有効なアクションからランダムに選択
            action = random.choice(valid_actions)
            action_source = "ランダム"
        else:
            # AIモデルで行動を予測
            action, _ = self.model.predict(
                self.obs,
                action_masks=action_mask_array,
                deterministic=False  # 確率的な選択（探索あり）
            )
            action_source = "AI"
        
        # 整数型に変換
        action = int(action)
        
        # 行動の説明を取得
        action_desc = action_to_description(action, self.env)
        await self.sio.emit('action', f"[{action_source}] {action_desc}", room=sid)
        
        # 行動を実行
        self.obs, reward, terminated, truncated, self.info = self.env.step(action)
        
        # フルチェインの検出
        # スタッククリアアクションの場合、infoからフルチェインかどうかを確認
        if action == ACTION_CLEAR_STACK and reward > 0:
            self.full_chain_count += 1  # フルチェインカウンターをインクリメント
            await self.sio.emit('action', f"フルチェイン達成！ 通算{self.full_chain_count}回目）", room=sid)
        
        # 報酬があれば送信
        if reward != 0:
            await self.sio.emit('reward', reward, room=sid)
        
        # 更新された状態を送信
        await self.send_game_state(sid)
        
        # ゲーム終了判定
        if terminated or truncated:
            self.running = False
            await self.sio.emit('action', "ゲームが終了しました", room=sid)
    
    async def send_game_state(self, sid):
        """現在のゲーム状態をクライアントに送信する"""
        if self.obs is None:
            return
        
        # 観測とinfoを組み合わせてゲーム状態を作成
        game_state = {
            'hand': self.obs['hand'].tolist(),
            'hold': int(self.obs['hold']),
            'next': int(self.obs['next']),
            'stack_top': int(self.obs['stack_top']),
            'stacked_zeros': int(self.obs['stacked_zeros']),
            'remaining_turns': int(self.obs['remaining_turns']),
            'remaining_merges': int(self.obs['remaining_merges']),
            'full_chain_count': self.full_chain_count,  # フルチェインの回数を追加
        }
        
        # infoからスタック全体を追加（利用可能な場合）
        if 'current_stack' in self.info:
            game_state['current_stack'] = self.info['current_stack']
        
        await self.sio.emit('gameState', game_state, room=sid)
    
    def run(self, host='localhost', port=5000):
        """サーバーを起動する"""
        print(f"Starting server at http://{host}:{port}")
        web.run_app(self.app, host=host, port=port)

if __name__ == '__main__':
    server = GameServer()
    server.run()
