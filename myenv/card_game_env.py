import gymnasium as gym
from gymnasium import spaces
import numpy as np
import random
from typing import List, Tuple, Optional, Dict, Any
from collections import Counter
from itertools import combinations, product

# --- 定数定義 ---
CARD_TYPES = list(range(0, 6)) # 0を追加
MAX_CARD_VALUE = 5
HAND_SIZE = 4
HOLD_SIZE = 1 # ホールド枠のサイズ
# EMPTY_SLOT = -1 # 空スロットの概念を削除 (ただし、hold=-1は「ホールドなし」として使用)
MAX_TURNS = 20
MAX_MERGES_PER_TURN = 2
MERGE_LIMIT_VALUE = 4 # 4+4=4, 5は合成不可
ZERO_DRAW_RATE = 0.05 # 0カードのドロー率

# アクション定義 (再構成)
# 0-3: 手札のカードをプレイ
# 4: ホールド枠のカードをプレイ
# 5-10: 手札のカードを合成 (ペアのインデックス組み合わせ)
# 11-14: 手札のカードをホールド (インデックス) - 上書き可能
# 15: スタックをクリア
ACTION_PLAY_HAND_OFFSET = 0
ACTION_PLAY_HOLD = HAND_SIZE # 4
ACTION_MERGE_OFFSET = HAND_SIZE + HOLD_SIZE # 4 + 1 = 5
_NUM_MERGE_COMBINATIONS = len(list(combinations(range(HAND_SIZE), 2))) # 6
ACTION_HOLD_CARD_OFFSET = ACTION_MERGE_OFFSET + _NUM_MERGE_COMBINATIONS # 5 + 6 = 11
ACTION_CLEAR_STACK = ACTION_HOLD_CARD_OFFSET + HAND_SIZE # 11 + 4 = 15
NUM_ACTIONS = ACTION_CLEAR_STACK + 1 # 16

# 報酬定義
REWARD_FULL_CHAIN = 1000.0
REWARD_ZERO_MULTIPLIER = 2 # 0カードによる報酬倍率
PENALTY_INVALID_ACTION = -0.1

