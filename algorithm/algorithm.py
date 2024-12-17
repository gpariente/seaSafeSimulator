# algorithm/search_algorithm.py

import math
import copy
from .api import AlgorithmAPI

SECONDS_PER_HOUR = 3600.0

class SearchAlgorithm(AlgorithmAPI):
    def detect_future_collision(self, state, horizon_steps, safety_zone_nm):
        collision_distance_nm = 2 * safety_zone_nm

        ship_status = ["Green"] * len(state.ships)

        if self.check_collisions(state, ship_status, collision_distance_nm):
            return ship_status

        self.simulate_future(state, ship_status, horizon_steps, collision_distance_nm)
        return ship_status

    def check_collisions(self, state, ship_status, collision_dist_nm):
        red_detected = False
        for i in range(len(state.ships)):
            for j in range(i+1, len(state.ships)):
                dist_nm = self.distance_nm(state.ships[i], state.ships[j])
                if dist_nm < collision_dist_nm:
                    ship_status[i] = "Red"
                    ship_status[j] = "Red"
                    red_detected = True
        return red_detected

    def simulate_future(self, current_state, ship_status, horizon_steps, collision_dist_nm):
        collision_info_logged = False
        future_state = copy.deepcopy(current_state)

        steps_data = []
        steps_data.append(self.record_step_data(future_state))

        for fstep in range(1, horizon_steps + 1):
            future_state.increment_time_step()
            future_state.update_ships()

            steps_data.append(self.record_step_data(future_state))

            future_red_found = False
            future_colliding_pairs = []
            for i in range(len(future_state.ships)):
                if ship_status[i] == "Red":
                    continue
                for j in range(i+1, len(future_state.ships)):
                    if ship_status[j] == "Red":
                        continue
                    dist_nm = self.distance_nm(future_state.ships[i], future_state.ships[j])
                    if dist_nm < collision_dist_nm:
                        if ship_status[i] != "Red":
                            ship_status[i] = "Orange"
                        if ship_status[j] != "Red":
                            ship_status[j] = "Orange"
                        future_red_found = True
                        future_colliding_pairs.append((i,j))

            if future_red_found and not collision_info_logged:
                if fstep - 1 >= 0:
                    prev_step_data = steps_data[fstep - 1]
                    if future_colliding_pairs:
                        i, j = future_colliding_pairs[0]
                        scenario, ship_a_role, ship_b_role = self.classify_and_assign_roles(
                            prev_step_data, i, j
                        )
                        # Assign scenario and roles to the ships in the original state
                        # Note: Use current_state.ships (the original state's ships)
                        current_state.ships[i].scenario = scenario
                        current_state.ships[i].role = ship_a_role
                        current_state.ships[j].scenario = scenario
                        current_state.ships[j].role = ship_b_role
                        print(f"Future collision detected at time step {current_state.time_step}, "
                              f"future step {fstep}. Scenario: {scenario}, "
                              f"Ship {i} Role: {ship_a_role}, Ship {j} Role: {ship_b_role}")
                collision_info_logged = True

    def record_step_data(self, state):
        ships_data = []
        for ship in state.ships:
            heading = self.get_ship_heading_angle(ship)
            ships_data.append({
                'pos': (ship.cx_nm, ship.cy_nm),
                'heading': heading
            })
        return ships_data

    def get_ship_heading_angle(self, ship):
        dx, dy = ship.direction
        angle_rad = math.atan2(dy, dx)
        angle_deg = math.degrees(angle_rad)
        if angle_deg < 0:
            angle_deg += 360
        return angle_deg

    def classify_and_assign_roles(self, step_data, i, j):
        ship_a_heading = step_data[i]['heading']
        ship_b_heading = step_data[j]['heading']
        scenario = self.classify_colreg_scenario(ship_a_heading, ship_b_heading)

        ship_a_pos = step_data[i]['pos']
        ship_b_pos = step_data[j]['pos']

        ship_a_dir = self.heading_to_direction(ship_a_heading)
        starboard_side_ship = 'A' if self.is_starboard(ship_a_pos, ship_a_dir, ship_b_pos) else 'B'

        ship_a_role, ship_b_role = self.assign_roles(scenario, starboard_side_ship)
        return scenario, ship_a_role, ship_b_role

    def heading_to_direction(self, heading_deg):
        rad = math.radians(heading_deg)
        dx = math.cos(rad)
        dy = math.sin(rad)
        return (dx, dy)

    def is_starboard(self, ship_a_pos, ship_a_dir, ship_b_pos):
        ax, ay = ship_a_pos
        bx, by = ship_b_pos
        vector_ab = (bx - ax, by - ay)
        cross = ship_a_dir[0]*vector_ab[1] - ship_a_dir[1]*vector_ab[0]
        return cross < 0

    def classify_colreg_scenario(self, ship_a_heading, ship_b_heading):
        course_diff = abs(ship_a_heading - ship_b_heading) % 360
        if course_diff > 180:
            course_diff = 360 - course_diff
        
        if course_diff > 150:
            return "Heading"
        elif course_diff > 45:
            return "Crossing"
        else:
            return "Overtaking"

    def assign_roles(self, scenario, starboard_side_ship):
        if scenario == "Heading":
            return ("Give-way", "Give-way")
        elif scenario == "Crossing":
            if starboard_side_ship == 'A':
                return ("Stand-on", "Give-way")
            else:
                return ("Give-way", "Stand-on")
        elif scenario == "Overtaking":
            return ("Stand-on", "Give-way")
        else:
            return ("Stand-on", "Stand-on")

    def distance_nm(self, ship1, ship2):
        dx = ship1.cx_nm - ship2.cx_nm
        dy = ship1.cy_nm - ship2.cy_nm
        return math.sqrt(dx*dx + dy*dy)
