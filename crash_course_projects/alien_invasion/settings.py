# settings.py

class Settings():
    """A class to store all settings for Alien Invasion."""

    def __init__(self):
        """Initialize the game's settings."""
        # --- SCREEN SETTINGS ---
        # Rationale: Standardizing dimensions and background color.
        self.screen_width = 1200
        self.screen_height = 800
        self.bg_color = (255, 255, 255)
        
        # --- SHIP SETTINGS ---
        self.ship_speed_factor = 1.5

        # --- BULLET SETTINGS ---
        # Rationale: Using underscores to maintain flat attribute hierarchy.
        self.bullet_speed_factor = 1
        self.bullet_width = 3
        self.bullet_height = 15
        self.bullet_color = (60, 60, 60)
        self.bullets_allowed = 3