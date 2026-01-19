import sys
import pygame

def run_telemetry():
    pygame.init()
    screen = pygame.display.set_mode((400, 300))
    pygame.display.set_caption("Key Telemetry Sentry")

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                sys.exit()
            
            # --- THE TELEMETRY STRIKE ---
            # Rationale: Print the integer ID of the key pressed.
            elif event.type == pygame.KEYDOWN:
                print(f"SIGNAL DETECTED: Key ID {event.key}")

        pygame.display.flip()

run_telemetry()