import os
import sys
import json
import subprocess
import time
import pygame
from enum import Enum


# --- Step 1: Prompt and generate game data ---
description = input("Enter a description for your point-and-click adventure: ")
# Run main.py and pass description via stdin
subprocess.run([sys.executable, "main.py"], input=description + "\n", text=True)

# Wait for game_data.json to appear
data_file = "game_data.json"
while not os.path.exists(data_file):
    time.sleep(0.1)

# Load game data
with open(data_file, 'r') as f:
    game_data = json.load(f)

# --- Step 2: Initialize Pygame ---
pygame.init()
WINDOW_WIDTH, WINDOW_HEIGHT = 800, 800
screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
pygame.display.set_caption("Point-and-Click Adventure")
clock = pygame.time.Clock()

# Load fonts
action_button_font = pygame.font.SysFont(None, 48)
interaction_text_font = pygame.font.SysFont(None, 26)
font = pygame.font.SysFont(None, 20)

# Load puzzles
puzzles = game_data.get("puzzles", {})

# Represent remaining requirements for each puzzle
puzzles_progress = puzzles

# --- Step 3: Load first scene ---
scenes = game_data.get("scenes", {})

current_scene = list(scenes.keys())[0]
for scene in scenes.keys():
    if "START" in scene.upper():
        current_scene = scene

scene_info = scenes[current_scene]
scene_image_file = "scene_" + current_scene + ".jpeg" # TODO: Hardcoded for now

background = pygame.image.load(scene_image_file).convert()
background = pygame.transform.scale(background, (600, 600))
background_rect = background.get_rect()
background_rect.midtop = (WINDOW_WIDTH//2, 40)

# Load cursor
cursor_img = pygame.image.load("ms_cursor.png").convert_alpha()
cursor_img = pygame.transform.scale(cursor_img, (40, 40))
pygame.mouse.set_visible(False)

# Load text, buttons
interaction_text = interaction_text_font.render("Interaction text", False, (255, 255, 255))
interaction_text_rect = interaction_text.get_rect(bottomright=(WINDOW_WIDTH - 10, WINDOW_HEIGHT - 10))

actions = ["talk", "use", "look", "pick up"]
action_rects = {}
PADDING = 10
btn_y = WINDOW_HEIGHT - 40
x_offset = PADDING
for act in actions:
    surf = action_button_font.render(act.title(), False, (255, 255, 255))
    rect = surf.get_rect(topleft=(x_offset, btn_y))
    action_rects[act] = (surf, rect)
    x_offset += rect.width + PADDING

current_action = None

hint_surf = font.render("Hint", False, (255, 255, 255))
hint_button_rect = hint_surf.get_rect(topleft=(x_offset, btn_y))

# Prepare item rects
ITEM_SIZE = 40
item_rects = {}
for name, info in scene_info.get("items", {}).items():
    coords = info.get("coordinates", [0.5, 0.5])
    x = int(coords[0] * WINDOW_WIDTH)
    y = int(coords[1] * WINDOW_HEIGHT)
    rect = pygame.Rect(0, 0, ITEM_SIZE, ITEM_SIZE)
    rect.center = (x, y)
    item_rects[name] = rect

# --- Main Loop ---
running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.MOUSEBUTTONDOWN:
            mx, my = pygame.mouse.get_pos()
            # Check action button click
            for act, (surf, rect) in action_rects.items():
                if rect.collidepoint((mx, my)):
                    current_action = act
            # Check hint button click
            if hint_button_rect:
                if hint_button_rect.collidepoint((mx, my)):
                    # Show a hint for the current scene
                    hint = scene_info.get("hint", "No hint available.")
                    interaction_text = interaction_text_font.render(hint, False, (255, 255, 255))
                    interaction_text_rect = interaction_text.get_rect(bottomright=(WINDOW_WIDTH - 10, WINDOW_HEIGHT - 10))
            # Check item click
            for item_name, rect in item_rects.items():
                if rect.collidepoint((mx, my)) and current_action:
                    print(f"{current_action.title()} on {item_name}")

                    # Set interaction text based on action
                    item_info = scene_info["items"][item_name]
                    if current_action in item_info["interactions"]:
                        interaction_text = interaction_text_font.render(
                            item_info["interactions"][current_action], False, (255, 255, 255)
                        )
                        interaction_text_rect = interaction_text.get_rect(bottomright=(WINDOW_WIDTH - 10, WINDOW_HEIGHT - 10))
                    else:
                        interaction_text = interaction_text_font.render(
                            "I don't feel like doing that.", False, (255, 255, 255)
                        )
                        interaction_text_rect = interaction_text.get_rect(bottomright=(WINDOW_WIDTH - 10, WINDOW_HEIGHT - 10))

                    # Check if current (action, item) matches any puzzle requirements
                    for puzzle_i in range(len(puzzles_progress)):
                        for requirement in puzzles_progress[puzzle_i]["requirements"]:
                            requirement_action_name, requirement_item_name = requirement
                            if (current_action, item_name) == (requirement_action_name, requirement_item_name):
                                # If the current action matches a puzzle requirement, remove the requirement
                                puzzles_progress[puzzle_i]["requirements"] = [req for req in puzzles_progress[puzzle_i] if req != (current_action, item_name)]

                                # Display puzzle completion text
                                interaction_text = interaction_text_font.render(
                                    puzzles_progress[puzzle_i]["completion_text"], False, (255, 204, 102)
                                )
                                interaction_text_rect = interaction_text.get_rect(bottomright=(WINDOW_WIDTH - 10, WINDOW_HEIGHT - 10))
                                break



    # Clear screen
    screen.fill((0, 0, 0))

    # Draw background
    screen.blit(background, background_rect)
    # Draw items as rectangles
    for name, rect in item_rects.items():
        pygame.draw.rect(screen, (200, 50, 50), rect, 2)
        label = font.render(name, True, (255, 255, 255))
        lbl_rect = label.get_rect(midbottom=(rect.centerx, rect.top - 5))
        screen.blit(label, lbl_rect)
    # Draw action buttons
    for act, (surf, rect) in action_rects.items():
        # Highlight selected
        color = (255, 255, 0) if act == current_action else (255, 255, 255)
        surf = action_button_font.render(act.title(), False, color)
        screen.blit(surf, rect)
    # Draw hint button
    hint_button = action_button_font.render("Clue", False, (255, 255, 255))
    hint_button_rect = hint_button.get_rect(topleft=(hint_button_rect.centerx, btn_y))

    # Draw interaction text
    screen.blit(interaction_text, interaction_text_rect)

    # Draw cursor
    mouse_x, mouse_y = pygame.mouse.get_pos()
    screen.blit(cursor_img, (mouse_x, mouse_y))

    pygame.display.flip()
    clock.tick(60)

pygame.quit()

# a pirate ship floating down a river inside a big mansion