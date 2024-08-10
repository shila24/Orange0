from enum import Enum
from Util import Util
from aiwolf import Role

class Side(Enum):
    """Enumeration type for side."""

    UNC = "UNC"
    """Uncertain."""
    VILLAGERS = "VILLAGERS"
    """Villager."""
    WEREWOLVES = "WEREWOLVES"
    """Werewolf."""
    ANY = "ANY"
    """Wildcard."""

    def get_role_list(self, N):
        if self == Side.VILLAGERS:
            if N == 5:
                return [Role.VILLAGER, Role.SEER]
            else:
                Util.error("Invalid N: " + str(N))
        elif self == Side.WEREWOLVES:
            return [Role.WEREWOLF, Role.POSSESSED]
        else:
            Util.error("Invalid side: " + str(self))
