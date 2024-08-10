from typing import List

from aiwolf import Agent, GameInfo, GameSetting, Role, Species
from aiwolf.constant import AGENT_NONE

from o0villager import SampleVillager
from ScoreMatrix import ScoreMatrix


class SampleBodyguard(SampleVillager):
    """Sample bodyguard agent."""

    to_be_guarded: Agent
    """Target of guard."""

    def __init__(self) -> None:
        """Initialize a new instance of SampleBodyguard."""
        super().__init__()
        self.to_be_guarded = AGENT_NONE

    def initialize(self, game_info: GameInfo, game_setting: GameSetting) -> None:
        super().initialize(game_info, game_setting)
        self.to_be_guarded = AGENT_NONE

    def guard(self) -> Agent:
        # Guard one of the alive non-fake seers.
        candidates: List[Agent] = self.get_alive([j.agent for j in self.divination_reports
                                                  if j.result != Species.WEREWOLF or j.target != self.me])
        # Guard one of the alive mediums if there are no candidates.
        if not candidates:
            candidates = [a for a in self.comingout_map if self.is_alive(a)
                          and self.comingout_map[a] == Role.MEDIUM]
        # Guard one of the alive sagents if there are no candidates.
        if not candidates:
            candidates = self.get_alive_others(self.game_info.agent_list)
        # Update a guard candidate if the candidate is changed.
        if self.to_be_guarded == AGENT_NONE or self.to_be_guarded not in candidates:
            self.to_be_guarded = self.random_select(candidates)
        return self.to_be_guarded if self.to_be_guarded != AGENT_NONE else self.me
