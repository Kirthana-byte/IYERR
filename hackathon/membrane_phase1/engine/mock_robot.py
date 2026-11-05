# Provides an explicit, deterministic test double with no physics or perception.
# Movement is planar arithmetic. One private pickup fixture tests holding changes.
# The diagnostic JPEG is not a simulated camera; depth is unavailable (None).
import math
from io import BytesIO
from PIL import Image, ImageDraw
from .robot import Robot


class MockRobot(Robot):
    def __init__(self):
        self.x = 0.0
        self.y = 0.0
        self.heading = 0.0
        self.holding = False
        self.pickup_attempts = 0
        self._state = 'Idle'
        self._fixture = (1.0, 0.0)

    def state(self):
        return dict(state=self._state, x=self.x, y=self.y,
                    heading=self.heading, holding=self.holding, retries=0)

    def move(self, distance):
        # Positive clockwise means +90 degrees points toward negative world y.
        angle = math.radians(self.heading)
        self.x += distance * math.cos(angle)
        self.y -= distance * math.sin(angle)
        self._state = 'Carry' if self.holding else 'Locate'
        return dict(collided=False, moved=distance)

    def turn(self, degrees):
        self.heading = (self.heading + degrees) % 360.0
        self._state = 'Carry' if self.holding else 'Locate'
        return dict(ok=True, heading=self.heading)

    def pickup(self):
        self.pickup_attempts += 1
        if self.holding:
            return dict(success=False)
        dx, dy = self._fixture[0] - self.x, self._fixture[1] - self.y
        distance = math.hypot(dx, dy)
        bearing = math.degrees(math.atan2(-dy, dx))
        error = (bearing - self.heading + 180) % 360 - 180
        success = distance <= 0.5 and (distance < 1e-12 or abs(error) <= 30)
        if success:
            self.holding = True
            self._state = 'Carry'
        return dict(success=success)

    def drop(self):
        if not self.holding:
            return dict(in_zone=False)
        self._fixture = (self.x, self.y)
        self.holding = False
        # Test zone is a private unit square centred at the origin.
        in_zone = abs(self.x) <= 0.5 and abs(self.y) <= 0.5
        self._state = 'Idle'
        return dict(in_zone=in_zone)

    def look(self):
        picture = Image.new('RGB', (640, 480), (36, 40, 48))
        ImageDraw.Draw(picture).text((20, 20), 'MOCK MODE - NO SIMULATED CAMERA', fill='white')
        output = BytesIO()
        picture.save(output, format='JPEG')
        return output.getvalue()

    def depth(self):
        return None
