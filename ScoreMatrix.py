import inspect
from typing import Dict, List, Set

import numpy as np
from o0villager import *
from o0possessed import *
from o0werewolf import *
from o0seer import *
from Side import Side
from Util import Util

from aiwolf import Agent, GameInfo, GameSetting, Role, Species
from aiwolf.constant import AGENT_NONE

# プレイヤー数と役職数
NUM_PLAYERS = 5
NUM_ROLES = 4  # 人狼, 村人, 狂人, 占い師
START_BELIEF =0.5


class ScoreMatrix:
    def __init__(self, game_info: GameInfo, game_setting: GameSetting, _player) -> None:
        self.game_info = game_info
        self.game_setting = game_setting
        self.N = game_setting.player_num
        self.M = len(game_info.existing_role_list)
        # score_matrix[エージェント1, 役職1, エージェント2, 役職2]: エージェント1が役職1、エージェント2が役職2である相対確率の対数
        # -infで相対確率は0になる
        self.score_matrix: np.ndarray = np.full((NUM_PLAYERS, NUM_PLAYERS, NUM_ROLES), 0.5)
        self.villager = SampleVillager()
        self.seer = SampleSeer()
        self.possessed = SamplePossessed()
        self.werewolf = SampleWerewolf()
        self.player = self.villager
        self.my_role = game_info.my_role # 自身の役職
        for r, i in {Role.VILLAGER: 0, Role.SEER: 1, Role.POSSESSED: 2, Role.WEREWOLF: 3}.items():
            self.rtoi[r] = i
        self.seer_co_count = 0
        self.medium_co_count = 0
        self.bodyguard_co_count = 0
        self.seer_co = []
        self.medium_co = []
        self.bodyguard_co = []
        
        for a, r in game_info.role_map.items():
            if r != Role.ANY and r != Role.UNC:
                self.set_score(a, r, a, r, float('inf'))


    def update(self, game_info: GameInfo) -> None:
        self.game_info = game_info


    # スコアは相対確率の対数を表す
    # スコア = log(相対確率)
    # スコアの付け方
    # 確定情報: +inf または -inf
    # 非確定情報: 有限値 最大を10で統一する
    # 書くときは100を最大として、相対確率に直すときに1/10倍する


    # スコアの取得
    # agent1, agent2: Agent or int
    # role1, role2: Role or int
    def get_score(self, agent1: Agent, role1: Role, agent2: Agent, role2: Role) -> float:
        i = agent1.agent_idx-1 if type(agent1) is Agent else agent1
        ri = self.rtoi[role1] if type(role1) is Role else role1
        j = agent2.agent_idx-1 if type(agent2) is Agent else agent2
        rj = self.rtoi[role2] if type(role2) is Role else role2
        
        if ri >= self.M or rj >= self.M or ri < 0 or rj < 0: # 存在しない役職の場合はスコアを-infにする (5人村の場合)
            return -float('inf')
        
        return self.score_matrix[i, ri, j, rj]


    # スコアの設定
    # agent1, agent2: Agent or int
    # role1, role2: Role or int
    def set_score(self, agent1: Agent, role1: Role, agent2: Agent, role2: Role, score: float) -> None:
        i = agent1.agent_idx-1 if type(agent1) is Agent else agent1
        ri = self.rtoi[role1] if type(role1) is Role else role1
        j = agent2.agent_idx-1 if type(agent2) is Agent else agent2
        rj = self.rtoi[role2] if type(role2) is Role else role2
        
        if ri >= self.M or rj >= self.M or ri < 0 or rj < 0: # 存在しない役職の場合はスコアを設定しない (5人村の場合)
            return
        
        if score == float('inf'): # スコアを+infにすると相対確率も無限に発散するので、代わりにそれ以外のスコアを0にする。
            self.score_matrix[i, :, j, :] = -float('inf')
            self.score_matrix[i, ri, j, rj] = 0
        else:
            if score > 100:
                self.score_matrix[i, ri, j, rj] = 100
            elif score < -100:
                self.score_matrix[i, ri, j, rj] = -100
            else:
                self.score_matrix[i, ri, j, rj] = score


    # スコアの加算
    # agent1, agent2: Agent or int
    # role1, rold2: Role, int, Species, Side or List
    def add_score(self, agent1: Agent, role1: Role, agent2: Agent, role2: Role, score: float) -> None:
        # 加算するスコアが大きい場合はどの関数から呼ばれたかを表示
        if abs(score) >= 5:
            caller = inspect.stack()[1]
            if caller.function != "add_scores":
                Util.debug_print("add_score:\t", caller.function, caller.lineno, "\t", score)
        
        if type(role1) is Side:
            role1 = role1.get_role_list(self.N)
        if type(role2) is Side:
            role2 = role2.get_role_list(self.N)
        if type(role1) is Species:
            if role1 == Species.HUMAN:
                role1 = Side.VILLAGERS.get_role_list(self.N) + [Role.POSSESSED]
            elif role1 == Species.WEREWOLF:
                role1 = Role.WEREWOLF
            else:
                Util.error_print('role1 is not Species.HUMAN or Species.WEREWOLF')
        if type(role2) is Species:
            if role2 == Species.HUMAN:
                role2 = Side.VILLAGERS.get_role_list(self.N) + [Role.POSSESSED]
            elif role2 == Species.WEREWOLF:
                role2 = Role.WEREWOLF
            else:
                Util.error_print('role2 is not Species.HUMAN or Species.WEREWOLF')
        if type(role1) is not list:
            role1 = [role1]
        if type(role2) is not list:
            role2 = [role2]
        for r1 in role1:
            for r2 in role2:
                modified_score = self.get_score(agent1, r1, agent2, r2) + score
                self.set_score(agent1, r1, agent2, r2, modified_score)


    # スコアの加算をまとめて行う
    def add_scores(self, agent: Agent, score_dict: Dict[Role, float]) -> None:
        # 加算するスコアが大きい場合はどの関数から呼ばれたかを表示
        if min(score_dict.values()) <= -5 or max(score_dict.values()) >= 5:
            caller = inspect.stack()[1]
            Util.debug_print("add_scores:\t", caller.function, caller.lineno, "\t", {str(r)[5]: s for r, s in score_dict.items()})
        
        for key, value in score_dict.items():
            self.add_score(agent, key, agent, key, value)


