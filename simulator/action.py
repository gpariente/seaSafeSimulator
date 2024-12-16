class Action:
    """
    Represents an action that can be taken on a ship at a given time step.
    This includes changes to the ship's heading and speed.
    """
    def __init__(self, shipId, headingChange=0.0, speedChange=0.0):
        self.shipId = shipId
        self.headingChange = headingChange    # in degrees
        self.speedChange = speedChange        # in knots
