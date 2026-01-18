# blue_sky.py
import sys
import pygame
from character import Character

def run_exercise():
    pygame.init()
    # Rationale: Creating a 1200x800 window.
    screen = pygame.display.set_mode((1200, 800))
    pygame.display.set_caption("Exercise 12-2: Game Character")

    # --- THE BLUE SKY SHIFT ---
    bg_color = (135, 206, 235) # A Sky Blue RGB triplet.

    character = Character(screen)

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                sys.exit()

        screen.fill(bg_color)
        character.blitme()
        pygame.display.flip()

run_exercise()