class CardGameEnv(gym.Env):
    """
    カスタムカードゲーム環境 (Number:0, ホールド機能追加版)

    ルール:
    - カード: 0から5までの数字 (CARD_TYPES)
    - 手札: 4枚 (HAND_SIZE)
    - ホールド: 1枚 (HOLD_SIZE), 0のみホールド可能
    - Next: 1枚
    - スタック:
        - 1以上: 数字の昇順に積む (スタックトップより大きい数字のみ)
        - 0: 連続して積める (スタックトップが0の場合のみ)
        - 1以上が積まれている場合、0は積めない
    - 得点:
        - 1, 2, 3, 4, 5 の順に積めたら +1点 (REWARD_FULL_CHAIN)
        - スタッククリア時、スタックにあった0の枚数nに応じて報酬 x (REWARD_ZERO_MULTIPLIER ^ n)
    - 合成: 同じ数字を合成して1つ上の数字に (5は不可、4+4=4)。1ターン2回まで (MAX_MERGES_PER_TURN)。
    - ターン: スタックをクリアすると1ターン終了。全20ターン (MAX_TURNS)。
    - 0カード特殊ルール:
        - いつでも破棄可能 (手札・ホールドから)。破棄するとNextから補充。
        - ホールド枠には0のみ置ける。
    """
    metadata = {'render_modes': ['human'], 'render_fps': 4}

    def __init__(self, render_mode: Optional[str] = None):
        super().__init__()

        self.render_mode = render_mode

        # --- ゲーム状態変数 ---
        self.hand: List[int] = [] # 初期化は reset で行う
        self.hold_slot: int = -1 # ホールド枠 (-1: ホールドなし, 0: 0をホールド)
        self.next_card: int = -1 # Nextカード (-1: 空)
        self.stack: List[int] = []
        self.current_turn: int = 0
        self.merges_this_turn: int = 0
        self.score: float = 0.0  # スコアを保持する変数を追加

        # --- 状態空間 ---
        # 手札 (0-5:カード) - 空の概念なし
        # ホールド枠 (0:ホールドなし, 1:カード)
        # Nextカード (0:空, 1-6:カード)
        # スタックトップ (0:空, 1-6:カード)
        # 残りターン数
        # 残り合成回数
        # スタック上の0の数
        self.observation_space = spaces.Dict({
            "hand": spaces.MultiDiscrete([MAX_CARD_VALUE + 1] * HAND_SIZE), # 0から5まで (空なし)
            "hold": spaces.Discrete(2), # 0: ホールドなし, 1: 0をホールド
            "next": spaces.Discrete(MAX_CARD_VALUE + 2), # 0から6まで (0は空を表す)
            "stack_top": spaces.Discrete(MAX_CARD_VALUE + 2), # 0から6まで (0は空を表す)
            "stacked_zeros": spaces.Discrete(HAND_SIZE + HOLD_SIZE + 1), # スタックされうる0の最大数 + 1
            "remaining_turns": spaces.Discrete(MAX_TURNS + 1),
            "remaining_merges": spaces.Discrete(MAX_MERGES_PER_TURN + 1)
        })

        # --- 行動空間 ---
        self.action_space = spaces.Discrete(NUM_ACTIONS)

        # 合成アクションとインデックスペアのマッピング
        self._merge_idx_pairs = list(combinations(range(HAND_SIZE), 2))
        self._action_to_merge_pair = {
            ACTION_MERGE_OFFSET + i: pair
            for i, pair in enumerate(self._merge_idx_pairs)
        }
        self._merge_pair_to_action = {v: k for k, v in self._action_to_merge_pair.items()}

    # --- カード操作メソッド ---
    def _count_specific_card_on_board(self, card_value: int) -> int:
        """現在の盤面にある特定のカードの枚数を数える (手札、ホールド、Next、スタック)"""
        count = self.hand.count(card_value)
        if self.hold_slot == card_value:
            count += 1
        if self.next_card == card_value:
            count += 1
        count += self.stack.count(card_value)
        return count

    def _draw_card(self) -> int:
        """
        カードを山札から引く。
        - 0カードは ZERO_DRAW_RATE (5%) の確率で引く。
        - 盤面に「5」が既に1枚ある場合は「5」を引かないようにする。
        - 引くカードがない場合はエラーとする (空の概念がないため)。
        """
        # 0カードを引くか判定
        if random.random() < ZERO_DRAW_RATE:
            return 0

        # 0以外を引く場合
        available_cards = list(range(1, MAX_CARD_VALUE + 1)) # 1から5

        # 盤面の5の数をチェック
        if self._count_specific_card_on_board(MAX_CARD_VALUE) >= 1:
            if MAX_CARD_VALUE in available_cards:
                available_cards.remove(MAX_CARD_VALUE)

        return random.choice(available_cards) # インデントを if ブロックに合わせる

    def _deal_initial_cards(self):
        """初期手札、Nextカードを配る。ホールドは -1 (空)"""
        self.hand = [self._draw_card() for _ in range(HAND_SIZE)]
        self.hold_slot = -1 # 初期ホールドは空
        self.next_card = self._draw_card()

    def _replace_card_in_hand(self, index: int):
        """指定された手札のカードをNextカードで補充し、新しいNextカードを引く"""
        if 0 <= index < HAND_SIZE:
            self.hand[index] = self.next_card
            self.next_card = self._draw_card() # 新しいNextを引く

    def _remove_and_replace_merged_cards(self, idx1: int, idx2: int, merged_card: int):
        """合成元のカードを削除し、合成結果とNextカードで補充する"""
        # idx1, idx2 は hand 配列に対するインデックス
        indices_to_replace = sorted([idx1, idx2])

        # 1枚目を合成結果で置き換え
        self.hand[indices_to_replace[0]] = merged_card
        # 2枚目をNextカードで置き換え
        self.hand[indices_to_replace[1]] = self.next_card
        # 新しいNextカードを引く
        self.next_card = self._draw_card()

    # --- 状態取得メソッド ---
    def _get_obs(self) -> Dict[str, Any]:
        """現在の状態を観測として取得する"""
        stacked_zeros = self.stack.count(0)
        
        # 内部表現から観測空間に合わせて変換
        hold_obs = 0 if self.hold_slot == -1 else 1  # -1 -> 0, 0 -> 1
        next_obs = 0 if self.next_card == -1 else self.next_card + 1  # -1 -> 0, 0-5 -> 1-6
        stack_top_obs = 0 if not self.stack else self.stack[-1] + 1  # -1 -> 0, 0-5 -> 1-6
        remaining_turns_obs = MAX_TURNS - self.current_turn + 1
        remaining_merges_obs = MAX_MERGES_PER_TURN - self.merges_this_turn

        # --- DEBUG PRINTS ---
        # --- END DEBUG PRINTS ---

        return {
            "hand": np.array(self.hand, dtype=np.int64), # そのまま渡す
            "hold": np.int64(hold_obs), # 0 or 1
            "next": np.int64(next_obs), # 0 or 1-6
            "stack_top": np.int64(stack_top_obs), # 0 or 1-6
            "stacked_zeros": np.int64(stacked_zeros),
            "remaining_turns": np.int64(remaining_turns_obs),
            "remaining_merges": np.int64(remaining_merges_obs)
        }

    def _get_info(self) -> Dict[str, Any]:
        """追加情報を取得する"""
        # フルチェイン情報を取得（存在する場合）
        is_full_chain = getattr(self, '_last_clear_is_full_chain', False)
        stacked_zeros = getattr(self, '_last_clear_stacked_zeros', 0) if is_full_chain else self.stack.count(0)
        
        return {
            "current_turn": self.current_turn,
            "merges_this_turn": self.merges_this_turn,
            "stack_size": len(self.stack),
            "current_stack": list(self.stack),
            "hold_content": self.hold_slot, # ホールド内容も追加
            "score": self.score,  # スコア情報を追加
            "is_full_chain": is_full_chain,  # フルチェイン情報
            "stacked_zeros": stacked_zeros  # スタックされた0の数
        }

    # --- ゲーム進行メソッド ---
    def reset(self, seed: Optional[int] = None, options: Optional[dict] = None) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """環境をリセットする"""
        super().reset(seed=seed)

        self.stack = []
        self.current_turn = 1
        self.merges_this_turn = 0
        self.score = 0.0  # スコアをリセット
        
        # フルチェイン情報をリセット
        self._last_clear_is_full_chain = False
        self._last_clear_stacked_zeros = 0
        
        self._deal_initial_cards() # 手札、ホールド、Nextを配る

        observation = self._get_obs()
        info = self._get_info()

        if self.render_mode == "human":
            self._render_frame()

        return observation, info

    def step(self, action: int) -> Tuple[Dict[str, Any], float, bool, bool, Dict[str, Any]]:
        """行動を実行し、環境を次の状態に進める"""
        terminated = False
        truncated = False # Gymnasiumではtruncatedを使うことが推奨される
        reward = 0.0

        # --- ターン開始時のチェック: 積めるカードがない場合 (ホールドからのプレイも考慮) ---
        play_masks = self.action_masks()
        can_play_from_hand = any(play_masks[ACTION_PLAY_HAND_OFFSET:ACTION_PLAY_HOLD])
        can_play_from_hold = play_masks[ACTION_PLAY_HOLD]
        if not can_play_from_hand and not can_play_from_hold and self.stack:
            # 強制的にスタッククリア
            reward, is_full_chain, num_zeros = self._calculate_clear_reward() # 報酬計算を分離
            self._end_turn() # ターン終了処理
            if self.current_turn > MAX_TURNS:
                terminated = True
            # 状態を更新して早期リターン
            observation = self._get_obs()
            info = self._get_info()
            if self.render_mode == "human":
                self._render_frame()
            return observation, reward, terminated, truncated, info
        # --- チェック終了 ---

        # --- アクションの実行 ---
        if ACTION_PLAY_HAND_OFFSET <= action < ACTION_PLAY_HOLD:
            reward = self._handle_play_hand_action(action)
        elif action == ACTION_PLAY_HOLD:
            reward = self._handle_play_hold_action()
        elif ACTION_MERGE_OFFSET <= action < ACTION_HOLD_CARD_OFFSET:
            reward = self._handle_merge_action(action)
        elif ACTION_HOLD_CARD_OFFSET <= action < ACTION_CLEAR_STACK:
            reward = self._handle_hold_card_action(action)
        elif action == ACTION_CLEAR_STACK:
            reward = self._handle_clear_stack_action()
        else:
            # 未定義のアクション
            reward = PENALTY_INVALID_ACTION

        # --- ターン終了判定 (スタッククリア時にターンが進む) ---
        if self.current_turn > MAX_TURNS:
            terminated = True # ゲーム終了

        # --- 状態と情報の取得 ---
        observation = self._get_obs()
        info = self._get_info()

        if self.render_mode == "human":
            self._render_frame()

        return observation, reward, terminated, truncated, info

    def _is_valid_play(self, card_to_play: int) -> bool:
        """カードがスタックにプレイ可能か (0のルールを考慮)"""
        if card_to_play == -1: # ホールド枠が空(-1)の場合など
            return False # プレイ不可

        stack_top = self.stack[-1] if self.stack else -1 # スタックが空なら -1

        if card_to_play == 0:
            # 0をプレイする場合
            # スタックが空 or スタックトップが0 の場合のみ可能
            return not self.stack or stack_top == 0
        else:
            # 1以上をプレイする場合
            if not self.stack: # スタックが空ならOK
                return True
            if stack_top == 0: # スタックトップが0なら、1以上のカードは常にプレイ可能
                return True
            # スタックトップが1以上の場合、昇順ルール
            return card_to_play > stack_top

    def _handle_play_hand_action(self, action: int) -> float:
        """手札のカードを使用するアクションを処理する"""
        hand_idx = action - ACTION_PLAY_HAND_OFFSET
        reward = 0.0

        if 0 <= hand_idx < len(self.hand):
            card_to_play = self.hand[hand_idx]
            if self._is_valid_play(card_to_play):
                self.stack.append(card_to_play)
                self._replace_card_in_hand(hand_idx) # 手札補充
            else:
                reward = PENALTY_INVALID_ACTION
        else:
             reward = PENALTY_INVALID_ACTION
        return reward

    def _handle_play_hold_action(self) -> float:
        """ホールド枠のカードを使用するアクションを処理する"""
        reward = 0.0
        card_to_play = self.hold_slot

        if self._is_valid_play(card_to_play):
            self.stack.append(card_to_play)
            self.hold_slot = -1
        else:
            reward = PENALTY_INVALID_ACTION
        return reward


    def _handle_merge_action(self, action: int) -> float:
        """手札のカードを合成するアクションを処理する"""
        reward = 0.0
        if self.merges_this_turn >= MAX_MERGES_PER_TURN:
            return PENALTY_INVALID_ACTION

        idx_pair = self._action_to_merge_pair.get(action)
        if not idx_pair:
            return PENALTY_INVALID_ACTION

        idx1, idx2 = idx_pair
        # インデックスの有効性とカードの有効性をチェック
        if (0 <= idx1 < HAND_SIZE and 0 <= idx2 < HAND_SIZE and
                idx1 != idx2 and # 異なるインデックス
                self.hand[idx1] == self.hand[idx2] and
                0 < self.hand[idx1] < MAX_CARD_VALUE and # 0は合成不可、5も不可
                self.hand[idx1] < MERGE_LIMIT_VALUE + 1): # 4以下

            card_value = self.hand[idx1]
            merged_card = card_value + 1 if card_value < MERGE_LIMIT_VALUE else MERGE_LIMIT_VALUE

            self._remove_and_replace_merged_cards(idx1, idx2, merged_card)
            self.merges_this_turn += 1
        else:
            reward = PENALTY_INVALID_ACTION

        return reward

    def _handle_hold_card_action(self, action: int) -> float:
        """手札のカードをホールドするアクションを処理する（上書き可能）"""
        hand_idx = action - ACTION_HOLD_CARD_OFFSET
        reward = 0.0

        # 手札のカードが0かを確認（ホールド枠の状態に関わらず上書き可能）
        if 0 <= hand_idx < HAND_SIZE and self.hand[hand_idx] == 0:
            self.hold_slot = self.hand[hand_idx] # ホールド枠へ移動 (0が入る)
            self._replace_card_in_hand(hand_idx) # 手札をNextで補充
        else:
            reward = PENALTY_INVALID_ACTION # ホールド不可
        return reward


    def _handle_clear_stack_action(self) -> float:
        """スタックをクリアするアクションを処理する"""
        if not self.stack:
            return PENALTY_INVALID_ACTION
        reward, is_full_chain, num_zeros = self._calculate_clear_reward()
        
        # フルチェイン情報をinfoに設定するために保存
        self._last_clear_is_full_chain = is_full_chain
        self._last_clear_stacked_zeros = num_zeros
        
        self._end_turn()
        return reward

    def _calculate_clear_reward(self) -> Tuple[float, bool, int]:
        """スタッククリア時の報酬を計算する"""
        reward = 0.0
        num_zeros = self.stack.count(0)
        non_zero_stack = [c for c in self.stack if c != 0]

        # フルチェイン判定 (1から5まで)
        is_full_chain = set(non_zero_stack) == set(range(1, MAX_CARD_VALUE + 1))
        if is_full_chain:
            reward = REWARD_FULL_CHAIN

        # 0カードによる報酬倍率
        if num_zeros > 0:
            if reward > 0:
                 reward *= (REWARD_ZERO_MULTIPLIER ** num_zeros)

        # スコアを更新
        if reward > 0:
            self.score += reward

        return reward, is_full_chain, num_zeros

    def _end_turn(self):
        """ターン終了処理 (スタッククリア、ターン数更新、合成回数リセット)"""
        self.stack = []
        self.current_turn += 1
        self.merges_this_turn = 0

    # --- 描画メソッド ---
    def render(self):
        """環境の現在の状態を描画する (humanモード用)"""
        if self.render_mode == "human":
            self._render_frame()

    def _render_frame(self):
        """現在のゲーム状態をコンソールに出力する"""
        print("-" * 30)
        print(f"Turn: {self.current_turn}/{MAX_TURNS}")
        # 手札とホールドの表示を整形 (-1 を '_' に)
        hand_str = "[" + ", ".join(str(c) if c != -1 else '_' for c in self.hand) + "]"
        hold_str = str(self.hold_slot) if self.hold_slot != -1 else '_'
        next_str = str(self.next_card) if self.next_card != -1 else '_'
        print(f"Hand: {hand_str} | Hold: [{hold_str}] | Next: {next_str}")
        stack_str = str(self.stack) if self.stack else "Empty"
        stack_top_str = str(self.stack[-1]) if self.stack else "N/A" # stack_top は -1 になる可能性あり
        print(f"Stack: {stack_str} (Top: {stack_top_str if stack_top_str != '-1' else 'N/A'})") # -1ならN/A表示
        print(f"Merges this turn: {self.merges_this_turn}/{MAX_MERGES_PER_TURN}")
        # print(f"Valid Actions: {self.action_masks()}") # デバッグ用
        print("-" * 30)

    # --- 有効行動マスク ---
    def action_masks(self) -> List[bool]:
        """現在の状態で有効な行動のマスクを返す"""
        mask = [False] * NUM_ACTIONS

        # 1. 手札からのプレイアクション (0-3)
        for i in range(HAND_SIZE):
            action_id = ACTION_PLAY_HAND_OFFSET + i
            if self._is_valid_play(self.hand[i]):
                mask[action_id] = True

        # 2. ホールドからのプレイアクション (4)
        if self._is_valid_play(self.hold_slot):
            mask[ACTION_PLAY_HOLD] = True

        # 3. カード合成アクション (5-10)
        if self.merges_this_turn < MAX_MERGES_PER_TURN:
            eligible_cards = Counter()
            indices_map = {}
            for idx, card in enumerate(self.hand):
                # 0以外、合成上限値未満のカード
                if 0 < card < MAX_CARD_VALUE and card < MERGE_LIMIT_VALUE + 1:
                    eligible_cards[card] += 1
                    if card not in indices_map:
                        indices_map[card] = []
                    indices_map[card].append(idx)

            for card, count in eligible_cards.items():
                if count >= 2:
                    # Check all combinations for the current card value
                    for idx1, idx2 in combinations(indices_map[card], 2):
                        pair = tuple(sorted((idx1, idx2)))
                        if pair in self._merge_pair_to_action:
                            action_id = self._merge_pair_to_action[pair]
                            # Ensure the indices are within the current hand size (should always be true now)
                            if 0 <= idx1 < HAND_SIZE and 0 <= idx2 < HAND_SIZE:
                                mask[action_id] = True


        # 4. 手札をホールドするアクション (11-14)（上書き可能）
        for i in range(HAND_SIZE):
            action_id = ACTION_HOLD_CARD_OFFSET + i
            # 手札のカードが0の場合のみホールド可能 (lenチェック不要)
            if self.hand[i] == 0:
                mask[action_id] = True

        # 5. スタッククリアアクション (15)
        if self.stack:
            mask[ACTION_CLEAR_STACK] = True

        return mask

    def close(self):
        """環境のリソースを解放する"""
        pass

# 環境外部からアクセスするためのアクションマスク取得関数
def get_action_masks(env: CardGameEnv) -> List[bool]:
    """環境のアクションマスクを取得する関数（マルチプロセッシング用）"""
    # 環境インスタンスの action_masks メソッドを呼び出す
    return env.action_masks()
