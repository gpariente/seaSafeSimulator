from simulator.ship import Ship

class State:
    """Represents a discrete time step state in the simulation."""
    def __init__(self, time_step, ships):
        self.time_step = time_step
        self.ships = ships  # List of Ship objects

    def isGoalState(self):
        """Check if all ships have reached their destinations."""
        return all(ship.reached_destination() for ship in self.ships)

    def update_ships(self, delta_seconds=1):
        """
        Update the position of all ships based on a time delta (in seconds).
        We'll call this with TIME_STEP_SECONDS (default 30.0).
        """
        for ship in self.ships:
            ship.update_position(delta_seconds)

    def increment_time_step(self):
        self.time_step += 1
