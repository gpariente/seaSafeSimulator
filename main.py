import pygame
import sys
import math

# Import your custom modules
from simulator import scenario_map
from simulator.ship import Ship
from simulator.state import State
from simulator.position import Position
from simulator.action import Action
from algorithm.algorithm import ColregsAlgorithm

pygame.init()

# Screen and color definitions
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

# Conversions
METERS_PER_NM = 1852.0
SECONDS_PER_HOUR = 3600.0

# Each discrete timestep in real seconds
TIME_STEP_SECONDS = 1.0

# Images / assets
logo_image = pygame.image.load("images/logo.png").convert_alpha()
logo_w, logo_h = logo_image.get_width(), logo_image.get_height()
logo_image = pygame.transform.scale(logo_image, (logo_w * 2, logo_h * 2))

sea_bg = pygame.image.load("images/sea_background.png").convert()
sea_bg = pygame.transform.scale(sea_bg, (WIDTH, HEIGHT))
bg_scroll_speed = 0.05


class InputBox:
    """Simple text input widget."""
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
        # Draw border
        pygame.draw.rect(screen, DARK_BLUE if self.active else BLACK, self.rect, 2)

    def get_text(self):
        return self.text


class Button:
    """Simple button with callback."""
    def __init__(self, text, x, y, width, height, callback):
        self.text = text
        self.rect = pygame.Rect(x, y, width, height)
        self.callback = callback
        self.base_color = (0, 76, 153)   # Darkish blue
        self.hover_color = (51, 153, 255)
        self.border_color = (255, 255, 255)
        self.text_color = (255, 255, 255)
        self.hover_text_color = (0, 76, 153)

    def draw(self, screen):
        mouse_pos = pygame.mouse.get_pos()
        is_hovered = self.rect.collidepoint(mouse_pos)
        color = self.hover_color if is_hovered else self.base_color

        pygame.draw.rect(screen, color, self.rect, border_radius=15)
        pygame.draw.rect(screen, self.border_color, self.rect, width=3, border_radius=15)

        text_surface = BUTTON_FONT.render(self.text, True,
                        self.hover_text_color if is_hovered else self.text_color)
        text_rect = text_surface.get_rect(center=self.rect.center)
        screen.blit(text_surface, text_rect)

    def check_click(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1 and self.rect.collidepoint(event.pos):
                self.callback()


class ScenarioSimulation:
    """
    Handles the main simulator loop for collisions, time-stepping, and rendering.
    """
    def __init__(self, map_size_nm, horizon_nm, safety_zone_m,
                 ship_width_m, ship_length_m, max_speed_knots, ships_data):

        # Map parameters
        self.map = scenario_map.Map(map_size_nm)
        self.horizon_nm = horizon_nm
        self.safety_zone_m = safety_zone_m
        self.ship_width_m = ship_width_m
        self.ship_length_m = ship_length_m
        self.max_speed_knots = max_speed_knots

        # Create ships from user-defined source/dest data
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
        self.scenario_ended = False

        # Horizon steps => how many 30s steps to look forward
        if self.max_speed_knots > 0:
            steps_per_hour = 3600 / TIME_STEP_SECONDS
            self.horizon_steps = int(horizon_nm * steps_per_hour / max_speed_knots)
        else:
            self.horizon_steps = 0

        # Our COLREGS-based collision avoidance algorithm
        self.search_algorithm = ColregsAlgorithm()

    def step(self, external_actions=None):
        """
        Called each game loop tick:
         1) Apply external user/AI actions
         2) Run collision detection & avoidance
         3) Advance the simulation time by TIME_STEP_SECONDS
         4) Draw or track statuses
        """
        if external_actions is None:
            external_actions = []

        # 1) Apply external actions (e.g., manual controls)
        for action in external_actions:
            if 0 <= action.shipId < len(self.state.ships):
                ship = self.state.ships[action.shipId]
                if abs(action.headingChange) > 1e-6:
                    ship.change_heading(action.headingChange)
                if abs(action.speedChange) > 1e-6:
                    ship.change_speed(action.speedChange)

        # 2) Algorithm: collision detection + (possibly) avoidance or revert
        safety_zone_nm = self.safety_zone_m / METERS_PER_NM
        statuses, auto_actions = self.search_algorithm.step(
            self.state,
            horizon_steps=self.horizon_steps,
            safety_zone_nm=safety_zone_nm,
            horizon_nm=self.horizon_nm
        )

        # Apply the algorithm's recommended actions
        for action in auto_actions:
            if 0 <= action.shipId < len(self.state.ships):
                ship = self.state.ships[action.shipId]
                if abs(action.headingChange) > 1e-6:
                    ship.change_heading(action.headingChange)
                if abs(action.speedChange) > 1e-6:
                    ship.change_speed(action.speedChange)

        # Update each ship's status
        for i, status in enumerate(statuses):
            self.state.ships[i].set_status(status)

        # 3) Advance simulation time
        self.state.increment_time_step()
        self.state.update_ships(delta_seconds=TIME_STEP_SECONDS)

        # Check if scenario ended (all ships at destinations)
        if not self.scenario_ended and self.state.isGoalState():
            self.scenario_ended = True

        return statuses, self.scenario_ended

    @property
    def time_step(self):
        return self.state.time_step

    def draw_ships(self, ship_statuses):
        """
        Draw each ship:
         - Safety zone circle (color-coded by status)
         - A small black circle for the ship
         - A short line showing the heading
        """
        safety_zone_px = int((self.safety_zone_m / METERS_PER_NM) * self.map.pixel_per_nm)

        for idx, ship in enumerate(self.state.ships):
            # Convert ship NM coordinates to screen pixels
            ship_px_x = int(ship.cx_nm * self.map.pixel_per_nm)
            ship_px_y = int(ship.cy_nm * self.map.pixel_per_nm)

            # Pick color by status
            status_color_map = {"Green": GREEN, "Orange": ORANGE, "Red": RED}
            color = status_color_map.get(ship.status, GREEN)

            # Draw the safety zone circle
            pygame.draw.circle(SCREEN, color, (ship_px_x, ship_px_y), safety_zone_px, 2)

            # Draw the ship itself (small circle)
            pygame.draw.circle(SCREEN, BLACK, (ship_px_x, ship_px_y), 5)

            # Draw heading line
            heading_deg = ship.get_heading_from_direction()
            heading_rad = math.radians(heading_deg)
            line_len = 15
            tip_x = ship_px_x + line_len * math.cos(heading_rad)
            tip_y = ship_px_y + line_len * math.sin(heading_rad)
            pygame.draw.line(SCREEN, BLACK, (ship_px_x, ship_px_y), (tip_x, tip_y), 2)


def main_menu():
    """
    Main menu screen with buttons: New Scenario, Load, Exit
    """
    def new_scenario_callback():
        new_scenario()

    button_width, button_height = 300, 60
    button_spacing = 20
    button_start_y = HEIGHT // 2 - (button_height * 1.5 + button_spacing)

    buttons = [
        Button("New Scenario", WIDTH // 2 - button_width // 2, button_start_y,
               button_width, button_height, new_scenario_callback),
        Button("Load Scenario", WIDTH // 2 - button_width // 2,
               button_start_y + button_height + button_spacing,
               button_width, button_height, lambda: print("Load Scenario")),
        Button("Exit", WIDTH // 2 - button_width // 2,
               button_start_y + 2 * (button_height + button_spacing),
               button_width, button_height, lambda: pygame.quit()),
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

        # Move the background slightly
        bg_offset_x = (bg_offset_x + bg_scroll_speed) % WIDTH
        SCREEN.blit(sea_bg, (-bg_offset_x, 0))
        SCREEN.blit(sea_bg, (-bg_offset_x + WIDTH, 0))

        # Draw the larger logo
        logo_rect = logo_image.get_rect(center=(WIDTH // 2, HEIGHT // 4))
        SCREEN.blit(logo_image, logo_rect)

        for button in buttons:
            button.draw(SCREEN)

        pygame.display.flip()


def new_scenario():
    """
    Screen for defining a new scenario: map size, horizon, safety zone, ships' positions, etc.
    """
    default_values = {
        "map_size": "3",
        "num_ships": "2",
        "horizon": "5.0",
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

    # Dynamically update source/dest input boxes
    def update_ship_inputs(num_ships):
        nonlocal source_dest_boxes
        source_dest_boxes = []
        for i in range(min(num_ships, 8)):
            # Example default positions: first ship from (0,0) to (3,3)
            # second from (3,3) to (0,0), etc.
            source_box = InputBox(250, 500 + i * 60, 150, 30,
                                  "0,0" if i == 0 else "3,3")
            dest_box = InputBox(600, 500 + i * 60, 150, 30,
                                "3,3" if i == 0 else "0,0")
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
            "Map Size (Nautical Miles):",
            "Number of Ships:",
            "Horizon Distance (NM):",
            "Safety Zone Distance (m):",
            "Ship Width (m):",
            "Ship Length (m):",
            "Max Speed (knots):"
        ]

        # Draw each label + input box
        for i, label in enumerate(labels):
            label_surface = INPUT_FONT.render(label, True, BLACK)
            SCREEN.blit(label_surface, (150, 100 + i * 50))
            input_boxes[list(input_boxes.keys())[i]].draw(SCREEN)

        # Draw source/dest for each ship
        for i, (src_box, dest_box) in enumerate(source_dest_boxes):
            source_label = INPUT_FONT.render(f"Ship {i + 1} Source (NM,NM):", True, BLACK)
            dest_label = INPUT_FONT.render("Destination (NM,NM):", True, BLACK)
            SCREEN.blit(source_label, (150, 500 + i * 60 - 20))
            SCREEN.blit(dest_label, (500, 500 + i * 60 - 20))
            src_box.draw(SCREEN)
            dest_box.draw(SCREEN)

        # Draw submit button
        submit_button.draw(SCREEN)

        # Event handling
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                pygame.quit()
                sys.exit()

            # Update text in each input box
            for box in input_boxes.values():
                box.handle_event(event)

            for src_box, dest_box in source_dest_boxes:
                src_box.handle_event(event)
                dest_box.handle_event(event)

            submit_button.check_click(event)

        # If user changes "num_ships" text
        num_ships_text = input_boxes["num_ships"].get_text()
        num_ships = int(num_ships_text) if num_ships_text.isdigit() else 0
        if num_ships != current_num_ships:
            current_num_ships = num_ships
            update_ship_inputs(current_num_ships)

        pygame.display.flip()


def start_scenario(inputs):
    """
    Called after user inputs scenario parameters:
     - Creates a ScenarioSimulation instance and runs its loop
    """
    map_size_nm = float(inputs.get("map_size", "100") or "100")
    horizon_nm = float(inputs.get("horizon", "2") or "2")
    safety_zone_m = float(inputs.get("safety_zone", "50") or "50")
    ship_width_m = float(inputs.get("ship_width", "20") or "20")
    ship_length_m = float(inputs.get("ship_length", "200") or "200")
    max_speed_knots = float(inputs.get("max_speed", "10") or "10")

    ships_data = inputs.get("source_dest", [])

    # Create the scenario simulation
    simulation = ScenarioSimulation(
        map_size_nm, horizon_nm, safety_zone_m,
        ship_width_m, ship_length_m, max_speed_knots, ships_data
    )

    running = True
    clock = pygame.time.Clock()

    while running:
        clock.tick(60)  # 60 FPS

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                pygame.quit()
                sys.exit()

        # We call step() each frame. If you wanted external actions, 
        # you'd pass them here.
        ship_status, done = simulation.step(external_actions=[])

        # Clear background
        SCREEN.fill(BLUE)

        # Show time step
        time_surface = INPUT_FONT.render(f"Time Step: {simulation.time_step}", True, WHITE)
        SCREEN.blit(time_surface, (10, 10))

        # Show scenario ended or running
        if done:
            ended_surface = INPUT_FONT.render("Scenario ended", True, WHITE)
            SCREEN.blit(ended_surface, (10, 30))
        else:
            running_surface = INPUT_FONT.render("Scenario Running...", True, WHITE)
            SCREEN.blit(running_surface, (10, 30))

        # Draw ships, statuses, etc.
        simulation.draw_ships(ship_status)

        pygame.display.flip()


if __name__ == "__main__":
    main_menu()
