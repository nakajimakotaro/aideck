import gymnasium as gym
from gymnasium import spaces
import numpy as np
import random
from typing import List, Tuple, Optional, Dict, Any

class CardGameEnv(gym.Env):
    """
    カスタムカードゲーム環境

    ルール:
    - カード: 1から5までの数字
    - 手札: 4枚
    - Next: 1枚
    - スタック: 数字の昇順に積む (スタックトップより大きい数字のみ)
    - 得点: 1, 2, 3, 4, 5 の順に積めたら +1点
    - 合成: 同じ数字を合成して1つ上の数字に (5は不可、4+4=4)。1ターン2回まで。
    - ターン: スタックをクリアすると1ターン終了。全20ターン。
    """
    metadata = {'render_modes': ['human'], 'render_fps': 4}

    def __init__(self, render_mode: Optional[str] = None):
        super().__init__()

        self.render_mode = render_mode

        # カードの種類 (1-5)
        self.card_types = list(range(1, 6))

        # ゲーム状態
        self.hand: List[int] = []
        self.next_card: Optional[int] = None
        self.stack: List[int] = []
        self.score: int = 0
        self.current_turn: int = 0
        self.max_turns: int = 20
        self.merges_this_turn: int = 0
        self.max_merges_per_turn: int = 2

        # 状態空間の定義
        # 手札4枚 (0:空, 1-5:カード)
        # Nextカード (0:空, 1-5:カード)
        # スタックトップ (0:空, 1-5:カード)
        # 残りターン数 (0-20)
        # 残り合成回数 (0-2)
        self.observation_space = spaces.Dict({
            "hand": spaces.MultiDiscrete([6] * 4),  # 0-5
            "next": spaces.Discrete(6),             # 0-5
            "stack_top": spaces.Discrete(6),        # 0-5
            "remaining_turns": spaces.Discrete(self.max_turns + 1),
            "remaining_merges": spaces.Discrete(self.max_merges_per_turn + 1)
        })

        # 行動空間の定義
        # 0-3: 手札のカードを使用 (インデックス)
        # 4-9: 手札のカードを合成 (ペアのインデックス組み合わせ: (0,1), (0,2), (0,3), (1,2), (1,3), (2,3))
        # 10: スタックをクリア (ターン終了)
        self.action_space = spaces.Discrete(11)

        # 合成アクションとインデックスペアのマッピング
        self._merge_actions = {
            4: (0, 1), 5: (0, 2), 6: (0, 3),
            7: (1, 2), 8: (1, 3), 9: (2, 3)
        }
        self._action_to_merge_pair = {v: k for k, v in self._merge_actions.items()}


    def _draw_card(self) -> Optional[int]:
        return random.randint(1, 5)

    def _deal_initial_cards(self):
        """初期手札とNextカードを配る"""
        self.hand = [self._draw_card() for _ in range(4)]
        self.next_card = self._draw_card()

    def reset(self, seed: Optional[int] = None, options: Optional[dict] = None) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """環境をリセットする"""
        super().reset(seed=seed)

        self._deal_initial_cards()
        self.stack = []
        self.score = 0
        self.current_turn = 1
        self.merges_this_turn = 0

        observation = self._get_obs()
        info = self._get_info()

        if self.render_mode == "human":
            self._render_frame()

        return observation, info

    def _get_obs(self) -> Dict[str, Any]:
        """現在の状態を観測として取得する"""
        # 手札をソートして観測の一貫性を保つ
        sorted_hand = sorted([card for card in self.hand if card != 0])

        return {
            "hand": np.array(sorted_hand, dtype=np.int64), # 常に長さ4にする
            "next": np.int64(self.next_card if self.next_card is not None else 0),
            "stack_top": np.int64(self.stack[-1] if self.stack else 0),
            "remaining_turns": np.int64(self.max_turns - self.current_turn + 1),
            "remaining_merges": np.int64(self.max_merges_per_turn - self.merges_this_turn)
        }

    def _get_info(self) -> Dict[str, Any]:
        """追加情報を取得する"""
        return {
            "score": self.score,
            "current_turn": self.current_turn,
            "merges_this_turn": self.merges_this_turn,
            "stack_size": len(self.stack),
        }

    def _is_valid_play(self, card_to_play: int) -> bool:
        """カードがスタックにプレイ可能か"""
        if not self.stack: # スタックが空なら何でも置ける
            return True
        return card_to_play > self.stack[-1]

    def _check_score(self):
        """スタックが1-5の順になっているかチェックし、スコアを加算"""
        if self.stack == list(range(1, 6)):
            self.score += 1
            self.stack = []

    def step(self, action: int) -> Tuple[Dict[str, Any], float, bool, bool, Dict[str, Any]]:
        """行動を実行し、環境を次の状態に進める"""
        terminated = False
        truncated = False
        reward = 0.0

        # 1. 行動の解釈と実行
        if 0 <= action <= 3:  # 手札のカードを使用
            hand_idx = action
            if hand_idx < len(self.hand) and self.hand[hand_idx] != 0:
                card_to_play = self.hand[hand_idx]
                if self._is_valid_play(card_to_play):
                    # 手札から削除
                    played_card = self.hand.pop(hand_idx)
                    # スタックに追加
                    self.stack.append(played_card)
                    # Nextからドロー
                    if self.next_card is not None and self.next_card != 0:
                        self.hand.append(self.next_card)
                    # 新しいNextをドロー
                    self.next_card = self._draw_card()
                    if self.next_card is None: self.next_card = 0
                    # 手札の空きを0で埋める (常に4枚にするため)
                    while len(self.hand) < 4:
                        self.hand.append(0)

                    # スコアチェック
                    self._check_score()
                else:
                    # 無効なプレイ (本来はマスクされるはずだが、念のため)
                    reward = -0.1 # ペナルティを与えるか？
            else:
                 # 無効なインデックス or 空のスロット
                 reward = -0.1

        elif 4 <= action <= 9: # 手札のカードを合成
            if self.merges_this_turn < self.max_merges_per_turn:
                idx_pair = self._merge_actions.get(action)
                if idx_pair:
                    idx1, idx2 = idx_pair
                    if idx1 < len(self.hand) and idx2 < len(self.hand) and \
                       self.hand[idx1] != 0 and self.hand[idx1] == self.hand[idx2] and \
                       self.hand[idx1] < 5: # 5は合成不可

                        card_value = self.hand[idx1]
                        merged_card = card_value + 1 if card_value < 4 else 4 # 4+4=4

                        # 合成元を削除 (インデックスが大きい方から削除)
                        rm_idx1, rm_idx2 = sorted(idx_pair, reverse=True)
                        self.hand.pop(rm_idx1)
                        self.hand.pop(rm_idx2)

                        # 合成結果を追加
                        self.hand.append(merged_card)

                        # Nextからドローして空きを埋める
                        if self.next_card is not None and self.next_card != 0:
                            self.hand.append(self.next_card)
                        # 新しいNextをドロー
                        self.next_card = self._draw_card()
                        if self.next_card is None: self.next_card = 0

                        # 手札の空きを0で埋める
                        while len(self.hand) < 4:
                            self.hand.append(0)

                        self.merges_this_turn += 1
                    else:
                        # 無効な合成 (ペアでない、5、空きスロットなど)
                        reward = -0.1
                else:
                    # 存在しないアクションID
                    reward = -0.1
            else:
                # 合成回数超過
                reward = -0.1

        elif action == 10: # スタックをクリア (ターン終了)
            self.stack = []
            self.current_turn += 1
            self.merges_this_turn = 0
            if self.current_turn > self.max_turns:
                terminated = True # ゲーム終了
            # ターン終了時の報酬は基本0 (スコアは積んだ時に加算)

        else:
            # 未定義のアクション
            reward = -0.1 # or raise error

        # 2. 状態の更新と終了判定
        observation = self._get_obs()
        info = self._get_info()

        # ゲーム終了条件
        if self.current_turn > self.max_turns:
            terminated = True


        if self.render_mode == "human":
            self._render_frame()

        # 最終ターン終了時に最終スコアを報酬とする設計も可能
        # if terminated:
        #     reward = float(self.score)

        return observation, reward, terminated, truncated, info

    def render(self):
        """環境の現在の状態を描画する (humanモード用)"""
        if self.render_mode == "human":
            self._render_frame()

    def _render_frame(self):
        """フレームを描画する内部メソッド"""
        print("-" * 20)
        print(f"Turn: {self.current_turn}/{self.max_turns} | Score: {self.score}")
        print(f"Hand: {self.hand} | Next: {self.next_card}")
        print(f"Stack: {self.stack} (Top: {self.stack[-1] if self.stack else 'Empty'})")
        print(f"Merges this turn: {self.merges_this_turn}/{self.max_merges_per_turn}")

    def action_masks(self) -> List[bool]:
        """現在の状態で有効な行動のマスクを返す"""
        mask = [False] * self.action_space.n # 全て無効で初期化

        # 1. カード使用アクションの有効性チェック
        stack_top = self.stack[-1] if self.stack else 0
        for i in range(4):
            if i < len(self.hand) and self.hand[i] != 0 and self.hand[i] > stack_top:
                mask[i] = True

        # 2. カード合成アクションの有効性チェック
        if self.merges_this_turn < self.max_merges_per_turn:
            hand_counts = {}
            hand_indices = {}
            valid_hand = [(idx, card) for idx, card in enumerate(self.hand) if card != 0 and card < 5] # 5は合成不可

            for idx, card in valid_hand:
                if card not in hand_counts:
                    hand_counts[card] = 0
                    hand_indices[card] = []
                hand_counts[card] += 1
                hand_indices[card].append(idx)

            for card, count in hand_counts.items():
                if count >= 2:
                    # ペアが見つかった
                    indices = hand_indices[card]
                    # 考えられるペアの組み合わせ ((0,1), (0,2), (1,2)など)
                    from itertools import combinations
                    for idx1, idx2 in combinations(indices, 2):
                        # インデックスペアに対応するアクションIDを探す
                        pair = tuple(sorted((idx1, idx2)))
                        if pair in self._action_to_merge_pair:
                             action_id = self._action_to_merge_pair[pair]
                             mask[action_id] = True


        # 3. スタッククリアアクションはスタックが空でないときのみ有効
        mask[10] = len(self.stack) > 0

        return mask

    def close(self):
        """環境のリソースを解放する"""
        pass
