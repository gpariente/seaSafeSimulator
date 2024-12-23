import math
from simulator.action import Action

METERS_PER_NM = 1852.0

class ColregsAlgorithm:
    """
    A 2-ship collision-avoidance approach that:
      - Respects a horizon distance: no checks if distance > horizon.
      - If collision "Orange" or "Red", we do exactly one COLREGS-based maneuver 
        and set is_avoiding=True for the relevant ship(s).
      - If a ship is_avoiding=True, it sticks to that heading/speed 
        until we detect 'completely safe' for the entire horizon => revert.
    """

    def step(self, state, horizon_steps, safety_zone_nm, horizon_nm):
        """
        Called each simulation step.
         - statuses: ["Green","Orange","Red"]
         - actions: [Action(shipId, headingChange, speedChange), ...]
        """
        ships = state.ships
        n = len(ships)
        statuses = ["Green"] * n
        actions = []

        if n < 2:
            return statuses, actions

        ship_a, ship_b = ships[0], ships[1]

        # 1) Evaluate collision status
        statuses = self.detect_future_collision(
            ship_a, ship_b, horizon_steps, safety_zone_nm, horizon_nm
        )

        # 2) For each ship, if it is currently in avoidance mode (ship.is_avoiding):
        #    we skip applying new turns unless we see that we can revert.
        #    We'll gather potential "revert" actions if ships appear safe.
        revert_actions = self.check_if_can_revert(ships, horizon_steps, safety_zone_nm, horizon_nm)

        # 3) If revert_actions are not empty, that means we are fully safe.
        #    We do that instead of collision check logic.
        if revert_actions:
            actions.extend(revert_actions)
        else:
            # 4) If no revert, and if neither ship is in avoidance mode,
            #    then we might do a new avoidance maneuver if "Orange"/"Red".
            #    If a ship is already in avoidance, we do not re-run "resolve_collisions."
            if (not ship_a.is_avoiding) and (not ship_b.is_avoiding):
                if "Red" in statuses or "Orange" in statuses:
                    # produce one-time avoidance action
                    avoidance_actions = self.resolve_collisions(ships, statuses, safety_zone_nm)
                    actions.extend(avoidance_actions)
                    # after we produce them, we'll mark is_avoiding on relevant ships
            else:
                # ships are already avoiding => do nothing
                pass

        return statuses, actions

    # -----------------------------------------------------------------
    #             Collision Detection with Horizon Distance
    # -----------------------------------------------------------------

    def detect_future_collision(self, ship_a, ship_b,
                                horizon_steps, safety_zone_nm, horizon_nm):
        """
        Return ["Green","Red"] or ["Green","Orange"] etc. (for 2 ships).
        """
        statuses = ["Green", "Green"]
        dist_now = self._distance_nm(ship_a.cx_nm, ship_a.cy_nm, ship_b.cx_nm, ship_b.cy_nm)

        # If beyond horizon => no collision checks => "Green"
        if dist_now > horizon_nm:
            return statuses

        # If within horizon => check immediate collision
        min_dist_for_collision = 2 * safety_zone_nm
        if dist_now < min_dist_for_collision:
            statuses[0] = "Red"
            statuses[1] = "Red"
            return statuses

        # Not Red => check future
        found_future_collision = False
        for step_idx in range(1, horizon_steps + 1):
            future_time_sec = step_idx * 30
            fpos_a = ship_a.future_position(future_time_sec)
            fpos_b = ship_b.future_position(future_time_sec)
            dist_future = self._distance_nm(fpos_a.x, fpos_a.y, fpos_b.x, fpos_b.y)
            if dist_future < min_dist_for_collision:
                found_future_collision = True
                break

        if found_future_collision:
            statuses[0] = "Orange"
            statuses[1] = "Orange"
        else:
            statuses[0] = "Green"
            statuses[1] = "Green"

        return statuses

    # -----------------------------------------------------------------
    #    Resolving Collisions Once (One-Time Maneuver) + Mark Avoiding
    # -----------------------------------------------------------------

    def resolve_collisions(self, ships, statuses, safety_zone_nm):
        """
        Produce avoidance actions if "Red" or "Orange".
        Then mark those ships as is_avoiding=True.
        """
        if len(ships) < 2:
            return []

        ship_a, ship_b = ships[0], ships[1]
        actions = []

        # If Red => both starboard + slow
        if "Red" in statuses:
            heading_change = 20.0
            speed_change = -3.0
            actions.append(Action(0, heading_change, speed_change))
            actions.append(Action(1, heading_change, speed_change))
            ship_a.is_avoiding = True
            ship_b.is_avoiding = True
            return actions

        # If Orange => we do scenario logic
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
        else:
            # crossing
            brg_from_a = self._relative_bearing(ship_a, ship_b)
            if 0 <= brg_from_a < 180:
                actions.append(Action(0, 15.0, 0.0))
                ship_a.is_avoiding = True
            else:
                actions.append(Action(1, 15.0, 0.0))
                ship_b.is_avoiding = True

        return actions

    # -----------------------------------------------------------------
    #    Reverting to Normal If Safe (for ships that are_avoiding)
    # -----------------------------------------------------------------

    def check_if_can_revert(self, ships, horizon_steps, safety_zone_nm, horizon_nm):
        """
        If ships in avoidance mode are now fully safe => revert to direct heading & speed.
        'Fully safe' means: 
         1) they're within horizon distance? If they're beyond horizon, it's safe, too.
         2) or if they're within horizon, we ensure the entire next horizon steps has no collision.

        We'll do a quick check. If absolutely no future collision => revert them.
        """
        if len(ships) < 2:
            return []

        ship_a, ship_b = ships[0], ships[1]
        # Only revert if BOTH ships are safe from collisions, 
        # i.e. "Green" across the entire horizon or distance > horizon.
        revert_actions = []

        # 1) Check distance now
        dist_now = self._distance_nm(ship_a.cx_nm, ship_a.cy_nm, ship_b.cx_nm, ship_b.cy_nm)
        if dist_now > horizon_nm:
            # If they're beyond horizon, no collision => revert both if they are avoiding
            if ship_a.is_avoiding or ship_b.is_avoiding:
                revert_actions.extend(self._revert_ship(0, ship_a))
                revert_actions.extend(self._revert_ship(1, ship_b))
            return revert_actions

        # else, within horizon => we do a future check
        min_dist_for_collision = 2 * safety_zone_nm
        future_collision_found = False
        for step_idx in range(1, horizon_steps + 1):
            future_time_sec = step_idx * 30
            fpos_a = ship_a.future_position(future_time_sec)
            fpos_b = ship_b.future_position(future_time_sec)
            dist_future = self._distance_nm(fpos_a.x, fpos_a.y, fpos_b.x, fpos_b.y)
            if dist_future < min_dist_for_collision:
                future_collision_found = True
                break

        if not future_collision_found:
            # completely safe => revert if they are avoiding
            if ship_a.is_avoiding:
                revert_actions.extend(self._revert_ship(0, ship_a))
            if ship_b.is_avoiding:
                revert_actions.extend(self._revert_ship(1, ship_b))

        return revert_actions

    def _revert_ship(self, ship_id, ship):
        """
        Returns a list of actions to realign the ship to its direct heading 
        from current pos->destination, and restore speed to max.
        Mark ship.is_avoiding=False.
        """
        revert_actions = []
        dx = ship.destination_nm_pos.x - ship.cx_nm
        dy = ship.destination_nm_pos.y - ship.cy_nm
        desired_heading = math.degrees(math.atan2(dy, dx)) if abs(dx)+abs(dy)>1e-6 else 0.0
        if desired_heading < 0:
            desired_heading += 360

        current_heading = ship.get_heading_from_direction()
        heading_diff = (desired_heading - current_heading + 180) % 360 - 180

        speed_diff = ship.maxSpeed - ship.currentSpeed

        # If difference is non-negligible, produce an action
        if abs(heading_diff) > 1e-3 or abs(speed_diff) > 1e-3:
            revert_actions.append(Action(ship_id, heading_diff, speed_diff))

        # Mark as done avoiding
        ship.is_avoiding = False
        return revert_actions

    # -----------------------------------------------------------------
    #                       COLREG Scenario Logic
    # -----------------------------------------------------------------

    def _determine_colreg_scenario(self, ship_a, ship_b):
        heading_a = ship_a.get_heading_from_direction()
        heading_b = ship_b.get_heading_from_direction()
        heading_diff = abs((heading_a - heading_b + 180) % 360 - 180)

        rel_brg_a = self._relative_bearing(ship_a, ship_b)
        # HEAD-ON if ~180° difference & other is roughly in front
        if heading_diff > 150 and (rel_brg_a < 30 or rel_brg_a > 330):
            return "head-on"

        # OVERTAKING
        if self._is_overtaking(ship_a, ship_b):
            return "overtaking"
        if self._is_overtaking(ship_b, ship_a):
            return "overtaking"

        # CROSSING
        return "crossing"

    def _is_overtaking(self, overtaker, other):
        heading_o = overtaker.get_heading_from_direction()
        heading_t = other.get_heading_from_direction()
        speed_o = overtaker.currentSpeed
        speed_t = other.currentSpeed

        heading_diff = abs((heading_o - heading_t + 180) % 360 - 180)
        if heading_diff < 20:
            rel_brg = self._relative_bearing(overtaker, other)
            # If other is in front (~0 deg) and overtaker is faster => overtaking
            if rel_brg < 30 or rel_brg > 330:
                if speed_o > speed_t:
                    return True
        return False

    # -----------------------------------------------------------------
    #                          Utilities
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
