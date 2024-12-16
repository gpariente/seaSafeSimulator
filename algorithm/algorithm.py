# algorithm/search_algorithm.py
import math
import copy
from .api import AlgorithmAPI

class SearchAlgorithm(AlgorithmAPI):
    """
    A concrete implementation of AlgorithmAPI that performs a forward simulation
    of states to detect future collisions.
    """

    def detect_future_collision(self, state, horizon_steps, safety_zone_nm):
        # safety_zone_nm is given directly, no need for conversion here
        collision_distance_nm = 2 * safety_zone_nm

        # Start with all ships as Green
        ship_status = ["Green"] * len(state.ships)

        # Check immediate collisions
        if self.check_collisions(state, ship_status, collision_distance_nm):
            # If immediate collision (Red), no future checks needed
            return ship_status

        # If no immediate Red, simulate future states
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

        for fstep in range(1, horizon_steps + 1):
            future_state.increment_time_step()
            future_state.update_ships()

            # Check collisions at this future step
            for i in range(len(future_state.ships)):
                if ship_status[i] == "Red":
                    continue
                for j in range(i+1, len(future_state.ships)):
                    if ship_status[j] == "Red":
                        continue
                    dist_nm = self.distance_nm(future_state.ships[i], future_state.ships[j])
                    if dist_nm < collision_dist_nm:
                        # Mark ships as Orange if not Red
                        if ship_status[i] != "Red":
                            ship_status[i] = "Orange"
                        if ship_status[j] != "Red":
                            ship_status[j] = "Orange"
                        if not collision_info_logged:
                            print(f"Future collision detected at time step {current_state.time_step}, "
                                  f"future step {fstep}, horizon steps {horizon_steps}")
                            collision_info_logged = True

    def distance_nm(self, ship1, ship2):
        dx = ship1.cx_nm - ship2.cx_nm
        dy = ship1.cy_nm - ship2.cy_nm
        return math.sqrt(dx*dx + dy*dy)
