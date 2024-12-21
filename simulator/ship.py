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
        self.scenario = None  # scenario attribute
        self.cx_nm = self.source_nm_pos.x
        self.cy_nm = self.source_nm_pos.y

        # Calculate initial direction
        dx = self.destination_nm_pos.x - self.cx_nm
        dy = self.destination_nm_pos.y - self.cy_nm
        dist_dir = math.sqrt(dx*dx + dy*dy)
        if dist_dir > 1e-6:
            self.direction = (dx/dist_dir, dy/dist_dir)
        else:
            self.direction = (0,0)

    def update_position(self, delta_seconds=1.0):
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
        pass

    def change_speed(self, speedChange):
        # speedChange in knots: +10, -10, or 0
        new_speed = self.currentSpeed + speedChange
        if new_speed < 0:
            new_speed = 0
        if new_speed > self.maxSpeed:
            new_speed = self.maxSpeed
        self.currentSpeed = new_speed

    def change_heading(self, headingChange):
        # headingChange in degrees: ±10° or 0°
        # Convert current direction to heading:
        current_heading = self.get_heading_from_direction()
        new_heading = (current_heading + headingChange) % 360
        self.direction = self.get_direction_from_heading(new_heading)

    def get_heading_from_direction(self):
        dx, dy = self.direction
        angle_rad = math.atan2(dy, dx)
        angle_deg = math.degrees(angle_rad)
        if angle_deg < 0:
            angle_deg += 360
        return angle_deg

    def get_direction_from_heading(self, heading_deg):
        rad = math.radians(heading_deg)
        dx = math.cos(rad)
        dy = math.sin(rad)
        return (dx, dy)
