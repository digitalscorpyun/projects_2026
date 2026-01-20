# ==============================================================================
# ✶⌁✶ alien.py — THE INVADER ENGINE v1.3.0 [HARDENED]
# ==============================================================================
import pygame
from pygame.sprite import Sprite

class Alien(Sprite):
    """A class to represent a single alien in the fleet."""

    def __init__(self, ai_settings, screen):
        """Initialize the alien and set its starting position."""
        super(Alien, self).__init__()
        self.screen = screen
        self.ai_settings = ai_settings

        # 1. THE DETERMINISTIC LOAD
        original_image = pygame.image.load('images/alien.jpg').convert()

        # 2. THE SAMPLER PROTOCOL
        # Rationale: Instead of assuming (255,255,255), we sample the pixel 
        # at (0,0). This ensures the background is keyed regardless of its 
        # exact RGB value.
        bg_color_sample = original_image.get_at((0, 0))
        original_image.set_colorkey(bg_color_sample)

        # 3. THE SCALE STRIKE
        # Rationale: Standard 'scale' is used here instead of 'smoothscale'
        # to prevent the math from creating new 'fringe' colors.
        self.image = pygame.transform.scale(original_image, (60, 60))

        self.rect = self.image.get_rect()

        # Start each new alien near the top left of the screen.
        self.rect.x = self.rect.width
        self.rect.y = self.rect.height
        self.x = float(self.rect.x)

    def blitme(self):
        """Draw the alien at its current location."""
        self.screen.blit(self.image, self.rect)