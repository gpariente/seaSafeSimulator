# file: algorithm/base.py
from abc import ABC, abstractmethod

class CollisionAvoidanceAlgorithm(ABC):
    @abstractmethod
    def step(self, state, horizon_steps, safety_zone_nm, horizon_nm):
        """
        Must return: statuses (list of ship statuses) and actions (list of Action objects).
        """
        pass
