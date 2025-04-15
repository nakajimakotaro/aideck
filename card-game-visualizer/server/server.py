import os
import sys
import json
import random
import numpy as np
from aiohttp import web
from sb3_contrib import MaskablePPO

# myenvディレクトリをパスに追加
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../myenv')))

from card_game_env import (
    CardGameEnv,
    ACTION_PLAY_HAND_OFFSET,
    ACTION_PLAY_HOLD,
    ACTION_MERGE_OFFSET,
    ACTION_HOLD_CARD_OFFSET,
    ACTION_CLEAR_STACK
)

# AIモデルのロード（グローバルで1回のみ）
model_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../myenv/ppo_cardgame_model.zip'))
print(f"Loading AI model from: {model_path}")
model = MaskablePPO.load(model_path)
print("AI model loaded successfully")

def action_to_description(action_id: int, env: CardGameEnv) -> str:
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

def set_env_state(env: CardGameEnv, obs: dict, info: dict):
    # myenv/card_game_env.py の内部状態に合わせてセット
    env.hand = list(obs['hand'])
    env.hold_slot = obs['hold']
    env.next_card = obs['next']
    # stackはcurrent_stackを優先してセット
    if 'current_stack' in obs:
        env.stack = list(obs['current_stack'])
    elif info and 'current_stack' in info:
        env.stack = list(info['current_stack'])
    else:
        env.stack = []
    # current_turn, merges_this_turn, score, fullchain_count もセット
    if info:
        if 'current_turn' in info:
            env.current_turn = int(info['current_turn'])
        if 'merges_this_turn' in info:
            env.merges_this_turn = int(info['merges_this_turn'])
        if 'score' in info:
            env.score = float(info['score'])
        if 'fullchain_count' in info:
            env.fullchain_count = float(info['fullchain_count'])

async def next_turn(request):
    data = await request.json()
    obs = data.get('obs')
    info = data.get('info', {})
    use_random = data.get('use_random', False)

    if obs is None:
        return web.json_response({'error': 'obs is required'}, status=400)

    # 環境を生成し状態をセット
    env = CardGameEnv()
    set_env_state(env, obs, info)

    # 有効なアクションを取得
    action_masks = env.action_masks()
    valid_actions = [i for i, valid in enumerate(action_masks) if valid]
    if not valid_actions:
        return web.json_response({'error': '有効なアクションがありません'}, status=400)

    action_mask_array = np.array(action_masks)
    if use_random:
        action = random.choice(valid_actions)
        action_source = "ランダム"
    else:
        # モデルが期待する観測値形式に変換
        model_obs = {
            "hand": np.array(env.hand, dtype=np.int64),
            "hold": np.int64(0 if env.hold_slot == -1 else 1),
            "next": np.int64(0 if env.next_card == -1 else env.next_card + 1),
            "stack_top": np.int64(0 if not env.stack else env.stack[-1] + 1),
            "stacked_zeros": np.int64(env.stack.count(0)),
            "remaining_turns": np.int64(20 - env.current_turn + 1),
            "remaining_merges": np.int64(2 - env.merges_this_turn)
        }
        action, _ = model.predict(
            model_obs, # 変換後の観測値を渡す
            action_masks=action_mask_array,
            deterministic=False
        )
        action = int(action)
        action_source = "AI"

    action_desc = action_to_description(action, env)
    # 行動を実行
    _, reward, terminated, truncated, new_info = env.step(action) # new_obs は使わない

    # レスポンス用に内部状態を整形
    response_obs = {
        'hand': [int(x) for x in env.hand],
        'hold': int(env.hold_slot),
        'next': int(env.next_card),
        'stack': [int(x) for x in env.stack],
        'current_turn': int(env.current_turn),
        'merges_this_turn': int(env.merges_this_turn),
        'score': float(env.score),
        'fullchain_count': float(env.fullchain_count),
    }

    response = {
        'obs': response_obs,
        'info': new_info, # infoはそのまま返す
        'action': int(action),
        'action_desc': f"[{action_source}] {action_desc}",
        'reward': float(reward), # rewardもfloatに変換
        'terminated': terminated,
        'truncated': truncated
    }
    return web.json_response(response)

async def reset_game(request):
    try:
        env = CardGameEnv()
        _, info = env.reset() # obs は使わない

        # レスポンス用に内部状態を整形
        response_obs = {
            'hand': [int(x) for x in env.hand],
            'hold': int(env.hold_slot),
            'next': int(env.next_card),
            'stack': [int(x) for x in env.stack],
            'current_turn': int(env.current_turn),
            'merges_this_turn': int(env.merges_this_turn),
            'score': float(env.score),
            'fullchain_count': float(env.fullchain_count),
        }

        response = {
            'obs': response_obs,
            'info': info # infoはそのまま返す
        }
        return web.json_response(response)
    except Exception as e:
        print("Error in reset_game:", e)
        return web.json_response({'error': str(e)}, status=500)

def create_app():
    app = web.Application()
    app.router.add_post('/api/next_turn', next_turn)
    app.router.add_get('/api/reset', reset_game) # Resetエンドポイントを追加
    return app

if __name__ == '__main__':
    app = create_app()
    web.run_app(app, host='localhost', port=5000)
