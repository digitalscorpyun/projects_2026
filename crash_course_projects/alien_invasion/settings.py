# settings.py
class Settings():
    def __init__(self):
        # ... Screen/Ship settings ...
        self.bg_color = (255, 255, 255)
        self.ship_speed_factor = 1.5

        # Bullet Settings
        # Rationale: Using underscores to create flat attributes.
        self.bullet_speed_factor = 1
        self.bullet_width = 3
        self.bullet_height = 15
        self.bullet_color = (60, 60, 60)