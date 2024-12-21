import pygame
import sys
import math
from simulator import scenario_map
from simulator.ship import Ship
from simulator.state import State
from simulator.position import Position
from simulator.action import Action
from algorithm.algorithm import SearchAlgorithm

pygame.init()

WIDTH, HEIGHT = 1000, 1000
SCREEN = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("SeaSafe - Simulator")

WHITE = (255, 255, 255)
BLUE = (135, 206, 250)
GRAY = (200, 200, 200)
BLACK = (0, 0, 0)
DARK_BLUE = (0, 0, 128)
GREEN = (0, 255, 0)
ORANGE = (255, 165, 0)
RED = (255, 0, 0)

TITLE_FONT = pygame.font.Font(pygame.font.get_default_font(), 50)
BUTTON_FONT = pygame.font.Font(pygame.font.get_default_font(), 30)
INPUT_FONT = pygame.font.Font(pygame.font.get_default_font(), 20)

METERS_PER_NM = 1852.0
SECONDS_PER_HOUR = 3600.0

# Each time step in the simulation = 30 real-world seconds
TIME_STEP_SECONDS = 1

# Images
logo_image = pygame.image.load("images/logo.png").convert_alpha()
# Scale the logo bigger, e.g. double size:
logo_w, logo_h = logo_image.get_width(), logo_image.get_height()
logo_image = pygame.transform.scale(logo_image, (logo_w * 2, logo_h * 2))

sea_bg = pygame.image.load("images/sea_background.png").convert()
sea_bg = pygame.transform.scale(sea_bg, (WIDTH, HEIGHT))
# Slower background movement
bg_scroll_speed = 0.05

ship_sprite = pygame.image.load("images/ship_sprite.png").convert_alpha()
# Scale sprite based on ship size. Since we don't know exact scale, just keep fixed for now.
# We'll dynamically scale in draw_ships based on ship width and length.
# For a default sprite size, keep as a base:
base_ship_sprite = ship_sprite

class InputBox:
    def __init__(self, x, y, w, h, text=""):
        self.rect = pygame.Rect(x, y, w, h)
        self.color = GRAY
        self.text = text
        self.font = INPUT_FONT
        self.txt_surface = self.font.render(text, True, BLACK)
        self.active = False

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            self.active = self.rect.collidepoint(event.pos)
        if event.type == pygame.KEYDOWN and self.active:
            if event.key == pygame.K_RETURN:
                self.active = False
            elif event.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
            else:
                self.text += event.unicode
            self.txt_surface = self.font.render(self.text, True, BLACK)

    def draw(self, screen):
        pygame.draw.rect(screen, self.color, self.rect, 0)
        screen.blit(self.txt_surface, (self.rect.x + 5, self.rect.y + 5))
        pygame.draw.rect(screen, DARK_BLUE if self.active else BLACK, self.rect, 2)

    def get_text(self):
        return self.text

