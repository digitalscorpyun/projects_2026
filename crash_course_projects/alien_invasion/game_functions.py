# game_functions.py
import sys
import pygame
from bullet import Bullet

def check_keydown_events(event, ai_settings, screen, ship, bullets):
    """Respond to keypresses."""
    if event.key == pygame.K_RIGHT:
        ship.moving_right = True
    elif event.key == pygame.K_LEFT:
        ship.moving_left = True
    elif event.key == pygame.K_SPACE:
        # Rationale: Delegating firing logic to fire_bullet function (Pg. 263).
        fire_bullet(ai_settings, screen, ship, bullets)
    elif event.key == pygame.K_q:
        sys.exit()

def fire_bullet(ai_settings, screen, ship, bullets):
    """Fire a bullet if limit not reached yet."""
    # Create a new bullet and add it to the bullets group.
    if len(bullets) < ai_settings.bullets_allowed:
        new_bullet = Bullet(ai_settings, screen, ship)
        bullets.add(new_bullet)

def check_keyup_events(event, ship):
    """Respond to key releases."""
    if event.key == pygame.K_RIGHT:
        ship.moving_right = False
    elif event.key == pygame.K_LEFT:
        ship.moving_left = False

def check_events(ai_settings, screen, ship, bullets):
    """Respond to keypresses and mouse events."""
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            sys.exit()
        elif event.type == pygame.KEYDOWN:
            check_keydown_events(event, ai_settings, screen, ship, bullets)
        elif event.type == pygame.KEYUP:
            check_keyup_events(event, ship)

def update_bullets(bullets):
    """Update position of bullets and get rid of old bullets."""
    # Update bullet positions.
    bullets.update()

    # Get rid of bullets that have disappeared.
    # Rationale: Pure calculation. NO drawing logic allowed here.
    for bullet in bullets.copy():
        if bullet.rect.bottom <= 0:
            bullets.remove(bullet)

def update_screen(ai_settings, screen, ship, alien, bullets):
    """Update images on the screen and flip to the new screen."""
    # 1. Fill background
    screen.fill(ai_settings.bg_color)
    
    # 2. Draw all bullets behind ship
    for bullet in bullets.sprites():
        bullet.draw_bullet()
        
    # 3. Draw ship (THE RESTORATION)
    ship.blitme()
    alien.blitme()
    # 4. Flip display (THE FINAL HANDSHAKE)
    # Rationale: Only flip once EVERYTHING is drawn.
    pygame.display.flip()