import pygame
import sys

WINDOW_WIDTH = 720
WINDOW_HEIGHT = 820

pygame.init()
screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
pygame.display.set_caption("Point-and-Click Drag Demo")

clock = pygame.time.Clock()

# Setup font
font = pygame.font.SysFont(None, 36)  # None = default font, 36 = font size

# Set cursor
cursor_img = pygame.image.load("ms_cursor.png").convert_alpha()
cursor_img = pygame.transform.scale(cursor_img, (40, 40))
pygame.mouse.set_visible(False)

# Load background (optional)
background = pygame.image.load("scene_night_time_jazz_lounge.jpeg")
background = pygame.transform.scale(background, (600, 600))
background_rect = background.get_rect()
background_rect.midtop = (WINDOW_WIDTH//2, 40)

# Define a draggable object
obj_color = (255, 0, 0)
obj_rect = pygame.Rect(100, 200, 50, 50)

dragging = False
offset_x = 0
offset_y = 0

while True:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            sys.exit()

        elif event.type == pygame.MOUSEBUTTONDOWN:
            if obj_rect.collidepoint(event.pos):
                dragging = True
                offset_x = obj_rect.x - event.pos[0]
                offset_y = obj_rect.y - event.pos[1]

        elif event.type == pygame.MOUSEBUTTONUP:
            dragging = False

        elif event.type == pygame.MOUSEMOTION:
            if dragging:
                obj_rect.x = event.pos[0] + offset_x
                obj_rect.y = event.pos[1] + offset_y

    screen.fill((0, 0, 0))  # or blit background
    screen.blit(background, background_rect)
    # pygame.draw.rect(screen, obj_color, obj_rect)
    
    mouse_x, mouse_y = pygame.mouse.get_pos()
    screen.blit(cursor_img, (mouse_x, mouse_y))

    item_rect = pygame.Rect(WINDOW_WIDTH//2, WINDOW_HEIGHT//2, 200, 200)
    
    if item_rect.collidepoint(mouse_x, mouse_y):
        hover_text_surface = font.render("Move to...", False, (255, 255, 255))
        screen.blit(hover_text_surface, (mouse_x, mouse_y + 40))
    
    pygame.display.flip()
    clock.tick(60)