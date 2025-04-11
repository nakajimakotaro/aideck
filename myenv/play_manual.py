import gymnasium as gym
import numpy as np
import time
from sb3_contrib.common.wrappers import ActionMasker

from card_game_env import CardGameEnv, ACTION_PLAY_HAND_OFFSET, ACTION_PLAY_HOLD, ACTION_MERGE_OFFSET, ACTION_HOLD_CARD_OFFSET, ACTION_CLEAR_STACK

def action_to_description(action_id, env):
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

def display_game_state(env, action_masks):
    """ゲームの状態と有効なアクションを表示（簡略化形式）"""
    print("\n" + "-" * 30)
    
    # スタックの表示（S: で始まる）
    stack_str = "".join(map(str, env.stack)) if env.stack else ""
    print(f"S: {stack_str}")
    
    # 手札の表示（括弧内はNextカード、その後に手札の内容）
    hand_str = "".join(map(str, env.hand))
    print(f"({env.next_card}){hand_str}")
    
    # ホールド枠の表示（H: で始まる、空の場合は_）
    hold_card = env.hold_slot if env.hold_slot != -1 else "_"
    print(f"H: {hold_card}")
    
    # ターン情報（簡略化のため省略可能だが、デバッグに役立つので残す）
    print(f"Turn: {env.current_turn}/20 | Merges: {env.merges_this_turn}/2")
    
    # 有効なアクションの表示
    print("\n有効なアクション:")
    valid_actions = [i for i, valid in enumerate(action_masks) if valid]
    
    for i, action_id in enumerate(valid_actions):
        print(f"  [{i+1}]: {action_to_description(action_id, env)}")
    
    print("=" * 50)
    return valid_actions

def main():
    """手動プレイのメインループ"""
    print("カードゲーム手動プレイモード")
    print("ゲームルール:")
    print("- カード: 0から5までの数字")
    print("- 手札: 4枚")
    print("- ホールド: 1枚 (0のみホールド可能)")
    print("- スタック: 数字の昇順に積む (0は特殊ルールあり)")
    print("- 得点: 1, 2, 3, 4, 5 の順に積めたら +1000点")
    print("- 合成: 同じ数字を合成して1つ上の数字に (5は不可、4+4=4)。1ターン2回まで")
    print("- ターン: スタックをクリアすると1ターン終了。全20ターン")
    print("- 0カード特殊ルール: いつでも破棄可能、ホールド枠には0のみ置ける")
    
    # 環境の作成
    env = CardGameEnv(render_mode="human")
    
    # ゲームの初期化
    obs, info = env.reset()
    terminated = False
    truncated = False
    total_reward = 0
    
    # ゲームループ
    while not terminated and not truncated:
        # 有効なアクションマスクを取得
        action_masks = env.action_masks()
        
        # ゲーム状態と有効なアクションを表示
        valid_actions = display_game_state(env, action_masks)
        
        if not valid_actions:
            print("有効なアクションがありません。ゲーム終了。")
            break
        
        # ユーザーからの入力を受け取る
        try:
            choice = int(input("\nアクションを選択してください (番号): "))
            if 1 <= choice <= len(valid_actions):
                action_id = valid_actions[choice - 1]
                print(f"選択: {action_to_description(action_id, env)}")
                
                # 環境でアクションを実行
                obs, reward, terminated, truncated, info = env.step(action_id)
                total_reward += reward
                
                # 報酬の表示
                if reward != 0:
                    print(f"報酬: {reward}")
            else:
                print("無効な選択です。もう一度お試しください。")
        except ValueError:
            print("数字を入力してください。")
        except KeyboardInterrupt:
            print("\nゲームを終了します。")
            break
    
    # ゲーム終了時の表示
    if terminated:
        print("\nゲーム終了!")
    elif truncated:
        print("\nゲームが途中で終了しました。")
    
    print(f"最終スコア: {total_reward}")
    env.close()

if __name__ == "__main__":
    main()
