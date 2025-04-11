import gymnasium as gym
from stable_baselines3.common.env_util import make_vec_env
from stable_baselines3.common.vec_env import SubprocVecEnv # For multiprocessing
from sb3_contrib import MaskablePPO
from sb3_contrib.common.wrappers import ActionMasker

from card_game_env import CardGameEnv # 作成した環境をインポート

# 環境をMaskable PPO用にラップする関数
def make_masked_env(env_id, rank, seed=0):
    """
    Utility function for multiprocessed env.

    :param env_id: (str) the environment ID
    :param num_env: (int) the number of environments you wish to have in subprocesses
    :param seed: (int) the inital seed for RNG
    :param rank: (int) index of the subprocess
    """
    def _init():
        # ここで CardGameEnv を直接インスタンス化
        env = CardGameEnv()
        # ActionMaskerでラップ
        env = ActionMasker(env, lambda env: env.action_masks())
        # シードを設定 (重要: 各プロセスで異なるシード)
        env.reset(seed=seed + rank)
        return env
    return _init

if __name__ == "__main__":
    env_id = "CardGameEnv-v0" # 任意のID (Gymnasiumに登録する場合は必要)
    num_cpu = 4  # 並列処理に使用するCPUコア数 (環境に合わせて調整)
    total_timesteps = 1_000_000 # 総学習ステップ数 (調整可能)
    log_dir = "./ppo_cardgame_logs/" # ログの保存先
    model_save_path = "./ppo_cardgame_model" # モデルの保存先

    print("Creating vectorized environment...")
    # SubprocVecEnv を使用してマルチプロセスで環境を実行
    # make_masked_env 関数を渡す
    vec_env = SubprocVecEnv([make_masked_env(env_id, i) for i in range(num_cpu)])

    print("Initializing MaskablePPO model...")
    # MaskablePPOモデルの初期化
    # Dict観測空間を使用しているため、MultiInputPolicyを指定
    model = MaskablePPO(
        "MultiInputPolicy", # MlpPolicyから変更
        vec_env,
        verbose=1,
        tensorboard_log=log_dir,
        learning_rate=3e-4, # 学習率 (調整可能)
        n_steps=2048,       # 各更新でのステップ数 (調整可能)
        batch_size=64,      # バッチサイズ (調整可能)
        n_epochs=10,        # 各更新でのエポック数 (調整可能)
        gamma=0.99,         # 割引率 (調整可能)
        gae_lambda=0.95,    # GAEラムダ (調整可能)
        clip_range=0.2,     # PPOクリップ範囲 (調整可能)
        ent_coef=0.0,       # エントロピー係数 (調整可能)
        vf_coef=0.5,        # Value function係数 (調整可能)
        max_grad_norm=0.5,  # 勾配クリッピング (調整可能)
        device="auto"       # 自動でデバイス選択 (CPU or GPU)
    )

    print(f"Starting training for {total_timesteps} timesteps...")
    # モデルの学習
    model.learn(
        total_timesteps=total_timesteps,
        log_interval=1, # ログ出力頻度 (エピソード数)
        progress_bar=True # プログレスバー表示
    )

    print(f"Training finished. Saving model to {model_save_path}...")
    # 学習済みモデルの保存
    model.save(model_save_path)

    print("Closing environment...")
    # 環境を閉じる
    vec_env.close()

    print("Done.")
    print(f"To view logs, run: tensorboard --logdir {log_dir}")
    print(f"To test the model, run: python test.py --model {model_save_path}.zip")
