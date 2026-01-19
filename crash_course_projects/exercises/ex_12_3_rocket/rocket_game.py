# rocket_game.py
import pygame
from rocket import Rocket
import rocket_functions as rf

def run_rocket_test():
    pygame.init()
    screen = pygame.display.set_mode((1000, 800))
    pygame.display.set_caption("Rocket Sandbox 12-3")
    
    bg_color = (30, 30, 30) # Deep space gray
    rocket = Rocket(screen)

    while True:
        rf.check_events(rocket)
        rocket.update()
        rf.update_screen(bg_color, screen, rocket)

run_rocket_test()