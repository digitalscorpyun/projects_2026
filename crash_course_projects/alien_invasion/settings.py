class Settings():
    """A class to store all settings for Alien Invasion."""

    def __init__(self):
        """Initialize the game's settings."""
        # Screen settings
        self.screen_width = 1200
        self.screen_height = 800
        
        # --- THE NORMALIZATION STRIKE ---
        # Rationale: Neutralizes the fringe artifacts (edge noise) in ship.bmp.
        # Aligns the game environment to the asset's native background.
        self.bg_color = (255, 255, 255) 
        # --------------------------------