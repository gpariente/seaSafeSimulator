# algorithm/api.py

class AlgorithmAPI:
    """
    A generic algorithm interface for collision detection and future prediction.
    This interface can be implemented by different algorithm classes.
    """
    def detect_future_collision(self, state, horizon_steps, safety_zone_nm):
        """
        Detect future collisions within the given horizon.

        :param state: The current simulation state (includes ships, time step, etc.)
        :param horizon_steps: How many future steps (seconds) to check for collisions.
        :param safety_zone_nm: The safety zone radius in nautical miles.
        :return: A list of statuses corresponding to each ship ('Green', 'Orange', or 'Red').
        """
        raise NotImplementedError("This method should be implemented by subclasses.")
