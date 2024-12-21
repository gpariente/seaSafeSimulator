from simulator.ship import Ship

class Environment:
    """
    Represents the simulation environment.
    """
    def __init__(self, map_size: int, time_step: int, safety_radius: int, horizon: int):
        self.map_size = map_size  # Size of the map (e.g., 20x20 nautical miles)
        self.time_step = time_step  # Time step in seconds
        self.safety_radius = safety_radius  # Safety zone radius in meters
        self.horizon = horizon  # Lookahead distance in nautical miles
        self.ships = []  # List of ships in the environment

    def add_ship(self, ship: Ship):
        """
        Adds a ship to the environment.
        """
        self.ships.append(ship)

    def update(self):
        """
        Updates the environment and all ships.
        """
        for ship in self.ships:
            ship.update()
