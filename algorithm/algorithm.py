import math
from simulator.action import Action
from algorithm.api import CollisionAvoidanceAlgorithm 

METERS_PER_NM = 1852.0

class ColregsAlgorithm(CollisionAvoidanceAlgorithm):
    """
    Updated approach:
      - Once we detect a collision scenario => set statuses to Orange/Red for both ships
        and apply a single starboard turn (if not already in avoidance).
      - As long as either ship.in_danger == True, we do not revert them to Green 
        unless the entire horizon is definitely clear.
      - This prevents flipping: once you're in Orange, you stay in Orange 
        until truly safe for the entire horizon.
    """

    def step(self, state, horizon_steps, safety_zone_nm, horizon_nm):
        ships = state.ships
        n = len(ships)
        statuses = ["Green"] * n
        actions = []

        # Quick exit if <2 ships
        if n < 2:
            return statuses, actions

        ship_a, ship_b = ships[0], ships[1]

        # 1) If not in danger => do normal horizon check
        #    If either in danger => check if we can revert to Green fully
        if not (ship_a.in_danger or ship_b.in_danger):
            statuses = self.detect_future_collision(
                ship_a, ship_b, horizon_steps, safety_zone_nm, horizon_nm
            )
        else:
            statuses = self.detect_future_collision(
                ship_a, ship_b, horizon_steps, safety_zone_nm, horizon_nm
            )
            if statuses == ["Green", "Green"]:
                # Double check entire horizon is safe
                can_revert = self._check_future_safety(ship_a, ship_b, horizon_steps, safety_zone_nm, horizon_nm)
                if not can_revert:
                    statuses = ["Orange", "Orange"]
                # else, truly revert to green

        # 2) Assign statuses temporarily (so we can see "Red" or "Orange" etc.)
        for i, st in enumerate(statuses):
            ships[i].set_status(st)

        # 3) If collision -> classify scenario & roles
        if "Red" in statuses:
            scenario = self._determine_colreg_scenario(ship_a, ship_b)
            ship_a.scenario = scenario
            ship_b.scenario = scenario
            self._assign_roles(ship_a, ship_b, scenario)

            self._handle_red(ships, actions)

        elif "Orange" in statuses:
            scenario = self._determine_colreg_scenario(ship_a, ship_b)
            ship_a.scenario = scenario
            ship_b.scenario = scenario
            self._assign_roles(ship_a, ship_b, scenario)

            self._handle_orange(ships, actions)

        else:
            # "Green" => revert if needed
            for i, ship in enumerate(ships):
                if ship.is_avoiding:
                    revert_actions = self._revert_ship(i, ship)
                    actions.extend(revert_actions)

        return statuses, actions
    
    def _assign_roles(self, ship_a, ship_b, scenario):
        """
        Set roles for each ship given the scenario:
          'head-on' => both give-way
          'overtaking' => overtaker is give-way, other is stand-on
          'crossing' => the vessel which has the other on her starboard side is give-way
        """
        if scenario == "head-on":
            ship_a.role = "Give-way"
            ship_b.role = "Give-way"

        elif scenario == "overtaking":
            if self._is_overtaking(ship_a, ship_b):
                ship_a.role = "Give-way"
                ship_b.role = "Stand-on"
            else:
                ship_b.role = "Give-way"
                ship_a.role = "Stand-on"

        else:  # "crossing"
            brg_a = self._relative_bearing(ship_a, ship_b)
            # if ship_b is on the starboard side of ship_a => ship_a is give-way
            # we interpret "0 <= brg_a < 180" as "b is to my front hemisphere"
            if 0 <= brg_a < 180:
                ship_a.role = "Give-way"
                ship_b.role = "Stand-on"
            else:
                ship_b.role = "Give-way"
                ship_a.role = "Stand-on"

    # -----------------------------------------------------------------
    #                      Collision Detection
    # -----------------------------------------------------------------

    def detect_future_collision(self, ship_a, ship_b,
                                horizon_steps, safety_zone_nm, horizon_nm):
        """
        Return ["Green","Red"], ["Green","Orange"], etc. for the two ships.
        once collision is found, we do not auto revert to Green next step 
        unless horizon is fully safe.
        """
        statuses = ["Green","Green"]
        dist_now = self._distance_nm(ship_a.cx_nm, ship_a.cy_nm, ship_b.cx_nm, ship_b.cy_nm)

        # If beyond horizon => "Green"
        if dist_now > horizon_nm:
            return statuses

        # Otherwise check immediate collision
        min_dist_for_collision = 2 * safety_zone_nm
        if dist_now < min_dist_for_collision:
            return ["Red","Red"]

        # Not red => check future
        future_collision = False
        if dist_now < min_dist_for_collision:
            return ["Red", "Red"]
        for step_idx in range(0, horizon_steps+1):
            future_time_sec = step_idx * 15 # NEED TO IMPORT PHYSICS STEP
            fa = ship_a.future_position(future_time_sec)
            fb = ship_b.future_position(future_time_sec)
            dist_f = self._distance_nm(fa.x, fa.y, fb.x, fb.y)
            if dist_f < min_dist_for_collision:
                future_collision = True
                break

        if future_collision:
            return ["Orange","Orange"]
        else:
            return ["Green","Green"]

    def _check_future_safety(self, ship_a, ship_b, horizon_steps, safety_zone_nm, horizon_nm):
        """
        Returns True if the entire horizon has NO collisions, or they are beyond horizon distance.
        """
        dist_now = self._distance_nm(ship_a.cx_nm, ship_a.cy_nm, ship_b.cx_nm, ship_b.cy_nm)
        if dist_now > horizon_nm:
            return True  # beyond horizon => safe

        min_dist_for_collision = 2 * safety_zone_nm
        for step_idx in range(0, horizon_steps + 1):
            future_time_sec = step_idx * 15
            fa = ship_a.future_position(future_time_sec)
            fb = ship_b.future_position(future_time_sec)
            dist_f = self._distance_nm(fa.x, fa.y, fb.x, fb.y)
            if dist_f < min_dist_for_collision:
                return False
        return True

    # -----------------------------------------------------------------
    #                      Handling Red / Orange
    # -----------------------------------------------------------------

    def _handle_red(self, ships, actions):
        """
        If immediate collision => if not is_avoiding, produce starboard + slow.
        """
        if len(ships) < 2: return
        ship_a, ship_b = ships[0], ships[1]

        if not ship_a.is_avoiding and not ship_b.is_avoiding:
            # Both do starboard turn
            actions.append(Action(0, 20.0, -3.0))
            actions.append(Action(1, 20.0, -3.0))
            ship_a.is_avoiding = True
            ship_b.is_avoiding = True

    def _handle_orange(self, ships, actions):
        """
        Future collision => apply one-time COLREGS maneuver if not avoiding.
        """
        if len(ships) < 2: return
        ship_a, ship_b = ships[0], ships[1]

        # If either is already is_avoiding => do nothing
        if ship_a.is_avoiding or ship_b.is_avoiding:
            return

        # else we do a single starboard turn for the relevant ship(s)
        scenario = self._determine_colreg_scenario(ship_a, ship_b)
        if scenario == "head-on":
            actions.append(Action(0, 15.0, 0.0))
            actions.append(Action(1, 15.0, 0.0))
            ship_a.is_avoiding = True
            ship_b.is_avoiding = True
        elif scenario == "overtaking":
            if self._is_overtaking(ship_a, ship_b):
                actions.append(Action(0, 15.0, 0.0))
                ship_a.is_avoiding = True
            else:
                actions.append(Action(1, 15.0, 0.0))
                ship_b.is_avoiding = True
        else: # crossing
            brg_a = self._relative_bearing(ship_a, ship_b)
            if 0 <= brg_a < 180:
                actions.append(Action(0, 15.0, 0.0))
                ship_a.is_avoiding = True
            else:
                actions.append(Action(1, 15.0, 0.0))
                ship_b.is_avoiding = True

    # -----------------------------------------------------------------
    #                         Reverting
    # -----------------------------------------------------------------

    def _revert_ship(self, ship_id, ship):
        """
        If we decide "Green" is safe, revert heading to direct path and speed to max.
        Set ship.is_avoiding=False so no more collisions are repeated.
        """
        revert_actions = []
        # Recompute direct heading to destination
        dx = ship.destination_nm_pos.x - ship.cx_nm
        dy = ship.destination_nm_pos.y - ship.cy_nm
        desired_heading = math.degrees(math.atan2(dy, dx)) if abs(dx)+abs(dy)>1e-6 else 0.0
        if desired_heading < 0:
            desired_heading += 360

        current_heading = ship.get_heading_from_direction()
        heading_diff = (desired_heading - current_heading + 180) % 360 - 180

        speed_diff = ship.maxSpeed - ship.currentSpeed

        # If different, produce an action
        if abs(heading_diff)>1e-3 or abs(speed_diff)>1e-3:
            revert_actions.append(Action(ship_id, heading_diff, speed_diff))

        # Mark not avoiding
        ship.is_avoiding = False
        return revert_actions

    # -----------------------------------------------------------------
    #                    COLREG Scenario Logic
    # -----------------------------------------------------------------
    def _determine_colreg_scenario(self, ship_a, ship_b):
        heading_a = ship_a.get_heading_from_direction()
        heading_b = ship_b.get_heading_from_direction()
        heading_diff = abs((heading_a - heading_b + 180) % 360 - 180)

        rel_brg_a = self._relative_bearing(ship_a, ship_b)
        if heading_diff > 150 and (rel_brg_a < 30 or rel_brg_a > 330):
            return "head-on"

        if self._is_overtaking(ship_a, ship_b) or self._is_overtaking(ship_b, ship_a):
            return "overtaking"

        return "crossing"

    def _is_overtaking(self, overtaker, other):
        heading_o = overtaker.get_heading_from_direction()
        heading_t = other.get_heading_from_direction()
        speed_o = overtaker.currentSpeed
        speed_t = other.currentSpeed

        heading_diff = abs((heading_o - heading_t + 180) % 360 - 180)
        if heading_diff < 20:
            rel_brg = self._relative_bearing(overtaker, other)
            if rel_brg < 30 or rel_brg > 330:
                if speed_o > speed_t:
                    return True
        return False

    # -----------------------------------------------------------------
    #                         Utilities
    # -----------------------------------------------------------------
    def _distance_nm(self, x1, y1, x2, y2):
        dx = x1 - x2
        dy = y1 - y2
        return math.sqrt(dx*dx + dy*dy)

    def _relative_bearing(self, ship_from, ship_to):
        heading_from = ship_from.get_heading_from_direction()
        dx = ship_to.cx_nm - ship_from.cx_nm
        dy = ship_to.cy_nm - ship_from.cy_nm
        bearing_abs = math.degrees(math.atan2(dy, dx))
        if bearing_abs < 0:
            bearing_abs += 360
        rel_bearing = (bearing_abs - heading_from) % 360
        return rel_bearing
