# ==============================================================================
# ✶⌁✶ alien.py — THE INVADER ENGINE v1.1.0 [HARDENED]
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

        # 1. THE ALPHA HANDSHAKE
        # Load and prepare transparency metadata.
        original_image = pygame.image.load('images/alien.png').convert_alpha()

        # 2. THE SMOOTH STRIKE
        # Rationale: Re-scaling the massive 860x948 asset to a manageable 60x60.
        self.image = pygame.transform.smoothscale(original_image, (60, 60))

        # 3. THE REINFORCEMENT FILTER
        # Rationale: Final sweep to nuke any residual 'off-white' fringe noise.
        self.image.set_colorkey((255, 255, 255))

        self.rect = self.image.get_rect()

        # Start each new alien near the top left of the screen.
        self.rect.x = self.rect.width
        self.rect.y = self.rect.height
        
        # Store the alien's exact position.
        self.x = float(self.rect.x)

    def blitme(self):
        """Draw the alien at its current location."""
        self.screen.blit(self.image, self.rect)