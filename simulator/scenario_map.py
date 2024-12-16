from simulator.position import Position

METERS_PER_NM = 1852.0
SECONDS_PER_HOUR = 3600.0
WIDTH, HEIGHT = 1000, 1000

class Map:
    """Handles the scaling and unit conversions for the scenario."""
    def __init__(self, map_size_nm):
        
        self.map_size_nm = map_size_nm
        self.pixel_per_nm = WIDTH / map_size_nm

    def nm_to_pixels(self, nm_value):
        return nm_value * self.pixel_per_nm

    def meters_to_pixels(self, meters):
        nm = meters / METERS_PER_NM
        return self.nm_to_pixels(nm)

    def nm_position_to_pixels(self, nm_x, nm_y):
        return Position(nm_x * self.pixel_per_nm, nm_y * self.pixel_per_nm)