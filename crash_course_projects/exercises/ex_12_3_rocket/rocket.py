# rocket.py
import pygame

class Rocket:
    def __init__(self, screen):
        self.screen = screen
        self.screen_rect = screen.get_rect()
        
        # Load image (reuse ship or find rocket)
        self.image = pygame.image.load('images/ship.png').convert_alpha()
        self.rect = self.image.get_rect()
        
        # Start in the center (12-3 Requirement)
        self.rect.center = self.screen_rect.center
        
        # Movement flags
        self.moving_right = False
        self.moving_left = False
        self.moving_up = False
        self.moving_down = False

    def update(self):
        """Update position with 4-way boundary checks."""
        if self.moving_right and self.rect.right < self.screen_rect.right:
            self.rect.centerx += 1
        if self.moving_left and self.rect.left > 0:
            self.rect.centerx -= 1
        if self.moving_up and self.rect.top > 0:
            self.rect.centery -= 1
        if self.moving_down and self.rect.bottom < self.screen_rect.bottom:
            self.rect.centery += 1

    def blitme(self):
        self.screen.blit(self.image, self.rect)