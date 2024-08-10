import sys
import time
import traceback
from collections import Counter, defaultdict
from typing import DefaultDict, Dict, List

from aiwolf import Agent, GameInfo, Role
from aiwolf.constant import AGENT_NONE


class Util:
    exit_on_error = False
    local = False
    need_traceback = True

    rtoi = {Role.VILLAGER: 0, Role.SEER: 1, Role.POSSESSED: 2, Role.WEREWOLF: 3, Role.MEDIUM: 4, Role.BODYGUARD: 5}
    debug_mode = True
    time_start = Dict[str, float]

    game_count: int = 0
    win_count: DefaultDict[Agent, int] = {}
    win_rate: DefaultDict[Agent, float] = {}
    # 役職ごとの回数
    agent_role_count: DefaultDict[Agent, DefaultDict[Role, int]] = defaultdict(lambda: defaultdict(int))
    # 役職ごとの勝利回数
    win_role_count: DefaultDict[Agent, DefaultDict[Role, int]] = defaultdict(lambda: defaultdict(int))
    # 役職ごとの勝率
    win_role_rate: DefaultDict[Agent, DefaultDict[Role, float]] = defaultdict(lambda: defaultdict(float))
    sum_score: float = 0.0
    # 投票宣言と投票先の一致回数
    vote_count: DefaultDict[Agent, int] = defaultdict(int)
    vote_match_count: DefaultDict[Agent, int] = defaultdict(int)


    @staticmethod
    def init():
        Util.time_start = {}
        Util.game_count = 0
        Util.win_count = defaultdict(int)
        Util.win_rate = defaultdict(float)
        Util.sum_score = 0


    @staticmethod
    def debug_print(*args, **kwargs):
        # if type(args[0]) == str and ("exec_time" in args[0] or "len(self.assignments)" in args[0]):
        #     return
        if Util.debug_mode:
            print(*args, **kwargs)


    @staticmethod
    def error_print(*args, **kwargs):
        print(*args, **kwargs, file=sys.stderr)
        if Util.local and Util.exit_on_error:
            if Util.need_traceback:
                traceback.print_stack()
            exit(1)


    @staticmethod
    def start_timer(func_name):
        Util.time_start[func_name] = time.time()


    @staticmethod
    def end_timer(func_name, time_threshold=0):
        time_end = time.time()
        time_exec = round((time_end - Util.time_start[func_name]) * 1000, 1)
        if time_exec >= time_threshold:
            if time_threshold == 0:
                Util.debug_print("exec_time:\t", func_name, time_exec)
            else:
                Util.error_print("exec_time:\t", func_name, time_exec)


    @staticmethod
    def timeout(func_name, time_threshold):
        time_now = time.time()
        time_exec = round((time_now - Util.time_start[func_name]) * 1000, 1)
        return time_exec >= time_threshold


    @staticmethod
    def update_win_rate(game_info: GameInfo, villager_win: bool):
        for agent, role in game_info.role_map.items():
            is_villager_side = role in [Role.VILLAGER, Role.SEER, Role.MEDIUM, Role.BODYGUARD]
            win = villager_win if is_villager_side else not villager_win
            Util.agent_role_count[agent][role] += 1
            if win:
                Util.win_count[agent] += 1
                Util.win_role_count[agent][role] += 1
            Util.win_rate[agent] = Util.win_count[agent] / Util.game_count
            Util.win_role_rate[agent][role] = Util.win_role_count[agent][role] / Util.agent_role_count[agent][role]
        Util.debug_print("")
        Util.debug_print("------------------")
        for agent in game_info.agent_list:
            Util.debug_print("win_rate:\t", agent, Util.win_rate[agent])
            role = game_info.role_map[agent]
            Util.debug_print("win_role_rate:\t", agent, role, Util.win_role_rate[agent][role])
        Util.debug_print("------------------")


    @staticmethod
    def get_strong_agent(agent_list: List[Agent], threshold: float = 0.0) -> Agent:
        rate = threshold
        strong_agent = AGENT_NONE
        for agent in agent_list:
            if Util.win_rate[agent] >= rate:
                rate = Util.win_rate[agent]
                strong_agent = agent
        return strong_agent


    @staticmethod
    def get_weak_agent(agent_list: List[Agent], threshold: float = 1.0) -> Agent:
        rate = threshold
        weak_agent = AGENT_NONE
        for agent in agent_list:
            if Util.win_rate[agent] <= rate:
                rate = Util.win_rate[agent]
                weak_agent = agent
        return weak_agent

    # 基本的には set(itertools.permutations) と同じ
    # ただし、fixed_positions で指定した位置に固定値を入れることができる
    @staticmethod
    def unique_permutations(lst, fixed_positions=None):
        if fixed_positions is None:
            fixed_positions = {}

        counter = Counter(lst)
        for pos, val in fixed_positions.items():
            counter[val] -= 1
        
        unique_elems = list(counter.keys())
        counts = list(counter.values())
        n = len(lst)
        
        def _unique_permutations(current_perm, remaining_counts, current_length):
            if current_length == n:
                yield tuple(current_perm)
                return
            if current_length in fixed_positions:
                yield from _unique_permutations(current_perm + [fixed_positions[current_length]], remaining_counts, current_length + 1)
            else:
                for idx, (elem, count) in enumerate(zip(unique_elems, remaining_counts)):
                    if count > 0:
                        remaining_counts[idx] -= 1
                        yield from _unique_permutations(current_perm + [elem], remaining_counts, current_length + 1)
                        remaining_counts[idx] += 1

        return _unique_permutations([], counts, 0)