# --------------- 公開情報から推測する ---------------
    # 襲撃結果を反映
    def killed(self, game_info: GameInfo, game_setting: GameSetting, agent: Agent) -> None:
        self.update(game_info)
        # 襲撃されたエージェントは人狼ではない
        self.set_score(agent, Role.WEREWOLF, agent, Role.WEREWOLF, -float('inf'))


    # 投票行動を反映
    def vote(self, game_info: GameInfo, game_setting: GameSetting, voter: Agent, target: Agent, day: int) -> None:
        self.update(game_info)
        N = self.N
        # 自分の投票行動は無視
        if voter == self.me:
            return
        # ---------- 5人村 ----------
        # 2日目でゲームの勝敗が決定しているので、1日目の投票行動の反映はほとんど意味ない
        if N == 5:
            # 投票者が村陣営で、投票対象が人狼である確率を上げる
            self.add_score(voter, Role.VILLAGER, target, Role.WEREWOLF, +0.1)
            self.add_score(voter, Role.SEER, target, Role.WEREWOLF, +0.3)


# --------------- 自身の能力の結果から推測する：確定情報なのでスコアを +inf or -inf にする ---------------
    # 自分の占い結果を反映（結果騙りは考慮しない）
    def my_divined(self, game_info: GameInfo, game_setting: GameSetting, target: Agent, species: Species) -> None:
        self.update(game_info)
        # 黒結果
        if species == Species.WEREWOLF:
            # 人狼であることが確定しているので、人狼のスコアを+inf(実際には他の役職のスコアを-inf(相対確率0)にする)
            self.set_score(target, Role.WEREWOLF, target, Role.WEREWOLF, +float('inf'))
        # 白結果
        elif species == Species.HUMAN:
            # 人狼でないことが確定しているので、人狼のスコアを-inf(相対確率0)にする
            self.set_score(target, Role.WEREWOLF, target, Role.WEREWOLF, -float('inf'))
        else:
            # 万が一不確定(Species.UNC, Species.ANY)の場合
            Util.error_print('my_divined: species is not Species.WEREWOLF or Species.HUMAN')



