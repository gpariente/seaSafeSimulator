# simulator/ship.py

import math
from simulator.position import Position

class Ship:
    def __init__(self, ship_id, source_nm_pos, dest_nm_pos, width_m, length_m, max_speed_knots, role="Unknown"):
        self.id = ship_id
        self.source_nm_pos = source_nm_pos
        self.destination_nm_pos = dest_nm_pos
        self.width_m = width_m
        self.length_m = length_m
        self.maxSpeed = max_speed_knots
        self.currentSpeed = max_speed_knots
        self.role = role
        self.scenario = None  # Added scenario attribute
        # Current position starts at source
        self.cx_nm = self.source_nm_pos.x
        self.cy_nm = self.source_nm_pos.y

        # Calculate direction
        dx = self.destination_nm_pos.x - self.cx_nm
        dy = self.destination_nm_pos.y - self.cy_nm
        dist_dir = math.sqrt(dx*dx + dy*dy)
        if dist_dir > 1e-6:
            self.direction = (dx/dist_dir, dy/dist_dir)
        else:
            self.direction = (0,0)

    def update_position(self, delta_seconds=1.0):
        # nm/sec
        nm_per_sec = self.currentSpeed / 3600.0
        dx = self.destination_nm_pos.x - self.cx_nm
        dy = self.destination_nm_pos.y - self.cy_nm
        dist = math.sqrt(dx*dx + dy*dy)
        step_dist = nm_per_sec * delta_seconds
        if dist > 1e-6:
            if dist < step_dist:
                self.cx_nm = self.destination_nm_pos.x
                self.cy_nm = self.destination_nm_pos.y
            else:
                self.cx_nm += self.direction[0] * step_dist
                self.cy_nm += self.direction[1] * step_dist

    def reached_destination(self):
        dist_to_dest = math.sqrt((self.destination_nm_pos.x - self.cx_nm)**2 + (self.destination_nm_pos.y - self.cy_nm)**2)
        return dist_to_dest <= 0.1

    def future_position(self, steps):
        nm_per_sec = self.currentSpeed / 3600.0
        fx = self.cx_nm + self.direction[0]*nm_per_sec*steps
        fy = self.cy_nm + self.direction[1]*nm_per_sec*steps
        return Position(fx, fy)

    def set_status(self, status):
        # If needed, handle status changes here
        pass
