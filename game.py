import os
import sys
import json
import subprocess
import time
import pygame
from enum import Enum

DEBUG_GAMEPLAY = False
# DEBUG_GAMEPLAY = True

DEBUG_ITEMS = False
# DEBUG_ITEMS = True

WINDOW_WIDTH, WINDOW_HEIGHT = 1000, 800
RGB_PINK = (255, 105, 180)
INTERACTION_TEXT_POS = (WINDOW_WIDTH//2, 20)

data_file = "game_data.json"

def get_user_text(screen, font, prompt_text, width, height):
    clock = pygame.time.Clock()
    input_text = ""
    prompt_surface = font.render(prompt_text, True, (255, 255, 255))
    prompt_rect = prompt_surface.get_rect(midtop=(width//2, 50))
    active = True
    while active:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RETURN:
                    active = False
                elif event.key == pygame.K_BACKSPACE:
                    input_text = input_text[:-1]
                else:
                    input_text += event.unicode
        screen.fill((0, 0, 0))
        screen.blit(prompt_surface, prompt_rect)
        # Render the current input text
        input_surface = font.render(input_text, True, (255, 255, 255))
        input_rect = input_surface.get_rect(midtop=(width//2, prompt_rect.bottom + 20))
        screen.blit(input_surface, input_rect)
        pygame.display.flip()
        clock.tick(30)
    return input_text

# Initialize game
pygame.init()
screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
pygame.display.set_caption("Point-and-Click Adventure")
clock = pygame.time.Clock()

# Load fonts
action_button_font = pygame.font.SysFont("None", 68)
interaction_text_font = pygame.font.SysFont(None, 48)
font = pygame.font.SysFont(None, 48)

if not DEBUG_GAMEPLAY:
    # Remove old game data
    if os.path.exists("game_data.json"):
        os.remove("game_data.json")

    # description = input("Enter a description for your point-and-click adventure: ")
    description = get_user_text(screen, font, "Describe your point-and-click adventure:", WINDOW_WIDTH, WINDOW_HEIGHT)
    # Run main.py and pass description via stdin
    subprocess.run([sys.executable, "main.py"], input=description + "\n", text=True)

    # Wait for game_data.json to appear
    while not os.path.exists(data_file):
        time.sleep(0.1)

# Load game data
with open(data_file, 'r') as f:
    game_data = json.load(f)

# Load puzzles
puzzles = game_data.get("puzzles", {})

# Remaining requirements for each puzzle
puzzles_progress = puzzles

# Load first scene
scenes = game_data.get("scenes", {})

current_scene = list(scenes.keys())[0]
for scene in scenes.keys():
    if "START" in scene.upper():
        current_scene = scene

scene_info = scenes[current_scene]
scene_image_file = "scene_" + current_scene + ".jpeg" # TODO: Hardcoded for now

background = pygame.image.load(scene_image_file).convert()
background = pygame.transform.scale(background, (900, 600))
background_rect = background.get_rect()
background_rect.midtop = (WINDOW_WIDTH//2, 40)

# Load cursor
cursor_img = pygame.image.load("ms_cursor.png").convert_alpha()
cursor_img = pygame.transform.scale(cursor_img, (40, 40))
pygame.mouse.set_visible(False)

# Load text, buttons
interaction_text = interaction_text_font.render("", False, RGB_PINK)
interaction_text_rect = interaction_text.get_rect(center=INTERACTION_TEXT_POS)

# Load hover text
hover_text = font.render("", False, (255, 255, 255))
hover_text_rect = hover_text.get_rect(bottomright=(WINDOW_WIDTH//2, WINDOW_HEIGHT//2 + 500))

actions = ["talk", "use", "look", "pick up"]
action_rects = {}
PADDING = 20
btn_y = WINDOW_HEIGHT - 80
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
ITEM_SIZE = 100
item_rects = {}
for name, info in scene_info.get("items", {}).items():
    coords = info.get("coordinates", [0.5, 0.5])
    x = int(coords[0] * background.get_width())
    y = int(coords[1] * background.get_height())
    rect = pygame.Rect(0, 0, ITEM_SIZE, ITEM_SIZE)
    rect.center = (x, y)
    item_rects[name] = rect

# Main loop
running = True
while running:
    for event in pygame.event.get():
        cursor_img = pygame.image.load("ms_cursor.png").convert_alpha()
        cursor_img = pygame.transform.scale(cursor_img, (50, 50))

        mx, my = pygame.mouse.get_pos()
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.MOUSEBUTTONDOWN:
            # Check action button click
            for act, (surf, rect) in action_rects.items():
                if rect.collidepoint((mx, my)):
                    current_action = act
            # Check hint button click
            if hint_button_rect:
                if hint_button_rect.collidepoint((mx, my)):
                    # Show a hint for the current scene
                    hint = scene_info.get("hint", "No hint available.")
                    interaction_text = interaction_text_font.render(hint, False, RGB_PINK)
                    interaction_text_rect = interaction_text.get_rect(center=INTERACTION_TEXT_POS)
            # Check item click
            for item_name, rect in item_rects.items():
                adjusted_rect = rect.copy()
                adjusted_rect.topleft = (
                    rect.left + background_rect.left,
                    rect.top + background_rect.top
                )
                if adjusted_rect.collidepoint((mx, my)) and current_action:
                    print(f"{current_action.title()} on {item_name}")

                    # Set interaction text based on action
                    item_info = scene_info["items"][item_name]
                    if current_action in item_info["interactions"]:
                        interaction_text = interaction_text_font.render(item_info["interactions"][current_action], False, RGB_PINK)
                        interaction_text_rect = interaction_text.get_rect(center=INTERACTION_TEXT_POS)
                    else:
                        interaction_text = interaction_text_font.render(
                            "I don't feel like doing that.", False, (255, 255, 255)
                        )
                        interaction_text_rect = interaction_text.get_rect(center=INTERACTION_TEXT_POS)

                    leads_to = scene_info["items"][item_name]["leads_to"]
                    if leads_to != "n/a" and game_data["scenes"][leads_to]["is_locked"] == False:
                        scene_info = scenes[leads_to]
                        
                        # Set background to new scene
                        scene_image_file = "scene_" + leads_to + ".jpeg"
                        # Load and scale the new scene
                        background = pygame.image.load(scene_image_file).convert()
                        background = pygame.transform.scale(background, (900, 600))

                        # Recompute the rect and position it
                        background_rect = background.get_rect()
                        background_rect.midtop = (WINDOW_WIDTH // 2, 40)

                        # Recompute items and their rects
                        item_rects = {}
                        for name, info in scene_info.get("items", {}).items():
                            coords = info.get("coordinates", [0.5, 0.5])
                            x = int(coords[0] * background.get_width())
                            y = int(coords[1] * background.get_height())
                            rect = pygame.Rect(0, 0, ITEM_SIZE, ITEM_SIZE)
                            rect.center = (x, y)
                            item_rects[name] = rect
                        
                        break
                    else:
                        # Check if current (action, item) matches any puzzle requirements
                        for puzzle_name in puzzles_progress.keys():
                            for requirement in puzzles_progress[puzzle_name]["requirements"]:
                                requirement_action_name, requirement_item_name = requirement
                                if (current_action, item_name) == (requirement_action_name, requirement_item_name):
                                    # If the current action matches a puzzle requirement, remove the requirement
                                    puzzles_progress[puzzle_name]["requirements"] = [req for req in puzzles_progress[puzzle_name]["requirements"] if req != [current_action, item_name]]

                                    # Unlock scene
                                    unlocked_scene = puzzles[puzzle_name]["result"]["unlocked_area"]
                                    game_data["scenes"][unlocked_scene]["is_locked"] = False

                                    # Display puzzle completion text
                                    interaction_text = interaction_text_font.render(
                                        puzzles_progress[puzzle_name]["completion_text"], False, (255, 204, 102)
                                    )
                                    interaction_text_rect = interaction_text.get_rect(center=INTERACTION_TEXT_POS)
                                    break

                    if leads_to != "n/a" and game_data["scenes"][leads_to]["is_locked"] == True:
                        hint = scene_info.get("hint", "No hint available.")
                        interaction_text = interaction_text_font.render(hint, False, RGB_PINK)
                        interaction_text_rect = interaction_text.get_rect(center=INTERACTION_TEXT_POS)
        else:
            for item_name, rect in item_rects.items():
                adjusted_rect = rect.copy()
                adjusted_rect.topleft = (
                    rect.left + background_rect.left,
                    rect.top + background_rect.top
                )
                # Event cursor hovers over item
                if adjusted_rect.collidepoint((mx, my)):
                    cursor_img = pygame.image.load("ms_cursor2.png").convert_alpha()
                    cursor_img = pygame.transform.scale(cursor_img, (50, 50))

                    if current_action:
                        hover_text = font.render((current_action + " " + ' '.join(item_name.split('_'))).title(), True, (0, 255, 255))
                    else:
                        hover_text = font.render("", True, (255, 255, 255))

                    break

    # Clear screen
    screen.fill((0, 0, 0))

    # Draw background
    screen.blit(background, background_rect)
    
    if DEBUG_ITEMS:
        # Draw interactable items
        for name, rect in item_rects.items():
            # Offset rect position by background's top-left
            draw_rect = rect.copy()
            draw_rect.topleft = (
                rect.left + background_rect.left,
                rect.top + background_rect.top
            )
            pygame.draw.rect(screen, (200, 50, 50), draw_rect, 2)

            # Draw label relative to adjusted rect
            label = font.render(name, True, (255, 255, 255))
            lbl_rect = label.get_rect(midbottom=(draw_rect.centerx, draw_rect.top - 5))
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

    # Draw hover text
    hover_text_rect = hover_text.get_rect(center=(WINDOW_WIDTH//2, WINDOW_HEIGHT//2 + 270))
    screen.blit(hover_text, hover_text_rect)

    # Draw cursor
    mouse_x, mouse_y = pygame.mouse.get_pos()
    screen.blit(cursor_img, (mouse_x, mouse_y))

    pygame.display.flip()
    clock.tick(60)

pygame.quit()
