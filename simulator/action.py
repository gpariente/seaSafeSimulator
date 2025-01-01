import gymnasium as gym
from gymnasium import spaces
import numpy as np

class Action(spaces.Space):
    def __init__(self, max_course_change, num_ships):
        super().__init__((num_ships,), np.int8)  # Example: using a discrete space for simplicity
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

        Returns:
            np.ndarray: An array of integers, one for each ship, representing the chosen action index.
        """
        return np.array([np.random.choice(len(self.single_ship_actions)) for _ in range(self.num_ships)])

    def contains(self, x):
        """
        Checks if a given action is valid within the action space.

        Args:
            x (np.ndarray): An array of integers, one for each ship, representing the action indices.

        Returns:
            bool: True if the action is valid, False otherwise.
        """
        if not isinstance(x, np.ndarray) or x.shape != (self.num_ships,):
            return False
        return all(0 <= action_index < len(self.single_ship_actions) for action_index in x)

    def decode_action(self, action_index, ship):
        """
        Decodes a single ship action index into speed and heading changes.

        Args:
            action_index (int): The index of the action for a single ship.
            ship (Ship): The ship object to which the action will be applied.

        Returns:
            tuple: A tuple containing the speed change and heading change.
        """
        speed_change_index, heading_change_index = self.single_ship_actions[action_index]
        speed_change = speed_change_index * 10
        heading_change = heading_change_index * self.max_course_change

        return speed_change, heading_change
    
    def maintain_course_and_speed_action_index(self):
            """
            Returns the index of the action corresponding to maintaining course and speed.
            """
            return self.single_ship_actions.index((0, 0))  # Assuming (0, 0) is maintain course and speed