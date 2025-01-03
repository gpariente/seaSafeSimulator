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

# =============================
# 1) Declare global WIDTH/HEIGHT at top-level,
#    with some default. We'll set them properly after we get the display info.
DEFAULT_WIDTH, DEFAULT_HEIGHT = 1000, 1000  # default fallback

# 2) After we get the display info, we'll override these with a fraction of user's screen
infoObject = pygame.display.Info()
# For example, let's do 80% of user’s screen resolution
WIDTH = int(infoObject.current_w * 0.4)
HEIGHT = int(infoObject.current_h * 0.7)

# We'll create a resizable window
SCREEN = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)
pygame.display.set_caption("SeaSafe - Simulator (Adjustable)")

# Define Colors
WHITE = (255, 255, 255)
BLUE = (135, 206, 250)
GRAY = (200, 200, 200)
BLACK = (0, 0, 0)
DARK_BLUE = (0, 0, 128)
GREEN = (0, 255, 0)
ORANGE = (255, 165, 0)
RED = (255, 0, 0)

# Define Fonts (sizes will be dynamic based on window size)
def get_dynamic_font(size_ratio):
    return pygame.font.Font(pygame.font.get_default_font(), int(min(WIDTH, HEIGHT) * size_ratio))

TITLE_FONT = get_dynamic_font(0.05)    # 5% of min dimension
BUTTON_FONT = get_dynamic_font(0.03)   # 3% of min dimension
INPUT_FONT = get_dynamic_font(0.02)    # 2% of min dimension

METERS_PER_NM = 1852.0
SECONDS_PER_HOUR = 3600.0

PHYSICS_STEP = 15.0          # each collision/logic step = 30s sim time
REAL_SECONDS_PER_STEP = 0.5  # after 2 real seconds, we do a 30s step

# Initialize sea_bg and logo_image
sea_bg = None
logo_image = None

# Load & scale the images according to current WIDTH, HEIGHT
try:
    logo_image_raw = pygame.image.load("images/logo.png").convert_alpha()
except pygame.error as e:
    print(f"Unable to load logo.png: {e}")
    sys.exit()

try:
    sea_bg_raw = pygame.image.load("images/sea_background.png").convert()
except pygame.error as e:
    print(f"Unable to load sea_background.png: {e}")
    sys.exit()

bg_scroll_speed = 0.05

def scale_images_to_window():
    """
    Re-scale background and logo to fit the current (WIDTH, HEIGHT).
    Also update fonts based on window size.
    """
    global logo_image, sea_bg, WIDTH, HEIGHT, TITLE_FONT, BUTTON_FONT, INPUT_FONT

    # Update fonts
    TITLE_FONT = get_dynamic_font(0.05)    # 5% of min dimension
    BUTTON_FONT = get_dynamic_font(0.03)   # 3% of min dimension
    INPUT_FONT = get_dynamic_font(0.02)    # 2% of min dimension

    # Background
    sea_bg = pygame.transform.scale(sea_bg_raw, (WIDTH, HEIGHT))

    # Logo
    logo_rect = logo_image_raw.get_rect()
    scale_factor = 0.3  # 30% of window width
    new_w = int(WIDTH * scale_factor)
    aspect = logo_rect.height / logo_rect.width
    new_h = int(new_w * aspect)
    logo_image = pygame.transform.smoothscale(logo_image_raw, (new_w, new_h))

# Immediately scale images to our new initial WIDTH & HEIGHT
scale_images_to_window()

