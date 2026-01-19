# game_functions.py
import pygame

def update_screen(ai_settings, screen, ship, bullets):
    """Update images on the screen and flip to the new screen."""
    screen.fill(ai_settings.bg_color)
    
    # Rationale: Redraw all bullets behind ship and aliens.
    # We must call the custom draw_bullet() method for each sprite.
    for bullet in bullets.sprites():
        bullet.draw_bullet()
        
    ship.blitme()
    pygame.display.flip()