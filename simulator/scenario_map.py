# scenario_map.py
import pygame
from simulator.position import Position

METERS_PER_NM = 1852.0
SECONDS_PER_HOUR = 3600.0

class Map:
    """Handles the scaling and unit conversions for the scenario."""
    def __init__(self, map_size_nm, window_width, window_height):
        """
        Initialize the map with the size in nautical miles and the current window dimensions.
        
        :param map_size_nm: Size of the map in nautical miles (assumed to be both width and height).
        :param window_width: Current width of the window in pixels.
        :param window_height: Current height of the window in pixels.
        """
        self.map_size_nm = map_size_nm
        self.window_width = window_width
        self.window_height = window_height
        self.update_scaling()

    def update_scaling(self):
        """
        Update the pixel scaling based on the current window size.
        This ensures that the map scales appropriately to fill the window.
        """
        # Separate scaling factors for x and y to stretch the map to fit the window
        self.pixel_per_nm_x = self.window_width / self.map_size_nm
        self.pixel_per_nm_y = self.window_height / self.map_size_nm

    def nm_to_pixels_x(self, nm_value):
        """
        Convert nautical miles to pixels on the x-axis.
        
        :param nm_value: Distance in nautical miles.
        :return: Distance in pixels.
        """
        return nm_value * self.pixel_per_nm_x

    def nm_to_pixels_y(self, nm_value):
        """
        Convert nautical miles to pixels on the y-axis.
        
        :param nm_value: Distance in nautical miles.
        :return: Distance in pixels.
        """
        return nm_value * self.pixel_per_nm_y

    def nm_position_to_pixels(self, nm_x, nm_y):
        """
        Convert a position from nautical miles to pixel coordinates.
        
        :param nm_x: X-coordinate in nautical miles.
        :param nm_y: Y-coordinate in nautical miles.
        :return: Position object with pixel coordinates.
        """
        x_px = int((nm_x / self.map_size_nm) * self.window_width)
        # Invert the y-coordinate calculation
        y_px = int(self.window_height - (nm_y / self.map_size_nm) * self.window_height)
        return Position(x_px, y_px)

    def get_map_rect(self):
        """
        Get the rectangle representing the map's position and size on the screen.
        
        :return: pygame.Rect object.
        """
        return pygame.Rect(0, 0, self.window_width, self.window_height)
