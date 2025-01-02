import gymnasium as gym
from gymnasium import spaces
import numpy as np

class Action(spaces.Space):
    def __init__(self, max_course_change, num_ships):
        super().__init__((num_ships,), np.int8)
        self.max_course_change = max_course_change
        self.num_ships = num_ships
        # Define possible actions for a single ship:
        self.single_ship_actions = [
            (-1, -1),  # Decrease speed, turn left
            (-1, 0),   # Decrease speed, maintain course
            (-1, 1),   # Decrease speed, turn right
            (0, -1),   # Maintain speed, turn left
            (0, 0),    # Maintain speed, maintain course
            (0, 1),    # Maintain speed, turn right
            (1, -1),   # Increase speed, turn left
            (1, 0),    # Increase speed, maintain course
            (1, 1),    # Increase speed, turn right
        ]

    def sample(self):
        """
        Returns a random sample from the action space.
        """
        return np.array([np.random.choice(len(self.single_ship_actions)) for _ in range(self.num_ships)])

    def contains(self, x):
        """
        Checks if a given action is valid within the action space.
        """
        if not isinstance(x, np.ndarray) or x.shape != (self.num_ships,):
            return False
        return all(0 <= action_index < len(self.single_ship_actions) for action_index in x)

    def decode_action(self, action_index, ship):
        """
        Decodes a single-ship action index into speed and heading changes.
        """
        speed_change_index, heading_change_index = self.single_ship_actions[action_index]
        # Speed change: +/-10 knots per step (example)
        speed_change = speed_change_index * 10
        # Heading change: +/- max_course_change
        heading_change = heading_change_index * self.max_course_change
        return speed_change, heading_change
    
    def maintain_course_and_speed_action_index(self):
        """
        Returns the index of the action corresponding to maintaining course and speed.
        """
        return self.single_ship_actions.index((0, 0))