class Button:
    def __init__(self, text, x, y, width, height, callback):
        self.text = text
        self.rect = pygame.Rect(x, y, width, height)
        self.callback = callback
        self.base_color = (0, 76, 153)  # Deep blue for water theme
        self.hover_color = (51, 153, 255)  # Light blue
        self.border_color = (255, 255, 255)  # White border
        self.text_color = (255, 255, 255)
        self.hover_text_color = (0, 76, 153)

    def draw(self, screen):
        mouse_pos = pygame.mouse.get_pos()
        is_hovered = self.rect.collidepoint(mouse_pos)
        color = self.hover_color if is_hovered else self.base_color

        # Rounded rectangle (simulate rounded corners)
        pygame.draw.rect(screen, color, self.rect, border_radius=15)
        pygame.draw.rect(screen, self.border_color, self.rect, width=3, border_radius=15)

        # Render text
        text_surface = BUTTON_FONT.render(self.text, True, self.hover_text_color if is_hovered else self.text_color)
        text_rect = text_surface.get_rect(center=self.rect.center)
        screen.blit(text_surface, text_rect)

    def check_click(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1 and self.rect.collidepoint(event.pos):
                self.callback()

class ScenarioSimulation:
    def __init__(self, map_size_nm, horizon_nm, safety_zone_m, ship_width_m, ship_length_m, max_speed_knots, ships_data):
        self.map = scenario_map.Map(map_size_nm)
        self.horizon_nm = horizon_nm
        self.safety_zone_m = safety_zone_m
        self.ship_width_m = ship_width_m
        self.ship_length_m = ship_length_m
        self.max_speed_knots = max_speed_knots

        ships = []
        for i, sd in enumerate(ships_data):
            try:
                sx_nm, sy_nm = map(float, sd["source"].split(","))
                dx_nm, dy_nm = map(float, sd["destination"].split(","))
            except:
                continue
            
            source_pos = Position(sx_nm, sy_nm)
            dest_pos = Position(dx_nm, dy_nm)

            ship = Ship(
                ship_id=i,
                source_nm_pos=source_pos,
                dest_nm_pos=dest_pos,
                width_m=self.ship_width_m,
                length_m=self.ship_length_m,
                max_speed_knots=self.max_speed_knots,
                role="Unknown"
            )
            ships.append(ship)

        self.state = State(time_step=0, ships=ships)

        if max_speed_knots > 0:
            self.horizon_steps = int((horizon_nm * SECONDS_PER_HOUR) / max_speed_knots)
        else:
            self.horizon_steps = 0

        self.scenario_ended = False
        self.search_algorithm = SearchAlgorithm()

    def update(self):
        self.state.increment_time_step()
        # Update ships with TIME_STEP_SECONDS = 30 sec
        self.state.update_ships(delta_seconds=TIME_STEP_SECONDS)

        if not self.scenario_ended:
            if self.state.isGoalState():
                self.scenario_ended = True

        safety_zone_nm = self.safety_zone_m / METERS_PER_NM
        ship_status = self.search_algorithm.detect_future_collision(
            self.state,
            self.horizon_steps,
            safety_zone_nm
        )

        for i, status in enumerate(ship_status):
            self.state.ships[i].set_status(status)

        return ship_status

    @property
    def time_step(self):
        return self.state.time_step

    def draw_ships(self, ship_status):
        global base_ship_sprite
        safety_zone_px = int((self.safety_zone_m / METERS_PER_NM) * self.map.pixel_per_nm)

        for idx, ship in enumerate(self.state.ships):
            ship_px_x = int(ship.cx_nm * self.map.pixel_per_nm)
            ship_px_y = int(ship.cy_nm * self.map.pixel_per_nm)
            
            # Convert ship width/length in meters to pixels:
            width_px = self.map.meters_to_pixels(ship.width_m)
            length_px = self.map.meters_to_pixels(ship.length_m)

            # Scale ship sprite according to ship size
            # If ship sprite originally 50x50, scale it so that length_px matches sprite length
            # Assume length corresponds to the major dimension (like the ship's heading direction)
            # We'll scale so that the sprite's largest dimension matches ship length in pixels
            # If the ship sprite is originally square, just scale both sides accordingly
            if length_px > 0 and width_px > 0:
                # Keep aspect ratio, sprite originally 50x50
                # scale_x = width_px/50, scale_y = length_px/50, pick min or max?
                # If we assume length is along the ship's direction, use length_px as major dimension:
                # let's match length_px to 50 pixels:
                scale_x = width_px / 50.0
                scale_y = length_px / 50.0
                scaled_sprite = pygame.transform.smoothscale(base_ship_sprite, (int(50*scale_x), int(50*scale_y)))
            else:
                scaled_sprite = base_ship_sprite

            status_color_map = {
                "Green": GREEN,
                "Orange": ORANGE,
                "Red": RED
            }
            color = status_color_map[ship_status[idx]]
            pygame.draw.circle(SCREEN, color, (ship_px_x, ship_px_y), safety_zone_px, 2)

            heading = ship.get_heading_from_direction()
            # If direction seems wrong, try removing the minus sign:
            rotated_ship = pygame.transform.rotate(scaled_sprite, heading)

            ship_rect = rotated_ship.get_rect(center=(ship_px_x, ship_px_y))
            SCREEN.blit(rotated_ship, ship_rect)

            # Draw scenario/role label if Orange
            if ship_status[idx] == "Orange" and ship.scenario is not None and ship.role is not None:
                label_font = INPUT_FONT
                label_text = f"Scenario: {ship.scenario}, Role: {ship.role}"
                label_surface = label_font.render(label_text, True, WHITE)
                # Place label above ship: use ship_rect to position
                label_x = ship_px_x - label_surface.get_width()//2
                label_y = ship_px_y - (ship_rect.height//2) - label_surface.get_height() - 5
                pygame.draw.rect(SCREEN, BLACK, (label_x - 2, label_y - 2, label_surface.get_width() + 4, label_surface.get_height() + 4))
                SCREEN.blit(label_surface, (label_x, label_y))

def main_menu():
    def new_scenario_callback():
        new_scenario()

    button_width, button_height = 300, 60
    button_spacing = 20
    button_start_y = HEIGHT // 2 - (button_height * 1.5 + button_spacing)

    buttons = [
        Button("New Scenario", WIDTH // 2 - button_width // 2, button_start_y, button_width, button_height, new_scenario_callback),
        Button("Load Scenario", WIDTH // 2 - button_width // 2, button_start_y + button_height + button_spacing, button_width, button_height, lambda: print("Load Scenario")),
        Button("Exit", WIDTH // 2 - button_width // 2, button_start_y + 2 * (button_height + button_spacing), button_width, button_height, lambda: pygame.quit()),
    ]

    running = True
    bg_offset_x = 0
    global bg_scroll_speed

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                pygame.quit()
                sys.exit()

            for button in buttons:
                button.check_click(event)

        # Animate background
        bg_offset_x = (bg_offset_x + bg_scroll_speed) % WIDTH
        SCREEN.blit(sea_bg, (-bg_offset_x, 0))
        SCREEN.blit(sea_bg, (-bg_offset_x + WIDTH, 0))

        # Draw larger logo
        logo_rect = logo_image.get_rect(center=(WIDTH // 2, HEIGHT // 4))
        SCREEN.blit(logo_image, logo_rect)

        for button in buttons:
            button.draw(SCREEN)

        pygame.display.flip()

def new_scenario():
    default_values = {
        "map_size": "3",
        "num_ships": "2",
        "horizon": "0.5",
        "safety_zone": "200",
        "ship_width": "200",
        "ship_length": "200",
        "max_speed": "20",
    }

    input_boxes = {
        "map_size": InputBox(400, 100, 200, 30, default_values["map_size"]),
        "num_ships": InputBox(400, 150, 200, 30, default_values["num_ships"]),
        "horizon": InputBox(400, 200, 200, 30, default_values["horizon"]),
        "safety_zone": InputBox(400, 250, 200, 30, default_values["safety_zone"]),
        "ship_width": InputBox(400, 300, 200, 30, default_values["ship_width"]),
        "ship_length": InputBox(400, 350, 200, 30, default_values["ship_length"]),
        "max_speed": InputBox(400, 400, 200, 30, default_values["max_speed"]),
    }

    source_dest_boxes = []
    current_num_ships = int(default_values["num_ships"])

    def update_ship_inputs(num_ships):
        nonlocal source_dest_boxes
        source_dest_boxes = []
        for i in range(min(num_ships, 8)):
            source_box = InputBox(250, 500 + i * 60, 150, 30, "0,0" if i == 0 else "3,3")
            dest_box = InputBox(600, 500 + i * 60, 150, 30, "3,3" if i == 0 else "0,0")
            source_dest_boxes.append((source_box, dest_box))

    update_ship_inputs(current_num_ships)

    def collect_inputs():
        inputs = {key: box.get_text() for key, box in input_boxes.items()}
        inputs["source_dest"] = [
            {"source": src.get_text(), "destination": dest.get_text()}
            for src, dest in source_dest_boxes
            if src.get_text() and dest.get_text()
        ]
        start_scenario(inputs)

    submit_button = Button("Start Scenario", 400, 900, 200, 50, collect_inputs)

    running = True
    while running:
        SCREEN.fill(WHITE)

        labels = [
            "Map Size (Nautical Miles):", "Number of Ships:", "Horizon Distance (NM):",
            "Safety Zone Distance (m):", "Ship Width (m):", "Ship Length (m):", "Max Speed (knots):"
        ]
        for i, label in enumerate(labels):
            label_surface = INPUT_FONT.render(label, True, BLACK)
            SCREEN.blit(label_surface, (150, 100 + i * 50))
            input_boxes[list(input_boxes.keys())[i]].draw(SCREEN)

        for i, (src_box, dest_box) in enumerate(source_dest_boxes):
            source_label = INPUT_FONT.render(f"Ship {i + 1} Source (NM,NM):", True, BLACK)
            dest_label = INPUT_FONT.render("Destination (NM,NM):", True, BLACK)
            SCREEN.blit(source_label, (150, 500 + i * 60 - 20))
            SCREEN.blit(dest_label, (500, 500 + i * 60 - 20))
            src_box.draw(SCREEN)
            dest_box.draw(SCREEN)

        submit_button.draw(SCREEN)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                pygame.quit()
                sys.exit()

            for box in input_boxes.values():
                box.handle_event(event)

            for src_box, dest_box in source_dest_boxes:
                src_box.handle_event(event)
                dest_box.handle_event(event)

            submit_button.check_click(event)

        num_ships_text = input_boxes["num_ships"].get_text()
        num_ships = int(num_ships_text) if num_ships_text.isdigit() else 0

        if num_ships != current_num_ships:
            current_num_ships = num_ships
            update_ship_inputs(current_num_ships)

        pygame.display.flip()

def start_scenario(inputs):
    map_size_nm = float(inputs.get("map_size", "100") or "100")  
    horizon_nm = float(inputs.get("horizon", "2") or "2") 
    safety_zone_m = float(inputs.get("safety_zone", "50") or "50")
    ship_width_m = float(inputs.get("ship_width", "20") or "20")
    ship_length_m = float(inputs.get("ship_length", "200") or "200")
    max_speed_knots = float(inputs.get("max_speed", "10") or "10")

    ships_data = inputs.get("source_dest", [])

    simulation = ScenarioSimulation(map_size_nm, horizon_nm, safety_zone_m, ship_width_m, ship_length_m, max_speed_knots, ships_data)

    running = True
    clock = pygame.time.Clock()

    while running:
        clock.tick(60)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                pygame.quit()
                sys.exit()

        ship_status = simulation.update()

        SCREEN.fill(BLUE)
        time_surface = INPUT_FONT.render(f"Time Step: {simulation.time_step}", True, WHITE)
        SCREEN.blit(time_surface, (10,10))

        if simulation.scenario_ended:
            ended_surface = INPUT_FONT.render("Scenario ended", True, WHITE)
            SCREEN.blit(ended_surface, (10,30))
        else:
            running_surface = INPUT_FONT.render("Scenario Running...", True, WHITE)
            SCREEN.blit(running_surface, (10,30))

        simulation.draw_ships(ship_status)
        pygame.display.flip()

if __name__ == "__main__":
    main_menu()
