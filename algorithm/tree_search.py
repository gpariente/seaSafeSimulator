# tree_search.py
import math
import numpy as np
from algorithm.api import CollisionAvoidanceAlgorithm
from simulator.ship import Ship
from simulator.position import Position
import copy  # NEW
from collections import defaultdict  # NEW

METERS_PER_NM = 1852.0

class TreeSearchAlgorithm(CollisionAvoidanceAlgorithm):
    def __init__(self, action_space, physics_step, observation):
        self.action_space = action_space
        self.physics_step = physics_step
        self.horizon_steps = 0

        # NEW: Store pre-planned maneuvers
        # Structure: self.planned_paths[ship_id][time_step] = action_index
        self.planned_paths = defaultdict(dict)

    # CHANGED: choose_action now checks planned_paths first.
    def choose_action(self, observation):
        """
        Chooses actions for each ship based on the observation and any backtracking plan.
        If a plan exists for (ship_id, current_time_step), use that. Otherwise default.
        """
        num_ships = len(observation["ships"])
        actions = np.zeros(num_ships, dtype=int)

        current_time = observation["time_step"]

        for i, ship_data in enumerate(observation["ships"]):
            ship_id = ship_data["id"]

            # DEBUG: Print which action we choose
            if current_time in self.planned_paths[ship_id]:
                chosen_action = self.planned_paths[ship_id][current_time]
                print(f"[choose_action] T={current_time}, Ship={ship_id}: Using *planned* action index={chosen_action}")  # DEBUG
                actions[i] = chosen_action
            else:
                # Maintain course and speed if no plan
                maintain_idx = self.action_space.maintain_course_and_speed_action_index()
                print(f"[choose_action] T={current_time}, Ship={ship_id}: No plan => maintain course/speed (action={maintain_idx})")  # DEBUG
                actions[i] = maintain_idx

        return actions

    # CHANGED: step() now detects collisions and triggers backtracking if needed.
    def step(self, observation, ships):
        """
        Detects potential collisions, determines COLREGs scenarios, and assigns roles.
        If a future collision is found (Orange), we attempt backtracking.
        """
        scenarios = [None] * len(ships)
        roles = [None] * len(ships)

        # 1) Do collision detection
        collision_pairs = self.detect_collisions(observation, ships)

        # 2) For each collision, classify scenario and assign roles
        for i, j in collision_pairs:
            ship_i_data = observation["ships"][i]
            ship_j_data = observation["ships"][j]
            scenario = self._determine_colreg_scenario(ship_i_data, ship_j_data)
            scenarios[i] = scenario
            scenarios[j] = scenario

            ship_i_role, ship_j_role = self._assign_roles(ship_i_data, ship_j_data, scenario)
            roles[i] = ship_i_role
            roles[j] = ship_j_role

        # 3) If a collision is predicted in the future => ships in Orange
        #    Attempt backtracking for the "give-way" ship.
        #    We do a simple approach: if ship_i or ship_j is "Orange" and is "give-way", plan a quick fix.
        for i, ship in enumerate(ships):
            if ship.status == "Orange":
                # Find collisions in horizon for this ship
                self._plan_backtracking(observation, ships, i)
                
        print(f"[step] T={observation['time_step']} => planned_paths={dict(self.planned_paths)}")  # DEBUG


        statuses = [ship.status for ship in ships]
        return statuses, scenarios, roles

    # NEW: _plan_backtracking tries minimal maneuvers for the give-way ship at time Tcollision-1, Tcollision-2, ...
    def _plan_backtracking(self, observation, ships, orange_ship_idx):
        current_time_step = observation["time_step"]
        horizon_steps = observation["horizon_steps"]
        orange_ship = ships[orange_ship_idx]

        # Only proceed if the ship is 'give-way' typically (simplified check)
        if orange_ship.role != "give-way":
            return

        # Find the earliest future collision time for this ship
        collision_time_step = self._find_earliest_collision_time(observation, ships, orange_ship_idx)
        print(f"[_plan_backtracking] T={current_time_step}, Ship={orange_ship.id}: collision_time_step={collision_time_step}")  # DEBUG
        if collision_time_step == -1:
            print(f"[_plan_backtracking] No future collision for Ship {orange_ship.id}. Nothing to do.")  # DEBUG
            return  # No actual future collision found

        # We'll try single-step maneuvers starting from Tcollision-1, Tcollision-2, ...
        # and see if that resolves the collision.
        for back_step in range(collision_time_step - 1, current_time_step - 1, -1):
            if back_step < current_time_step:
                break
            # We try a small set of actions for the give-way ship at that back_step
            for action_idx in range(len(self.action_space.single_ship_actions)):
                print(f"   Ship {orange_ship.id} => Attempting action_idx={action_idx} at back_step={back_step}")  # DEBUG

                # Create a temporary plan
                temp_plan = copy.deepcopy(self.planned_paths)
                temp_plan[orange_ship.id][back_step] = action_idx

                # Check if this plan avoids collision
                if self._check_plan_avoids_collision(observation, ships, orange_ship_idx, collision_time_step, temp_plan):
                    print(f"      => Found a collision-free plan for Ship {orange_ship.id}! Committing plan.")  # DEBUG

                    # If yes, commit the plan and stop
                    self.planned_paths = temp_plan
                    return

    # NEW: Finds earliest collision time for a given ship
    def _find_earliest_collision_time(self, observation, ships, ship_idx):
        """
        Returns the earliest time step in the horizon at which ship_idx collides with any other ship.
        If no collision, returns -1.
        """
        horizon_steps = observation["horizon_steps"]
        current_time = observation["time_step"]
        safety_zone_nm = observation["safety_zone_m"] / METERS_PER_NM

        for step in range(1, horizon_steps + 1):
            # For each future time step
            future_t = step * self.physics_step
            # The time-step index if we do collisions in discrete steps
            future_time_step = current_time + step

            # Predict ship_idx's future position
            ship_i = ships[ship_idx]
            ship_i_future = ship_i.future_position(future_t)

            # Check collisions with others
            for j, other_ship in enumerate(ships):
                if j == ship_idx:
                    continue
                other_future = other_ship.future_position(future_t)
                dist_future = self._distance_nm(ship_i_future.x, ship_i_future.y, other_future.x, other_future.y)
                if dist_future < safety_zone_nm:
                    return future_time_step

        return -1

    # NEW: Simulate from the current time step up to the collision time step with the proposed plan
    #      to see if collisions are avoided.
    def _check_plan_avoids_collision(self, observation, ships, orange_ship_idx,
                                     collision_time_step, temp_plan):
        current_time = observation["time_step"]
        safety_zone_nm = observation["safety_zone_m"] / METERS_PER_NM
        steps_to_sim = collision_time_step - current_time

        # Copy original ships => sim_ships
        sim_ships = [copy.deepcopy(s) for s in ships]

        for step_idx in range(steps_to_sim):
            sim_time = current_time + step_idx

            # apply actions
            for s in sim_ships:
                ship_id = s.id
                if sim_time in temp_plan[ship_id]:
                    chosen_action_idx = temp_plan[ship_id][sim_time]
                else:
                    chosen_action_idx = self.action_space.maintain_course_and_speed_action_index()

                speed_change, heading_change = self.action_space.decode_action(chosen_action_idx, s)
                # If the resulting speed would be ≤ 0 => skip immediately
                if (s.currentSpeed + speed_change) <= 0:
                    # We reject this plan
                    return False

                s.change_speed(speed_change)
                s.change_heading(heading_change)

            # After movement, if speed is exactly 0, skip as well
            for s in sim_ships:
                if s.currentSpeed <= 0.01:  # or s.currentSpeed < 1, etc.
                    print("      => Plan sets speed near zero => reject.")
                    return False

            # update positions
            for s in sim_ships:
                s.update_position(delta_seconds=self.physics_step)

            # check collisions
            if self._any_collision(sim_ships, safety_zone_nm):
                return False

        return True

    # NEW: Check if any collision among ships
    def _any_collision(self, ships, safety_zone_nm):
        for i in range(len(ships)):
            for j in range(i + 1, len(ships)):
                dist_now = self._distance_nm(ships[i].cx_nm, ships[i].cy_nm,
                                             ships[j].cx_nm, ships[j].cy_nm)
                if dist_now < 2 * safety_zone_nm:
                    return True
        return False

    def detect_collisions(self, observation, ships):
        """
        Detects collisions between all pairs of ships within the horizon distance and updates ship statuses.
        Returns a list of collisions at the current step or future steps.
        """
        collision_pairs = []
        num_ships = len(ships)
        safety_zone_nm = observation["safety_zone_m"] / METERS_PER_NM

        for i in range(num_ships):
            for j in range(i + 1, num_ships):
                ship_i = ships[i]
                ship_j = ships[j]

                # Immediate collision check
                if self._is_immediate_collision(ship_i, ship_j, safety_zone_nm):
                    ship_i.set_status("Red")
                    ship_j.set_status("Red")
                    collision_pairs.append((i, j))
                    continue

                # Future collision
                future_collision_detected = self._detect_future_collision(
                    ship_i, ship_j, safety_zone_nm, observation
                )
                if future_collision_detected:
                    # Mark them Orange if not Red
                    if ship_i.status != "Red":
                        ship_i.set_status("Orange")
                    if ship_j.status != "Red":
                        ship_j.set_status("Orange")
                    collision_pairs.append((i, j))

        # Reset ships to Green if no collision (immediate or future)
        for i in range(num_ships):
            if ships[i].status not in ("Orange", "Red"):
                ships[i].set_status("Green")

        return collision_pairs

    def _is_immediate_collision(self, ship_i, ship_j, safety_zone_nm):
        dist_now = self._distance_nm(ship_i.cx_nm, ship_i.cy_nm, ship_j.cx_nm, ship_j.cy_nm)
        return dist_now < 2 * safety_zone_nm

    def _detect_future_collision(self, ship_i, ship_j, safety_zone_nm, observation):
        horizon_steps = observation["horizon_steps"]
        current_time_step = observation["time_step"]

        for step in range(1, horizon_steps + 1):
            future_time_sec = step * self.physics_step
            ship_i_future_pos = ship_i.future_position(future_time_sec)
            ship_j_future_pos = ship_j.future_position(future_time_sec)
            distance_future = self._distance_nm(
                ship_i_future_pos.x, ship_i_future_pos.y,
                ship_j_future_pos.x, ship_j_future_pos.y
            )
            if distance_future < safety_zone_nm:
                return True
        return False

    def _determine_colreg_scenario(self, ship_i_data, ship_j_data):
        theta_A = math.radians(ship_i_data["heading"])
        theta_B = math.radians(ship_j_data["heading"])
        D_AB = self._distance_nm(ship_i_data["position"][0], ship_i_data["position"][1],
                                 ship_j_data["position"][0], ship_j_data["position"][1])

        phi_AB = math.atan2(ship_j_data["position"][1] - ship_i_data["position"][1],
                            ship_j_data["position"][0] - ship_i_data["position"][0])
        if phi_AB < 0:
            phi_AB += 2 * math.pi

        gamma_AB = abs(theta_A - theta_B)
        q = phi_AB - theta_A
        if q > math.pi:
            q -= 2 * math.pi
        elif q < -math.pi:
            q += 2 * math.pi

        deg_q = math.degrees(q)
        if -5 <= deg_q <= 5:
            scenario = "head-on"
        elif -112.5 <= deg_q < -5:
            scenario = "crossing-give-way"
        elif 5 < deg_q <= 112.5:
            scenario = "crossing-stand-on"
        elif (112.5 < deg_q <= 180) or (-180 <= deg_q < -112.5):
            scenario = "overtaking"
        else:
            scenario = "unknown"

        return scenario

    def _is_overtaking(self, overtaker_data, other_data, relative_bearing):
        overtaker_speed = overtaker_data["speed"]
        other_speed = other_data["speed"]
        heading_difference = abs(overtaker_data["heading"] - other_data["heading"])
        if (overtaker_speed > other_speed and 
            (relative_bearing > 112.5 and relative_bearing < 247.5) and 
            heading_difference < 20):
            return True
        return False

    def _assign_roles(self, ship_i_data, ship_j_data, scenario):
        if scenario == "head-on":
            return "give-way", "give-way"
        elif scenario == "overtaking":
            if ship_i_data["speed"] > ship_j_data["speed"]:
                return "give-way", "stand-on"
            else:
                return "stand-on", "give-way"
        elif scenario == "crossing-give-way":
            return "give-way", "stand-on"
        elif scenario == "crossing-stand-on":
            return "stand-on", "give-way"
        else:
            return "unknown", "unknown"

    def _calculate_relative_bearing(self, pos_ship_a, heading_ship_a, pos_ship_b):
        dx = pos_ship_b[0] - pos_ship_a[0]
        dy = pos_ship_b[1] - pos_ship_a[1]
        absolute_bearing = math.degrees(math.atan2(dy, dx))
        relative_bearing = (absolute_bearing - heading_ship_a) % 360
        return relative_bearing

    def _distance_nm(self, x1, y1, x2, y2):
        dx = x1 - x2
        dy = y1 - y2
        return math.sqrt(dx**2 + dy**2)