class InputBox:
    """Simple text input widget."""
    def __init__(self, rel_x, rel_y, rel_w, rel_h, text=""):
        """
        Positions and sizes are relative (0 to 1) based on current window size.
        """
        self.rel_x = rel_x
        self.rel_y = rel_y
        self.rel_w = rel_w
        self.rel_h = rel_h
        self.text = text
        self.color = GRAY
        self.font = INPUT_FONT
        self.txt_surface = self.font.render(text, True, BLACK)
        self.active = False
        self.update_rect()

    def update_rect(self):
        """Update the actual rect based on relative positions and current WIDTH and HEIGHT."""
        self.rect = pygame.Rect(
            int(self.rel_x * WIDTH),
            int(self.rel_y * HEIGHT),
            int(self.rel_w * WIDTH),
            int(self.rel_h * HEIGHT)
        )

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            self.active = self.rect.collidepoint(event.pos)
        if event.type == pygame.KEYDOWN and self.active:
            if event.key == pygame.K_RETURN:
                self.active = False
            elif event.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
            else:
                # Limit input length if necessary
                self.text += event.unicode
            self.txt_surface = self.font.render(self.text, True, BLACK)

    def draw(self, screen):
        # Update rect in case window size changed
        self.update_rect()
        pygame.draw.rect(screen, self.color, self.rect, 0)
        # Adjust text position based on current rect
        screen.blit(self.txt_surface, (self.rect.x + 5, self.rect.y + (self.rect.height - self.txt_surface.get_height()) // 2))
        pygame.draw.rect(screen, DARK_BLUE if self.active else BLACK, self.rect, 2)

    def get_text(self):
        return self.text

    def update_font(self):
        """Update the font size based on current window size."""
        self.font = INPUT_FONT
        self.txt_surface = self.font.render(self.text, True, BLACK)

class Button:
    """Simple button with callback."""
    def __init__(self, text, rel_x, rel_y, rel_width, rel_height, callback):
        """
        Positions and sizes are relative (0 to 1) based on current window size.
        """
        self.text = text
        self.rel_x = rel_x
        self.rel_y = rel_y
        self.rel_width = rel_width
        self.rel_height = rel_height
        self.callback = callback
        self.base_color = (0, 76, 153)
        self.hover_color = (51, 153, 255)
        self.border_color = (255, 255, 255)
        self.text_color = (255, 255, 255)
        self.hover_text_color = (0, 76, 153)
        self.font = BUTTON_FONT
        self.update_rect()

    def update_rect(self):
        """Update the actual rect based on relative positions and current WIDTH and HEIGHT."""
        self.rect = pygame.Rect(
            int(self.rel_x * WIDTH),
            int(self.rel_y * HEIGHT),
            int(self.rel_width * WIDTH),
            int(self.rel_height * HEIGHT)
        )

    def draw(self, screen):
        # Update rect and font in case window size changed
        self.update_rect()
        self.update_font()

        mouse_pos = pygame.mouse.get_pos()
        is_hovered = self.rect.collidepoint(mouse_pos)
        color = self.hover_color if is_hovered else self.base_color

        pygame.draw.rect(screen, color, self.rect, border_radius=15)
        pygame.draw.rect(screen, self.border_color, self.rect, width=3, border_radius=15)

        text_surface = self.font.render(
            self.text, True,
            self.hover_text_color if is_hovered else self.text_color
        )
        text_rect = text_surface.get_rect(center=self.rect.center)
        screen.blit(text_surface, text_rect)

    def check_click(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1 and self.rect.collidepoint(event.pos):
                self.callback()

    def update_font(self):
        """Update the font size based on current window size."""
        self.font = BUTTON_FONT

class ScenarioSimulation:
    """
    Handles the main simulator loop for collisions, time-stepping, and rendering.
    """
    def __init__(self, map_size_nm, horizon_nm, safety_zone_m,
                 ship_width_m, ship_length_m, max_speed_knots, ships_data,
                 window_width, window_height, collision_algorithm=None):

        self.map = scenario_map.Map(map_size_nm, window_width, window_height)
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
        self.scenario_ended = False

        if self.max_speed_knots > 0:
            steps_per_hour = 3600.0 / PHYSICS_STEP
            self.horizon_steps = int(horizon_nm * steps_per_hour / max_speed_knots)
        else:
            self.horizon_steps = 0

        if collision_algorithm is None:
            self.search_algorithm = ColregsAlgorithm()  # default
        else:
            self.search_algorithm = collision_algorithm  # user-supplied

    def physics_step(self):
        # Update ships based on prev step heading/speed.
        self.state.update_ships(delta_seconds=PHYSICS_STEP)
        # Collision detection
        safety_zone_nm = self.safety_zone_m / METERS_PER_NM
        statuses, auto_actions = self.search_algorithm.step(
            self.state,
            horizon_steps=self.horizon_steps,
            safety_zone_nm=safety_zone_nm,
            horizon_nm=self.horizon_nm
        )
        # Apply avoidance
        for action in auto_actions:
            if 0 <= action.shipId < len(self.state.ships):
                shp = self.state.ships[action.shipId]
                if abs(action.headingChange) > 1e-6:
                    shp.change_heading(action.headingChange)
                if abs(action.speedChange) > 1e-6:
                    shp.change_speed(action.speedChange)

        for i, st in enumerate(statuses):
            self.state.ships[i].set_status(st)

        self.state.increment_time_step()
        

        if not self.scenario_ended and self.state.isGoalState():
            self.scenario_ended = True

    @property
    def time_step(self):
        return self.state.time_step

    def draw_ships(self):
        # Determine map area
        map_rect = self.map.get_map_rect()
        safety_zone_px_x = int((self.safety_zone_m / METERS_PER_NM) * self.map.pixel_per_nm_x)
        safety_zone_px_y = int((self.safety_zone_m / METERS_PER_NM) * self.map.pixel_per_nm_y)

        for idx, ship in enumerate(self.state.ships):
            ship_px_pos = self.map.nm_position_to_pixels(ship.cx_nm, ship.cy_nm)

            status_color_map = {"Green": GREEN, "Orange": ORANGE, "Red": RED}
            color = status_color_map.get(ship.status, GREEN)
            # Draw safety zone ellipse (stretched if necessary)
            pygame.draw.ellipse(SCREEN, color, 
                                (int(ship_px_pos.x - safety_zone_px_x), 
                                int(ship_px_pos.y - safety_zone_px_y),
                                2 * safety_zone_px_x, 
                                2 * safety_zone_px_y), 2)
            # Draw ship position
            pygame.draw.circle(SCREEN, BLACK, (int(ship_px_pos.x), int(ship_px_pos.y)), 5)

            # Draw heading line
            heading_deg = ship.get_heading_from_direction()
            heading_rad = math.radians(heading_deg)
            line_len_x = int(15 * math.cos(heading_rad))  # Adjust based on scaling if necessary
            line_len_y = int(15 * math.sin(heading_rad))
            tip_x = ship_px_pos.x + line_len_x
            tip_y = ship_px_pos.y + line_len_y
            pygame.draw.line(SCREEN, BLACK, (int(ship_px_pos.x), int(ship_px_pos.y)), (int(tip_x), int(tip_y)), 2)

            # If status is Orange or Red => show label with scenario/role
            if ship.status in ("Orange", "Red") and ship.scenario is not None and ship.role is not None:
                label_font = INPUT_FONT
                scenario_text = f"Scenario: {ship.scenario}"
                role_text = f"Role: {ship.role}"
                # heading_text = f"Heading: {int(heading_deg)}°"

                # Render them line by line
                scenario_surf = label_font.render(scenario_text, True, WHITE)
                role_surf = label_font.render(role_text, True, WHITE)
                # head_surf = label_font.render(heading_text, True, WHITE)

                # Calculate label position with offset to prevent overlapping
                label_x = int(ship_px_pos.x)
                label_y = int(ship_px_pos.y + 10 + idx * 20)  # Offset based on ship index

                # Draw background box
                max_width = max(scenario_surf.get_width(), role_surf.get_width())
                total_height = scenario_surf.get_height() + role_surf.get_height()
                box_rect = pygame.Rect(label_x, label_y, max_width + 6, total_height + 6)

                # Center the box horizontally around the ship
                box_rect.centerx = label_x
                # Adjust y position to prevent overlapping
                box_rect.y = label_y + idx * 20

                pygame.draw.rect(SCREEN, BLACK, box_rect)
                # Blit each line
                line_y = box_rect.y + 2
                SCREEN.blit(scenario_surf, (box_rect.x + 3, line_y))
                line_y += scenario_surf.get_height()
                SCREEN.blit(role_surf, (box_rect.x + 3, line_y))
                line_y += role_surf.get_height()
                # SCREEN.blit(head_surf, (box_rect.x + 3, line_y))


    def update_window_size(self, window_width, window_height):
        """
        Update the map scaling based on the new window size.
        
        :param window_width: New window width in pixels.
        :param window_height: New window height in pixels.
        """
        self.map.window_width = window_width
        self.map.window_height = window_height
        self.map.update_scaling()

def main_menu():
    """
    Main menu screen with buttons: New Scenario, Load, Exit
    """
    global WIDTH, HEIGHT, SCREEN, sea_bg, bg_scroll_speed, logo_image, logo_image_raw

    def new_scenario_callback():
        new_scenario()

    # Define button dimensions and positions relative to window size
    button_width_ratio, button_height_ratio = 0.3, 0.06  # 30% width, 6% height
    button_spacing_ratio = 0.02  # 2% spacing

    # Calculate button positions to avoid overlapping
    start_y = 0.4  # Starting y position for the first button

    buttons = [
        Button(
            "New Scenario",
            rel_x=0.5 - button_width_ratio / 2,
            rel_y=start_y,
            rel_width=button_width_ratio,
            rel_height=button_height_ratio,
            callback=new_scenario_callback
        ),
        Button(
            "Load Scenario",
            rel_x=0.5 - button_width_ratio / 2,
            rel_y=start_y + button_height_ratio + button_spacing_ratio,
            rel_width=button_width_ratio,
            rel_height=button_height_ratio,
            callback=lambda: print("Load Scenario")
        ),
        Button(
            "Exit",
            rel_x=0.5 - button_width_ratio / 2,
            rel_y=start_y + 2 * (button_height_ratio + button_spacing_ratio),
            rel_width=button_width_ratio,
            rel_height=button_height_ratio,
            callback=lambda: pygame.quit() or sys.exit()
        ),
    ]

    running = True
    bg_offset_x = 0

    while running:
        dt = 1 / 60.0  # Not that critical here, but let's define

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                pygame.quit()
                sys.exit()
            elif event.type == pygame.VIDEORESIZE:
                # User resized window => update WIDTH/HEIGHT + re-scale
                WIDTH, HEIGHT = event.w, event.h
                SCREEN = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)
                scale_images_to_window()
                # Update all buttons' positions and sizes
                for button in buttons:
                    button.update_rect()
                    button.update_font()
            else:
                for button in buttons:
                    button.check_click(event)

        bg_offset_x = (bg_offset_x + bg_scroll_speed * WIDTH * 0.001) % WIDTH  # Adjust scroll speed based on WIDTH

        # Draw background
        SCREEN.blit(sea_bg, (-bg_offset_x, 0))
        SCREEN.blit(sea_bg, (-bg_offset_x + WIDTH, 0))

        # Center the logo (e.g., top center)
        logo_rect_center = logo_image.get_rect(center=(WIDTH // 2, int(HEIGHT * 0.2)))
        SCREEN.blit(logo_image, logo_rect_center)

        for button in buttons:
            button.draw(SCREEN)

        pygame.display.flip()

def new_scenario():
    """
    Screen for defining a new scenario: map size, horizon, safety zone, ships' positions, etc.
    """
    global WIDTH, HEIGHT, SCREEN, sea_bg

    default_values = {
        "map_size": "3",
        "num_ships": "2",
        "horizon": "5.0",
        "safety_zone": "200",
        "ship_width": "200",
        "ship_length": "200",
        "max_speed": "20",
    }

    # Define input box relative positions and sizes
    input_boxes = {
        "map_size": InputBox(rel_x=0.5 - 0.1, rel_y=0.1, rel_w=0.2, rel_h=0.03, text=default_values["map_size"]),
        "num_ships": InputBox(rel_x=0.5 - 0.1, rel_y=0.15, rel_w=0.2, rel_h=0.03, text=default_values["num_ships"]),
        "horizon": InputBox(rel_x=0.5 - 0.1, rel_y=0.2, rel_w=0.2, rel_h=0.03, text=default_values["horizon"]),
        "safety_zone": InputBox(rel_x=0.5 - 0.1, rel_y=0.25, rel_w=0.2, rel_h=0.03, text=default_values["safety_zone"]),
        "ship_width": InputBox(rel_x=0.5 - 0.1, rel_y=0.3, rel_w=0.2, rel_h=0.03, text=default_values["ship_width"]),
        "ship_length": InputBox(rel_x=0.5 - 0.1, rel_y=0.35, rel_w=0.2, rel_h=0.03, text=default_values["ship_length"]),
        "max_speed": InputBox(rel_x=0.5 - 0.1, rel_y=0.4, rel_w=0.2, rel_h=0.03, text=default_values["max_speed"]),
    }

    source_dest_boxes = []
    current_num_ships = int(default_values["num_ships"])

    def update_ship_inputs(num_ships):
        nonlocal source_dest_boxes
        source_dest_boxes = []
        for i in range(min(num_ships, 8)):
            src_box = InputBox(
                rel_x=0.3 - 0.075,  # Adjusted to fit within window (centered around 0.3)
                rel_y=0.5 + i * 0.07,
                rel_w=0.15,
                rel_h=0.03,
                text="0,0" if i == 0 else "3,3"
            )
            dest_box = InputBox(
                rel_x=0.7 - 0.075,  # Adjusted to fit within window (centered around 0.7)
                rel_y=0.5 + i * 0.07,
                rel_w=0.15,
                rel_h=0.03,
                text="3,3" if i == 0 else "0,0"
            )
            source_dest_boxes.append((src_box, dest_box))

    update_ship_inputs(current_num_ships)

    def collect_inputs():
        inputs = {key: box.get_text() for key, box in input_boxes.items()}
        inputs["source_dest"] = [
            {"source": src.get_text(), "destination": dest.get_text()}
            for src, dest in source_dest_boxes
            if src.get_text() and dest.get_text()
        ]
        start_scenario(inputs)

    # Define submit button
    submit_button = Button(
        "Start Scenario",
        rel_x=0.5 - 0.1,  # Centered, width 20%
        rel_y=0.9,
        rel_width=0.2,
        rel_height=0.05,
        callback=collect_inputs
    )

    running = True
    while running:
        SCREEN.fill(WHITE)

        # Render labels
        labels = [
            "Map Size (Nautical Miles):",
            "Number of Ships:",
            "Horizon Distance (NM):",
            "Safety Zone Distance (m):",
            "Ship Width (m):",
            "Ship Length (m):",
            "Max Speed (knots):"
        ]

        label_positions = [
            (0.05, 0.1),
            (0.05, 0.15),
            (0.05, 0.2),
            (0.05, 0.25),
            (0.05, 0.3),
            (0.05, 0.35),
            (0.05, 0.4),
        ]

        for i, label in enumerate(labels):
            label_surface = INPUT_FONT.render(label, True, BLACK)
            label_pos = (int(WIDTH * label_positions[i][0]), int(HEIGHT * label_positions[i][1]))
            SCREEN.blit(label_surface, label_pos)
            input_boxes[list(input_boxes.keys())[i]].draw(SCREEN)

        # Render source and destination input boxes
        for i, (src_box, dest_box) in enumerate(source_dest_boxes):
            source_label = INPUT_FONT.render(f"Ship {i + 1} Source (NM,NM):", True, BLACK)
            dest_label = INPUT_FONT.render("Destination (NM,NM):", True, BLACK)
            SCREEN.blit(source_label, (int(WIDTH * 0.15), int(HEIGHT * (0.5 + i * 0.07 - 0.02))))
            SCREEN.blit(dest_label, (int(WIDTH * 0.55), int(HEIGHT * (0.5 + i * 0.07 - 0.02))))
            src_box.draw(SCREEN)
            dest_box.draw(SCREEN)

        # Draw submit button
        submit_button.draw(SCREEN)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                pygame.quit()
                sys.exit()
            elif event.type == pygame.VIDEORESIZE:
                # User resized => update WIDTH/HEIGHT
                WIDTH, HEIGHT = event.w, event.h
                SCREEN = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)
                scale_images_to_window()
                # Re-position input boxes
                for box in input_boxes.values():
                    box.update_rect()
                    box.update_font()
                for src_box, dest_box in source_dest_boxes:
                    src_box.update_rect()
                    src_box.update_font()
                    dest_box.update_rect()
                    dest_box.update_font()
                submit_button.update_rect()
                submit_button.update_font()
            else:
                for box in input_boxes.values():
                    box.handle_event(event)
                for src_box, dest_box in source_dest_boxes:
                    src_box.handle_event(event)
                    dest_box.handle_event(event)
                submit_button.check_click(event)

        # Update number of ships if changed
        num_ships_text = input_boxes["num_ships"].get_text()
        num_ships = int(num_ships_text) if num_ships_text.isdigit() else 0
        if num_ships != current_num_ships:
            current_num_ships = num_ships
            update_ship_inputs(current_num_ships)

        pygame.display.flip()

def start_scenario(inputs):
    global WIDTH, HEIGHT, SCREEN, sea_bg

    map_size_nm = float(inputs.get("map_size", "3") or "3")
    horizon_nm = float(inputs.get("horizon", "2") or "2")
    safety_zone_m = float(inputs.get("safety_zone", "200") or "200")
    ship_width_m = float(inputs.get("ship_width", "200") or "200")
    ship_length_m = float(inputs.get("ship_length", "200") or "200")
    max_speed_knots = float(inputs.get("max_speed", "10") or "10")

    ships_data = inputs.get("source_dest", [])

    simulation = ScenarioSimulation(
        map_size_nm, horizon_nm, safety_zone_m,
        ship_width_m, ship_length_m, max_speed_knots, ships_data,
        window_width=WIDTH,
        window_height=HEIGHT
    )

    running = True
    clock = pygame.time.Clock()
    real_time_accumulator = 0.0

    while running:
        dt = clock.tick(60) / 1000.0  # Delta time in seconds
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                pygame.quit()
                sys.exit()
            elif event.type == pygame.VIDEORESIZE:
                WIDTH, HEIGHT = event.w, event.h
                SCREEN = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)
                scale_images_to_window()
                # Update simulation map scaling
                simulation.update_window_size(WIDTH, HEIGHT)

        # Accumulate real time
        real_time_accumulator += dt
        if real_time_accumulator >= REAL_SECONDS_PER_STEP:
            real_time_accumulator -= REAL_SECONDS_PER_STEP
            # Do one 30s step
            simulation.physics_step()

        # Draw background (could be a different color or image)
        SCREEN.fill(BLUE)

        # Display simulation time step
        time_surface = INPUT_FONT.render(f"Sim Time Step: {simulation.time_step}", True, WHITE)
        SCREEN.blit(time_surface, (int(WIDTH * 0.01), int(HEIGHT * 0.01)))

        # Display scenario status
        if simulation.scenario_ended:
            ended_surface = INPUT_FONT.render("Scenario ended", True, WHITE)
            SCREEN.blit(ended_surface, (int(WIDTH * 0.01), int(HEIGHT * 0.05)))
        else:
            running_surface = INPUT_FONT.render("Scenario Running...", True, WHITE)
            SCREEN.blit(running_surface, (int(WIDTH * 0.01), int(HEIGHT * 0.05)))

        # Draw ships
        simulation.draw_ships()

        pygame.display.flip()

if __name__ == "__main__":
    main_menu()
