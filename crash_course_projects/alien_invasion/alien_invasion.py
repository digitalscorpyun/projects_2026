import pygame
from pygame.sprite import Group

from settings import Settings
from ship import Ship
import game_functions as gf

def run_game():
    # Initialize pygame, settings, and screen object.
    # Rationale: Establishing the 'Known Good State' of the environment.
    pygame.init()
    ai_settings = Settings()
    screen = pygame.display.set_mode(
        (ai_settings.screen_width, ai_settings.screen_height))
    pygame.display.set_caption("Alien Invasion")

    # Make a ship.
    ship = Ship(ai_settings, screen)
    
    # Make a group to store bullets in.
    # Rationale: Using pygame.sprite.Group to manage multiple ballistic nodes.
    bullets = Group()

    # Start the main loop for the game.
    while True:
        # Check for keyboard/mouse events (The Dispatcher)
        gf.check_events(ai_settings, screen, ship, bullets)
        
        # Update the ship's position (The Engine)
        ship.update()
        
        # Update bullet positions (The Ballistic Strike)
        # Rationale: Group.update() automatically calls update() on every bullet in the group.
        bullets.update()
        
        # Redraw the screen (The Visualizer)
        # FIX: Synchronized with the 4-argument signature in game_functions.py.
        gf.update_screen(ai_settings, screen, ship, bullets)

run_game()