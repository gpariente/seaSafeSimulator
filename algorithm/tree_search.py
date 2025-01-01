# tree_search.py
import math
import numpy as np
from algorithm.api import CollisionAvoidanceAlgorithm
from simulator.ship import Ship  
from simulator.position import Position

METERS_PER_NM = 1852.0

class TreeSearchAlgorithm(CollisionAvoidanceAlgorithm):
    def __init__(self, action_space, physics_step, observation):
        self.action_space = action_space
        self.physics_step = physics_step
        self.horizon_steps = 0


    def choose_action(self, observation):
        """
        Chooses actions for each ship based on the observation.
        Ships maintain course and speed if no collision is detected.

        Args:
            observation (dict): The observation from the environment.

        Returns:
            np.ndarray: An array of action indices, one for each ship.
        """
        num_ships = len(observation["ships"])
        actions = np.zeros(num_ships, dtype=int)  # Initialize actions to maintain course and speed

        for i, ship_data in enumerate(observation["ships"]):
            if ship_data["status"] == "Green":
                # Maintain course and speed
                actions[i] = self.action_space.maintain_course_and_speed_action_index()

            elif ship_data["status"] == "Orange":
                # Maintain course and speed
                actions[i] = self.action_space.maintain_course_and_speed_action_index()
            else:  # Red status - you can implement a more sophisticated logic here if needed
                # For now, also maintain course and speed
                actions[i] = self.action_space.maintain_course_and_speed_action_index()

        return actions



    def step(self, observation, ships):
            """
            Detects potential collisions, determines COLREGs scenarios, and assigns roles.

            Args:
                observation (dict): The observation from the environment.
                ships (list): List of Ship objects.

            Returns:
                tuple: A tuple containing:
                    - statuses (list): A list of statuses for each ship (e.g., "Green", "Orange", "Red").
                    - scenarios (list): A list of COLREGs scenarios for each ship (or None if not applicable).
                    - roles (list): A list of roles for each ship (or None if not applicable).
            """

            scenarios = [None] * len(ships)
            roles = [None] * len(ships)

            # Simplified Collision Detection and Status Updates
            collision_pairs = self.detect_collisions(observation, ships)

            for i, j in collision_pairs:
                ship_i_data = observation["ships"][i]
                ship_j_data = observation["ships"][j]

                # Classify the scenario at the time of collision
                scenario = self._determine_colreg_scenario(ship_i_data, ship_j_data)
                scenarios[i] = scenario
                scenarios[j] = scenario

                # Assign roles based on the scenario
                ship_i_role, ship_j_role = self._assign_roles(ship_i_data, ship_j_data, scenario)
                roles[i] = ship_i_role
                roles[j] = ship_j_role

            statuses = [ship.status for ship in ships]

            return statuses, scenarios, roles

    def detect_collisions(self, observation, ships):
        """
        Detects collisions between all pairs of ships within the horizon distance and updates ship statuses.

        Args:
            observation (dict): The observation from the environment.
            ships (list): List of Ship objects.

        Returns:
            list: A list of tuples, where each tuple contains the indices of a pair of ships in collision.
        """
        collision_pairs = []
        num_ships = len(ships)
        safety_zone_nm = observation["safety_zone_m"] / METERS_PER_NM

        for i in range(num_ships):
            for j in range(i + 1, num_ships):
                ship_i = ships[i]
                ship_j = ships[j]

                # Check for immediate collision
                if self._is_immediate_collision(ship_i, ship_j, safety_zone_nm):
                    print(f"Immediate collision detected between Ship {ship_i.id} and Ship {ship_j.id}")
                    if ship_i.status != "Red":
                        ship_i.set_status("Red")
                    if ship_j.status != "Red":
                        ship_j.set_status("Red")
                    collision_pairs.append((i, j))
                    continue  # Continue to the next pair if immediate collision found

                # Check for future collisions only if no immediate collision
                future_collision_time = self._detect_future_collision(ship_i, ship_j, safety_zone_nm, observation)
                if future_collision_time != -1:
                    print(f"Future collision detected between Ship {ship_i.id} and Ship {ship_j.id} at time step {future_collision_time}")
                    if ship_i.status != "Red":
                        ship_i.set_status("Orange")
                    if ship_j.status != "Red":
                        ship_j.set_status("Orange")
                    collision_pairs.append((i, j))

        # Reset status to Green if no collision is detected
        for i in range(num_ships):
            ship_i_in_collision = False
            for j in range(num_ships):
                if i != j:
                    # Check for immediate collision at the current time step
                    if self._is_immediate_collision(ships[i], ships[j], safety_zone_nm):
                        ship_i_in_collision = True
                        break
                    # Check for future collision at the current time step
                    if self._detect_future_collision(ships[i], ships[j], safety_zone_nm, observation):
                        ship_i_in_collision = True
                        break
            if not ship_i_in_collision:
                ships[i].set_status("Green")

        return collision_pairs

    def _is_immediate_collision(self, ship_i, ship_j, safety_zone_nm):
        """
        Checks if there is an immediate collision between two ships.
        """
        dist_now = self._distance_nm(ship_i.cx_nm, ship_i.cy_nm, ship_j.cx_nm, ship_j.cy_nm)
        return dist_now < safety_zone_nm

    def _detect_future_collision(self, ship_i, ship_j, safety_zone_nm, observation):
            """
            Detects if a future collision will occur between two ships within the horizon.

            Args:
                ship_i (Ship): The first ship.
                ship_j (Ship): The second ship.
                safety_zone_nm (float): The safety zone distance in nautical miles.
                observation (dict): The observation from the environment, including horizon steps.

            Returns:
                bool: True if a future collision is detected within the horizon, False otherwise.
            """
            # Use the horizon steps from the observation
            horizon_steps = observation["horizon_steps"]
            current_time_step = observation["time_step"]

            for step in range(1, horizon_steps + 1):
                future_time_sec = step * self.physics_step

                # Calculate future positions for both ships
                ship_i_future_pos = ship_i.future_position(future_time_sec)
                ship_j_future_pos = ship_j.future_position(future_time_sec)

                # Calculate the distance between the future positions
                distance_future = self._distance_nm(ship_i_future_pos.x, ship_i_future_pos.y, ship_j_future_pos.x, ship_j_future_pos.y)

                # If the distance is less than the safety zone, a collision is detected
                if distance_future < safety_zone_nm:
                    # Calculate the actual time step when the collision is predicted to occur
                    collision_time_step = current_time_step + step + 1
                    print(f"Future collision detected between Ship {ship_i.id} and Ship {ship_j.id} at time step {collision_time_step}")
                    return True  # Collision detected at this future time step

            return False  # No collision detected within the horizon


    def _determine_colreg_scenario(self, ship_i_data, ship_j_data):
        """
        Determines the COLREGs scenario between two ships based on their positions and headings.

        Args:
            ship_i_data (dict): Data of the first ship.
            ship_j_data (dict): Data of the second ship.

        Returns:
            str: The COLREGs scenario ("head-on", "overtaking", "crossing-give-way", or "crossing-stand-on").
        """
        theta_A = math.radians(ship_i_data["heading"])  # Own ship's heading in radians
        theta_B = math.radians(ship_j_data["heading"])  # Target ship's heading in radians
        D_AB = self._distance_nm(ship_i_data["position"][0], ship_i_data["position"][1],
                                 ship_j_data["position"][0], ship_j_data["position"][1])  # Distance between ships

        # Relative bearing of the target ship from the own ship
        phi_AB = math.atan2(ship_j_data["position"][1] - ship_i_data["position"][1],
                            ship_j_data["position"][0] - ship_i_data["position"][0])
        if phi_AB < 0:
            phi_AB += 2 * math.pi

        # Relative course angle between the two ships
        gamma_AB = abs(theta_A - theta_B)

        # Calculate q parameter as per the article
        q = phi_AB - theta_A
        if q > math.pi:
            q -= 2 * math.pi
        elif q < -math.pi:
            q += 2 * math.pi

        # Determine encounter situation based on q
        if -5 <= math.degrees(q) <= 5:
            scenario = "head-on"
        elif -112.5 <= math.degrees(q) < -5:
            scenario = "crossing-give-way"
        elif 5 < math.degrees(q) <= 112.5:
            scenario = "crossing-stand-on"
        elif (112.5 < math.degrees(q) <= 180) or (-180 <= math.degrees(q) < -112.5):
            scenario = "overtaking"
        else:
            scenario = "unknown"  # This should ideally not happen

        return scenario

    def _is_overtaking(self, overtaker_data, other_data, relative_bearing):
        """
        Checks if one ship is overtaking another based on COLREGs definition.
        """
        overtaker_speed = overtaker_data["speed"]
        other_speed = other_data["speed"]
        heading_difference = abs(overtaker_data["heading"] - other_data["heading"])

        # Check if the overtaker is faster and approaching from behind within 67.5 degrees of the stern
        if overtaker_speed > other_speed and (relative_bearing > 112.5 and relative_bearing < 247.5) and heading_difference < 20:
            return True

        return False

    def _assign_roles(self, ship_i_data, ship_j_data, scenario):
        """
        Assigns roles to two ships based on the COLREGs scenario.

        Args:
            ship_i_data (dict): Data of the first ship.
            ship_j_data (dict): Data of the second ship.
            scenario (str): The COLREGs scenario.

        Returns:
            tuple: A tuple containing the roles of the two ships ("give-way" or "stand-on").
        """
        if scenario == "head-on":
            return "give-way", "give-way"
        elif scenario == "overtaking":
            # For simplicity, we assume the faster ship is the overtaking
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
        """
        Calculates the relative bearing of ship B from ship A.

        Args:
            pos_ship_a (tuple): Position of ship A (x, y).
            heading_ship_a (float): Heading of ship A in degrees.
            pos_ship_b (tuple): Position of ship B (x, y).

        Returns:
            float: The relative bearing in degrees.
        """
        dx = pos_ship_b[0] - pos_ship_a[0]
        dy = pos_ship_b[1] - pos_ship_a[1]
        absolute_bearing = math.degrees(math.atan2(dy, dx))
        relative_bearing = (absolute_bearing - heading_ship_a) % 360
        return relative_bearing

    def _distance_nm(self, x1, y1, x2, y2):
        """Calculates the distance in nautical miles between two points."""
        dx = x1 - x2
        dy = y1 - y2
        return math.sqrt(dx**2 + dy**2)