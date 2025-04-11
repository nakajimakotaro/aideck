import gymnasium as gym
import numpy as np
from sb3_contrib import MaskablePPO
from sb3_contrib.common.wrappers import ActionMasker
import argparse
import time

from card_game_env import CardGameEnv # 作成した環境をインポート

def main(model_path: str, num_episodes: int = 5, render: bool = True):
    """
    訓練済みモデルをテストする関数

    :param model_path: 訓練済みモデルファイル (.zip) のパス
    :param num_episodes: テストするエピソード数
    :param render: ゲームプレイをレンダリングするかどうか
    """
    print(f"Loading model from {model_path}...")
    # 環境を作成 (テスト時はシングルプロセスで、レンダリングを有効にする)
    render_mode = "human" if render else None
    env = CardGameEnv(render_mode=render_mode)
    # ActionMaskerでラップ
    env = ActionMasker(env, lambda env: env.action_masks())

    # モデルをロード
    # 注意: load時にも環境 (またはその observation/action space) が必要になることがある
    # custom_objects を使うことで、load時に必要な情報を渡せる場合がある
    # MaskablePPOの場合、通常は policy='MlpPolicy' など policy の指定で十分なことが多い
    try:
        model = MaskablePPO.load(model_path, env=env, device='auto')
        print("Model loaded successfully.")
    except Exception as e:
        print(f"Error loading model: {e}")
        print("Please ensure the model was saved correctly and dependencies are installed.")
        env.close()
        return

    total_scores = []
    total_steps = []

    print(f"\nRunning {num_episodes} test episodes...")
    for episode in range(num_episodes):
        obs, info = env.reset()
        terminated = False
        truncated = False
        episode_score = 0
        episode_steps = 0

        print(f"\n--- Episode {episode + 1} ---")
        if render:
            env.render()
            #time.sleep(0.5) # 少し待機して表示を見やすくする

        while not terminated and not truncated:
            # 現在の観測と有効なアクションマスクを取得
            action_masks = env.action_masks()

            # モデルに行動を予測させる (deterministic=True で決定論的な行動を選択)
            action, _states = model.predict(obs, action_masks=action_masks, deterministic=True)

            # action は numpy 配列で返ってくることがあるため、整数に変換
            action_int = int(action.item()) if isinstance(action, np.ndarray) else int(action)
            print(f"Agent Action: {action_int}")

            # 環境で行動を実行
            obs, reward, terminated, truncated, info = env.step(action_int)
            episode_steps += 1

            if render:
                env.render()
                # time.sleep(0.5) # ステップ間の待機

            # スコアは info から取得するのが確実 (報酬はステップ毎の学習用信号)
            episode_score = info.get('score', 0) # reset時に0に戻るので最終値を取得

            if terminated or truncated:
                print(f"Episode finished after {episode_steps} steps.")
                print(f"Final Score for Episode {episode + 1}: {episode_score}")
                total_scores.append(episode_score)
                total_steps.append(episode_steps)

    env.close()
    print("\n--- Test Summary ---")
    if total_scores:
        print(f"Average Score over {num_episodes} episodes: {np.mean(total_scores):.2f}")
        print(f"Average Steps per episode: {np.mean(total_steps):.2f}")
        print(f"Max Score: {np.max(total_scores)}")
        print(f"Min Score: {np.min(total_scores)}")
    else:
        print("No episodes were completed.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test a trained MaskablePPO agent for the Card Game.")
    parser.add_argument("--model", type=str, required=True, help="Path to the trained model (.zip file)")
    parser.add_argument("--episodes", type=int, default=5, help="Number of episodes to run")
    parser.add_argument("--no-render", action="store_true", help="Disable rendering the game")
    args = parser.parse_args()

    main(model_path=args.model, num_episodes=args.episodes, render=not args.no_render)
