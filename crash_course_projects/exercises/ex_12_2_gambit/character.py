# character.py
import pygame

class Character:
    """A class to manage the centered game character."""

    def __init__(self, screen):
        """Initialize the character and set its starting position."""
        self.screen = screen
        # Rationale: This line was missing, causing the 'screen_rect' error.
        self.screen_rect = screen.get_rect()

        # Load the character image and convert for alpha/transparency performance.
        self.image = pygame.image.load('images/gambit.png').convert_alpha()
        
        # --- THE CHROMATIC STRIKE ---
        # Rationale: Punching out the background color. 
        # Note: If your Gambit background isn't PURE yellow, use an editor to make it transparent.
        self.image.set_colorkey((255, 255, 0)) 
        
        self.rect = self.image.get_rect()

        # --- THE CENTER STRIKE ---
        # Rationale: Aligning character center to screen center.
        self.rect.center = self.screen_rect.center

    def blitme(self):
        """Draw the character at its current location."""
        self.screen.blit(self.image, self.rect)