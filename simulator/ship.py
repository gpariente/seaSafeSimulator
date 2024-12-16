import math
from simulator.position import Position

class Ship:
    def __init__(self, ship_id, source_nm_pos, dest_nm_pos, width_m, length_m, max_speed_knots, role=None):
        self.id = ship_id
        # source_nm_pos and dest_nm_pos are Position objects in NM now
        self.source = source_nm_pos
        self.destination = dest_nm_pos

        # Store ship dimensions in meters or convert to NM for internal logic if needed
        self.width_m = width_m
        self.length_m = length_m

        self.maxSpeed = max_speed_knots   # in knots (NM/hour)
        self.currentSpeed = max_speed_knots  # start at max speed
        self.role = role if role else "Unknown"
        self.status = "Green"  # default status

        # Current position starts at source (in NM)
        self.cx_nm = self.source.x
        self.cy_nm = self.source.y

        # Destination center also in NM
        self.dest_cx_nm = self.destination.x
        self.dest_cy_nm = self.destination.y

        # Calculate direction and heading in NM
        dx = self.dest_cx_nm - self.cx_nm
        dy = self.dest_cy_nm - self.cy_nm
        dist_dir = math.sqrt(dx*dx + dy*dy)
        if dist_dir > 1e-6:
            self.direction = (dx/dist_dir, dy/dist_dir)
        else:
            self.direction = (0, 0)

        # Heading in degrees: atan2(dy,dx)
        # Define 0 degrees as East, angle increases counterclockwise
        self.heading = math.degrees(math.atan2(dy, dx))

    def get_position(self):
        # Return current position in NM as a Position object
        return Position(self.cx_nm, self.cy_nm)

    def reached_destination(self):
        dist_to_dest = math.sqrt((self.dest_cx_nm - self.cx_nm)**2 + (self.dest_cy_nm - self.cy_nm)**2)
        return dist_to_dest <= (1.0 / 1852.0)  # e.g., 1 meter tolerance in NM (1/1852 NM)

    def future_position(self, steps):
        # Steps in seconds, and speed in NM/h
        # NM/sec = knots/3600
        nm_per_sec = self.currentSpeed / 3600.0
        fx = self.cx_nm + self.direction[0]*nm_per_sec*steps
        fy = self.cy_nm + self.direction[1]*nm_per_sec*steps
        return Position(fx, fy)

    def update_position(self, delta_seconds=1.0):
        # Assuming 1 frame = 1 second, if using a different timestep, adjust delta_seconds.
        nm_per_sec = self.currentSpeed / 3600.0
        dx = self.dest_cx_nm - self.cx_nm
        dy = self.dest_cy_nm - self.cy_nm
        dist = math.sqrt(dx*dx + dy*dy)
        step_dist = nm_per_sec * delta_seconds
        if dist > 1e-6:
            if dist < step_dist:
                # We will overshoot the destination, snap to destination
                self.cx_nm = self.dest_cx_nm
                self.cy_nm = self.dest_cy_nm
            else:
                self.cx_nm += self.direction[0] * step_dist
                self.cy_nm += self.direction[1] * step_dist

    def set_status(self, new_status):
        self.status = new_status