# --------------- 他の人の発言から推測する：確定情報ではないので有限の値を加減算する ---------------
    # 他者のCOを反映
    def talk_co(self, game_info: GameInfo, game_setting: GameSetting, talker: Agent, role: Role, day: int, turn: int) -> None:
        self.update(game_info)
        N = self.N
        my_role = self.my_role
        role_map = self.game_info.role_map
        # 自分と仲間の人狼のCOは無視
        if talker == self.me or (talker in role_map and role_map[talker] == Role.WEREWOLF):
            return
        # ---------- 5人村 ----------
        if N == 5:
            # ----- 占いCO -----
            # 基本、初日の早いターンでCOなので、COでのスコア変更は少なめにして、結果でスコアを変更する
            if role == Role.SEER:
                # --- 占い ---
                if my_role == Role.SEER:
                    # 人狼と狂人の確率を上げる（対抗にしか黒結果が出ない）のではなく、村人と占いの確率を下げる
                    # +5, +3を上回る行動学習結果なら、行動学習を優先する
                    self.add_scores(talker, {Role.VILLAGER: -100, Role.SEER: -100, Role.POSSESSED: +5, Role.WEREWOLF: +3})
                # --- それ以外 ---
                else:
                    # 既にCOしている場合：複数回COすることでscoreを稼ぐのを防ぐ
                    if talker in self.seer_co:
                        return
                    # 複数占いCOがあった場合、誰か一人が真で残りは偽である確率はほぼ100%
                    # (両方とも偽という割り当ての確率を0%にする)
                    # for seer in set(self.seer_co) | self.hidden_seers:
                    #     self.add_score(seer, Role.SEER, talker, Side.WEREWOLVES, +100)
                    #     self.add_score(talker, Role.SEER, seer, Side.WEREWOLVES, +100)
                    # 村人である確率を下げる（村人の役職騙りを考慮しない）
                    self.add_scores(talker, {Role.VILLAGER: -100})
                    # 初COの場合
                    self.seer_co_count += 1
                    self.seer_co.append(talker)
                    # --- 人狼 ---
                    if my_role == Role.WEREWOLF:
                        # 占いと狂人どちらもありうるので、CO段階では何もしない→結果でスコアを変更する
                        return
                    # --- 狂人 ---
                    elif my_role == Role.POSSESSED:
                        # 占いと人狼どちらもありうるので、CO段階では少しの変更にする
                        # 気持ち、1CO目は占いっぽい
                        if self.seer_co_count == 1:
                            self.add_scores(talker, {Role.SEER: +1})
                        # 2CO目以降は無視
                        else:
                            return
                    # --- 村人 ---
                    else:
                        # 村人視点では、COを重視する：結果では正確に判断できないから
                        # 気持ち、1,2CO目は占いor狂人、3CO目は占いor人狼っぽい
                        if self.seer_co_count == 1:
                            self.add_scores(talker, {Role.SEER: +2, Role.POSSESSED: +2, Role.WEREWOLF: +1})
                        elif self.seer_co_count == 2:
                            self.add_scores(talker, {Role.SEER: +2, Role.POSSESSED: +2, Role.WEREWOLF: +2})
                        else:
                            self.add_scores(talker, {Role.SEER: +1, Role.POSSESSED: +1, Role.WEREWOLF: +2})
            # ----- 狂人CO -----
            # 村人の狂人COはないと仮定する→PP阻止のために村人が狂人COすることがある→少しの変更にする
            elif role == Role.POSSESSED:
                # --- 人狼 ---
                if my_role == Role.WEREWOLF:
                    self.add_scores(talker, {Role.POSSESSED: +5})
                # --- 狂人 ---
                elif my_role == Role.POSSESSED:
                    # 人狼で狂人COするエージェントはいないので不要→今までの推論を優先するべき
                    # self.add_scores(talker, {Role.WEREWOLF: +5})
                    pass
                # --- 村人 or 占い ---
                else:
                    self.add_scores(talker, {Role.POSSESSED: +5, Role.WEREWOLF: +1})
            # ----- 人狼CO -----
            elif role == Role.WEREWOLF:
                # --- 狂人 ---
                if my_role == Role.POSSESSED:
                    # 村陣営がPP阻止のために、人狼COする場合があるので、少しの変更にする
                    self.add_scores(talker, {Role.WEREWOLF: +5})
                # --- 人狼 ---
                elif my_role == Role.WEREWOLF:
                    # 村陣営がPP阻止のために、人狼COする場合があるので、少しの変更にする
                    self.add_scores(talker, {Role.POSSESSED: +5})
                # --- 村人 or 占い ---
                else:
                    # 狂人と人狼どちらもありうるので、少しの変更にする：狂人と人狼で優劣をつけない→あくまで今までの結果を重視する
                    self.add_scores(talker, {Role.POSSESSED: +5, Role.WEREWOLF: +5})

    # 投票意思を反映
    # それほど重要ではないため、スコアの更新は少しにする
    def talk_will_vote(self, game_info: GameInfo, game_setting: GameSetting, talker: Agent, target: Agent, day: int, turn: int) -> None:
        self.update(game_info)
        N = self.N
        will_vote = self.player.will_vote_reports
        # 自分の投票意思は無視
        if talker == self.me:
            return
        # 同じ対象に二回目以降の投票意思は無視
        if will_vote[talker] == target:
            return
        # 初日初ターンは無視
        if day == 1 and turn <= 1:
            return
        # ---------- 5人村 ----------
        if N == 5:
            # 発言者が村人・占い師で、対象が人狼である確率を上げる
            self.add_score(talker, Role.VILLAGER, target, Role.WEREWOLF, +0.1)
            self.add_score(talker, Role.SEER, target, Role.WEREWOLF, +0.3)
            # 人狼は投票意思を示しがちだから、人狼である確率を上げる
            # 違う対象に投票意思を示している
            self.add_scores(talker, {Role.WEREWOLF: +1})


    # Basketにないため、後で実装する→実装しない
    def talk_estimate(self, game_info: GameInfo, game_setting: GameSetting, talker: Agent, target: Agent, role: Role, day: int, turn: int) -> None:
        self.update(game_info)


    # 他者の占い結果を反映
    # 条件分岐は、N人村→myrole→白黒結果→targetが自分かどうか
    def talk_divined(self, game_info: GameInfo, game_setting: GameSetting, talker: Agent, target: Agent, species: Species, day: int, turn: int) -> None:
        self.update(game_info)
        N = self.N
        my_role = self.my_role
        role_map = self.game_info.role_map
        # 自分と仲間の人狼の結果は無視
        if talker == self.me or (talker in role_map and role_map[talker] == Role.WEREWOLF):
            return
        # CO の時点で占い師以外の村人陣営の可能性を0にしているが、COせずに占い結果を出した場合のためにここでも同じ処理を行う
        self.add_scores(talker, {Role.VILLAGER: -100, Role.MEDIUM: -100, Role.BODYGUARD: -100})
        # すでに同じ相手に対する占い結果がある場合は無視
        # ただし、結果が異なる場合は、人狼・狂人の確率を上げる
        for report in self.player.divination_reports:
            if report.agent == talker and report.target == target:
                if report.result == species:
                    return
                else:
                    Util.debug_print('同じ相手に対して異なる占い結果を出した時')
                    self.add_scores(talker, {Role.POSSESSED: +100, Role.WEREWOLF: +100})
                    return
        # ---------- 5人村 ----------
        if N == 5:
            # ----- 占い -----
            if my_role == Role.SEER:
                # self.add_scores(talker, {Role.POSSESSED: +100, Role.WEREWOLF: +100})
                self.add_scores(talker, {Role.VILLAGER: -100, Role.SEER: -100, Role.POSSESSED: +5, Role.WEREWOLF: +3})
                # 黒結果
                if species == Species.WEREWOLF:
                    # 対象：自分
                    if target == self.me:
                        self.add_scores(talker, {Role.POSSESSED: +100, Role.WEREWOLF: +100})
                    # 対象：自分以外
                    else:
                        self.add_score(talker, Side.WEREWOLVES, target, Species.HUMAN, +5)
                        self.add_score(talker, Side.WEREWOLVES, target, Role.WEREWOLF, -5)
                # 白結果
                elif species == Species.HUMAN:
                    # 対象：自分
                    if target == self.me:
                        self.add_scores(talker, {Role.POSSESSED: +100, Role.WEREWOLF: +100})
                    # 対象：自分以外
                    else:
                        self.add_score(talker, Side.WEREWOLVES, target, Species.HUMAN, -5)
                        self.add_score(talker, Side.WEREWOLVES, target, Role.WEREWOLF, +5)
            # ----- 人狼 -----
            elif my_role == Role.WEREWOLF:
                # 黒結果
                if species == Species.WEREWOLF:
                    # 対象：自分
                    if target == self.me:
                        # talkerの占い師である確率を上げる (誤爆を考慮しなければ100%)
                        self.add_scores(talker, {Role.SEER: +100, Role.POSSESSED: +0})
                    # 対象：自分以外
                    else:
                        # talkerの狂人である確率を上げる (ほぼ100%と仮定)
                        if self.player.comingout_map[target] == Role.SEER:
                            self.add_scores(talker, {Role.POSSESSED: +10})
                            Util.debug_print('狂人:\t', talker)
                # 白結果
                elif species == Species.HUMAN:
                    # 対象：自分
                    if target == self.me:
                        # talkerの占い師である確率を下げる、狂人である確率を上げる（結果の矛盾が起こっているから、値を大きくしている）
                        self.add_scores(talker, {Role.SEER: -100, Role.POSSESSED: +100})
                        Util.debug_print('狂人:\t', talker)
                    # 対象：自分以外
                    else:
                        # 狂人は基本的に黒結果を出すことが多いので、talkerの占い師である確率を上げる
                        # 確定ではないので、値は控えめにする
                        self.add_scores(talker, {Role.SEER: +10, Role.POSSESSED: +5})
            # ----- 狂人 -----
            elif my_role == Role.POSSESSED:
                # 黒結果
                if species == Species.WEREWOLF:
                    # 対象：自分
                    if target == self.me:
                        # talkerの占い師である確率を下げる
                        # 本来は占い師である確率を0%にしたいが、占い師の結果騙りがあるため、-100にはしない
                        self.add_scores(talker, {Role.SEER: -5, Role.WEREWOLF: +5})
                    # 対象：自分以外
                    else:
                        # talkerが占い師で、targetが人狼である確率を上げる
                        # かなりの確率で人狼であると仮定する
                        self.add_score(talker, Role.SEER, target, Role.WEREWOLF, +10)
                        # 占い師は確率的に白結果を出すことが多いので、talkerの人狼である確率を少し上げる
                        self.add_scores(talker, {Role.WEREWOLF: +3})
                # 白結果
                elif species == Species.HUMAN:
                    # 対象：自分
                    if target == self.me:
                        # talkerの占い師である確率を上げる
                        # 自分への白結果はほぼ占い師確定
                        self.add_scores(talker, {Role.SEER: +10})
                    # 対象：自分以外
                    else:
                        # talkerが占い師で、targetが人狼である確率を下げる
                        self.add_score(talker, Role.SEER, target, Role.WEREWOLF, -5)
                        # 人狼は基本的に黒結果を出すことが多いので、talkerの占い師である確率を上げる
                        # 確定ではないので、値は控えめにする
                        self.add_scores(talker, {Role.SEER: +3, Role.WEREWOLF: +1})
            # ----- 村人 -----
            else:
                # 黒結果
                if species == Species.WEREWOLF:
                    # 対象：自分
                    if target == self.me:
                        # talkerの占い師である確率を下げる（結果の矛盾が起こっているから、値を大きくしている）
                        self.add_scores(talker, {Role.SEER: -100, Role.POSSESSED: +10, Role.WEREWOLF: +10})
                    # 対象：自分以外
                    else:
                        # talkerが占い師で、targetが人狼である確率を上げる
                        self.add_score(talker, Role.SEER, target, Role.WEREWOLF, +3)
                        # talkerが狂人と人狼である確率を少し上げる
                        self.add_scores(talker, {Role.POSSESSED: +3, Role.WEREWOLF: +1})
                # 白結果
                elif species == Species.HUMAN:
                    # 対象：自分
                    if target == self.me:
                        # talkerの占い師である確率を上げる
                        # 自分への白結果はほぼ占い師確定
                        self.add_scores(talker, {Role.SEER: +10})
                    # 対象：自分以外
                    else:
                        # talkerが占い師で、targetが人狼である確率を下げる
                        self.add_score(talker, Role.SEER, target, Role.WEREWOLF, -5)
                        # 人狼は基本的に黒結果を出すことが多いので、talkerの占い師である確率を上げる
                        # 確定ではないので、値は控えめにする
                        self.add_scores(talker, {Role.SEER: +3, Role.POSSESSED: +1, Role.WEREWOLF: +1})
        
# --------------- 他の人の発言から推測する ---------------

    # N日目の始めに推測する
    # COしているのに、噛まれていない違和感を反映する
    def Nth_day_start(self, game_info: GameInfo, game_setting: GameSetting) -> None:
        self.update(game_info)
        day: int = self.game_info.day
        my_role = self.my_role

        # if day <= 2 or len(game_info.last_dead_agent_list) == 0:
        #     return
        if day <= 2:
            return

        # 生存者数の推移(GJなし)：15→13→11→9→7→5
        # 3日目0GJ(11人)、4日目1GJ以下(14-day人以下)なら、採用
        alive_cnt: int = len(self.game_info.alive_agent_list)
        Util.debug_print('(day, alive_cnt) = ', day, alive_cnt)
        if (day == 3 and alive_cnt <= 11) or (day >= 4 and alive_cnt <= 14-day):
            Util.debug_print('Nth_day_start: 採用')
            if my_role != Role.WEREWOLF:
                for agent, role in self.player.alive_comingout_map.items():
                    if role in [Role.SEER, Role.MEDIUM, Role.BODYGUARD]:
                        self.add_scores(agent, {Role.POSSESSED: +1, Role.WEREWOLF: +3})


