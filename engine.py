import pygame
import json
import os
import random
import copy
import math
from settings import *
from inventory import Inventory
from ui import ActionBar

class DummyChannel:
    def play(self, *args, **kwargs): pass
    def stop(self): pass
    def get_busy(self): return False
    def set_volume(self, vol): pass
    def fadeout(self, time): pass

try:
    pygame.mixer.init()
    CH_WALK = pygame.mixer.Channel(1)
    CH_RAIN = pygame.mixer.Channel(2)
    CH_CRICKETS = pygame.mixer.Channel(3)
    CH_TORCHES = pygame.mixer.Channel(4) 
    MIXER_READY = True
except Exception:
    CH_WALK = DummyChannel()
    CH_RAIN = DummyChannel()
    CH_CRICKETS = DummyChannel()
    CH_TORCHES = DummyChannel()
    MIXER_READY = False

def load_audio_safe(filename):
    if not MIXER_READY: return None
    try: return pygame.mixer.Sound(filename)
    except: return None

SFX_PICKUP = load_audio_safe("pickup.wav")
SFX_DOOR = load_audio_safe("door.wav")
SFX_ERROR = load_audio_safe("error.wav")
SFX_USE = load_audio_safe("use.wav")
SFX_WALK = load_audio_safe("walking.mp3")
SFX_RAIN = load_audio_safe("raining.mp3")
SFX_FIREBALL = load_audio_safe("shoot_fireball.wav")
SFX_DRINK = load_audio_safe("drink.wav")
SFX_CRICKETS = load_audio_safe("Midnight_crickets.mp3")
SFX_TORCH = load_audio_safe("torches_burning_sound.mp3") 
SFX_HIT_METALLIC = load_audio_safe("sword_hit_metallic.mp3")

class Game:
    def __init__(self):
        pygame.init()
        pygame.mouse.set_visible(False) 
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("RPGW3D Engine")
        self.clock = pygame.time.Clock()

        # Initialize map early
        self.map = [[TileType.EMPTY.value for _ in range(MAP_SIZE)] for _ in range(MAP_SIZE)]
        
        self.font = pygame.font.SysFont("georgia", 16) 
        self.font_msg = pygame.font.SysFont("georgia", 20, bold=True)
        self.font_small_bold = pygame.font.SysFont("georgia", 14, bold=True)
        self.font_massive = pygame.font.SysFont("georgia", 60, bold=True)
        self.font_massive_win = pygame.font.SysFont("georgia", 50, bold=True)
        
        self.game_over_overlay = pygame.Surface((WIDTH, HEIGHT))
        self.game_over_overlay.set_alpha(200)
        self.game_over_overlay.fill((100, 0, 0))
        
        self.level_complete_overlay = pygame.Surface((WIDTH, HEIGHT))
        self.level_complete_overlay.set_alpha(180)
        self.level_complete_overlay.fill((0, 0, 0))
        
        # Stat system
        self.stat_points = 5
        self.strength = 10
        self.intelligence = 10
        self.endurance = 10
        self.show_stat_screen = False
        
        # Initialize stats
        self.recalculate_max_stats()
        self.health = self.max_health
        self.mana = self.max_mana
        self.stamina = self.max_stamina
        
        # Player position and rotation
        self.player_x = 24.0
        self.player_y = 24.0
        self.player_angle = 0.0
        
        # Create icon and sfx dictionaries for Inventory
        icons_dict = {
            "sword": None, "key": None, "key_silver": None, "key_gold": None,
            "key_dungeon": None, "health_potion": None, "mana_potion": None,
            "artifact": None, "unlit_torch": None, "lit_torch": None, "staff": None
        }
        
        sfx_dict = {
            "door": SFX_DOOR,
            "pickup": SFX_PICKUP,
            "use": SFX_USE,
            "drink": SFX_DRINK
        }
        
        # Inventory and UI
        self.inventory = Inventory(icons_dict, sfx_dict)
        self.action_bar = ActionBar({})
        
        # Game state
        self.game_over = False
        self.level_complete = False
        self.current_level = 1
        
        # Raycasting surface
        self.raycasting_surface = pygame.Surface((WIDTH, HEIGHT))

    def get_initial_map_data(self):
        """Load map from JSON or create default bordered map"""
        default_map = [[TileType.EMPTY.value for _ in range(MAP_SIZE)] for _ in range(MAP_SIZE)]
        for i in range(MAP_SIZE):
            default_map[0][i] = default_map[MAP_SIZE-1][i] = default_map[i][0] = default_map[i][MAP_SIZE-1] = TileType.WALL_BRICK.value
        
        try:
            map_file = MAP_DATA_FILE if self.current_level == 1 else f"map_level_{self.current_level}.json"
            if os.path.exists(map_file):
                with open(map_file, "r") as f:
                    data = json.load(f)
                    # Handle both dict and list formats
                    if isinstance(data, dict):
                        map_data = data.get('map', default_map)
                    else:
                        map_data = data
                    
                    # Verify dimensions
                    if len(map_data) == MAP_SIZE and len(map_data[0]) == MAP_SIZE:
                        print(f"Map successfully loaded from {map_file}.")
                        return map_data
                    else:
                        print("Map data size mismatch! Falling back to default map.")
        except Exception as e:
            print(f"Failed to load map data: {e}")
            
        return default_map

    def recalculate_max_stats(self):
        """Recalculate max stats based on attributes"""
        self.max_health = 50 + (self.endurance * 5)
        self.max_mana = 20 + (self.intelligence * 3)
        self.max_stamina = 50 + (self.endurance * 5)
        self.melee_dmg = 20 + int(self.strength * 1.5)
        self.magic_dmg = 25 + int(self.intelligence * 2.0)

    def is_walkable(self, x, y):
        """Check if a tile is walkable"""
        grid_x = int(x)
        grid_y = int(y)
        
        if not (0 <= grid_x < MAP_SIZE and 0 <= grid_y < MAP_SIZE):
            return False
        
        tile = self.map[grid_y][grid_x]
        
        # Walls and obstacles are not walkable
        non_walkable = [
            TileType.WALL_BRICK.value, TileType.WALL_STONE.value, TileType.WALL_WOOD.value,
            TileType.WALL_BRICK_CRACKED.value, TileType.WALL_STONE_CRACKED.value, 
            TileType.WALL_WOOD_CRACKED.value, TileType.TREE.value, TileType.DEAD_TREE.value,
            TileType.BUSH.value, TileType.ROCK.value, TileType.FORCE_FIELD.value
        ]
        
        return tile not in non_walkable

    def handle_player_movement(self, keys):
        """Handle player movement based on key input"""
        old_x, old_y = self.player_x, self.player_y
        move_speed = PLAYER_SPEED
        
        # Forward/Backward movement
        if keys[pygame.K_w]:
            new_x = self.player_x + math.cos(self.player_angle) * move_speed
            new_y = self.player_y + math.sin(self.player_angle) * move_speed
            if self.is_walkable(new_x, new_y):
                self.player_x = new_x
                self.player_y = new_y
        
        if keys[pygame.K_s]:
            new_x = self.player_x - math.cos(self.player_angle) * move_speed
            new_y = self.player_y - math.sin(self.player_angle) * move_speed
            if self.is_walkable(new_x, new_y):
                self.player_x = new_x
                self.player_y = new_y
        
        # Strafe left/right
        if keys[pygame.K_a]:
            new_x = self.player_x + math.cos(self.player_angle - math.pi / 2) * move_speed
            new_y = self.player_y + math.sin(self.player_angle - math.pi / 2) * move_speed
            if self.is_walkable(new_x, new_y):
                self.player_x = new_x
                self.player_y = new_y
        
        if keys[pygame.K_d]:
            new_x = self.player_x + math.cos(self.player_angle + math.pi / 2) * move_speed
            new_y = self.player_y + math.sin(self.player_angle + math.pi / 2) * move_speed
            if self.is_walkable(new_x, new_y):
                self.player_x = new_x
                self.player_y = new_y
        
        # Rotation
        if keys[pygame.K_LEFT]:
            self.player_angle -= PLAYER_ROTATION_SPEED
        
        if keys[pygame.K_RIGHT]:
            self.player_angle += PLAYER_ROTATION_SPEED

    def cast_ray(self, angle):
        """Cast a single ray and return the distance to the nearest wall"""
        sin_a = math.sin(angle)
        cos_a = math.cos(angle)
        
        for depth in range(1, MAX_DEPTH):
            target_x = self.player_x + cos_a * depth
            target_y = self.player_y + sin_a * depth
            
            col = int(target_x / TILE_SIZE)
            row = int(target_y / TILE_SIZE)
            
            if col < 0 or col >= MAP_SIZE or row < 0 or row >= MAP_SIZE:
                return depth
            
            # Check for walls
            tile = self.map[row][col]
            if tile in [TileType.WALL_BRICK.value, TileType.WALL_STONE.value, TileType.WALL_WOOD.value,
                       TileType.WALL_BRICK_CRACKED.value, TileType.WALL_STONE_CRACKED.value,
                       TileType.WALL_WOOD_CRACKED.value]:
                return depth
        
        return MAX_DEPTH

    def render_3d_view(self):
        """Render the 3D first-person view using raycasting"""
        self.raycasting_surface.fill((50, 50, 60))  # Sky/ceiling color
        
        # Draw floor
        pygame.draw.rect(self.raycasting_surface, (40, 50, 40), (0, HEIGHT // 2, WIDTH, HEIGHT // 2))
        
        # Cast rays for each column
        for i in range(NUM_RAYS):
            angle = self.player_angle - (FOV / 2) + (i * DELTA_ANGLE)
            depth = self.cast_ray(angle)
            
            # Correct for fisheye effect
            depth = depth * math.cos(angle - self.player_angle)
            
            # Calculate wall height
            if depth > 0:
                wall_height = min(int((WALL_HEIGHT_MULTIPLIER / depth)), HEIGHT)
            else:
                wall_height = HEIGHT
            
            # Draw wall slice
            col_width = WIDTH // NUM_RAYS
            x = i * col_width
            
            # Shade based on distance
            shade = max(50, 255 - (depth / MAX_DEPTH) * 200)
            color = (shade, shade * 0.7, shade * 0.5)
            
            rect = pygame.Rect(x, (HEIGHT - wall_height) // 2, col_width, wall_height)
            pygame.draw.rect(self.raycasting_surface, color, rect)
        
        self.screen.blit(self.raycasting_surface, (0, 0))

    def render_ui(self):
        """Render UI elements like health, mana, stats"""
        # Health bar
        health_text = self.font_msg.render(f"HP: {self.health}/{self.max_health}", True, (255, 0, 0))
        self.screen.blit(health_text, (10, 10))
        
        # Mana bar
        mana_text = self.font_msg.render(f"Mana: {self.mana}/{self.max_mana}", True, (0, 100, 255))
        self.screen.blit(mana_text, (10, 35))
        
        # Stamina bar
        stamina_text = self.font_msg.render(f"Stamina: {self.stamina}/{self.max_stamina}", True, (0, 255, 0))
        self.screen.blit(stamina_text, (10, 60))
        
        # Level info
        level_text = self.font.render(f"Level: {self.current_level}", True, (200, 200, 200))
        self.screen.blit(level_text, (WIDTH - 150, 10))
        
        # Controls hint
        controls_text = self.font.render("W/A/S/D: Move | Arrow Keys: Rotate | C: Stats | ESC: Quit", True, (150, 150, 150))
        self.screen.blit(controls_text, (WIDTH // 2 - controls_text.get_width() // 2, HEIGHT - 25))
        
        # Action bar
        self.action_bar.draw(self.screen)

    def render_stat_screen(self):
        """Render the stat allocation screen"""
        self.screen.fill((20, 20, 25))
        
        title = self.font_massive.render("CHARACTER STATS", True, (255, 215, 0))
        self.screen.blit(title, (WIDTH // 2 - title.get_width() // 2, 50))
        
        y_pos = 150
        stat_color = (100, 200, 255)
        
        # Display stats and available points
        stats = [
            ("Strength", self.strength),
            ("Intelligence", self.intelligence),
            ("Endurance", self.endurance),
        ]
        
        for stat_name, stat_val in stats:
            text = self.font_msg.render(f"{stat_name}: {stat_val}", True, stat_color)
            self.screen.blit(text, (WIDTH // 2 - 150, y_pos))
            y_pos += 40
        
        # Display derived stats
        y_pos += 20
        derived_color = (200, 150, 100)
        derived = [
            (f"Max Health: {self.max_health}", derived_color),
            (f"Max Mana: {self.max_mana}", derived_color),
            (f"Melee Damage: {self.melee_dmg}", derived_color),
            (f"Magic Damage: {self.magic_dmg}", derived_color),
        ]
        
        for text_str, color in derived:
            text = self.font.render(text_str, True, color)
            self.screen.blit(text, (WIDTH // 2 - 150, y_pos))
            y_pos += 30
        
        # Available points
        points_text = self.font_msg.render(f"Points Available: {self.stat_points}", True, (0, 255, 100))
        self.screen.blit(points_text, (WIDTH // 2 - points_text.get_width() // 2, HEIGHT - 100))
        
        # Instructions
        instr = self.font.render("Press C to close | Press ESC to quit", True, (150, 150, 150))
        self.screen.blit(instr, (WIDTH // 2 - instr.get_width() // 2, HEIGHT - 40))

    def check_item_pickup(self):
        """Check if player is on an item and pick it up"""
        tile_x = int(self.player_x / TILE_SIZE)
        tile_y = int(self.player_y / TILE_SIZE)
        
        if 0 <= tile_x < MAP_SIZE and 0 <= tile_y < MAP_SIZE:
            tile = self.map[tile_y][tile_x]
            
            if tile == TileType.ITEM_DAGGER.value:
                self.inventory.add_item("Dagger", 1, "weapon", "A sharp blade", health=0, mana=0)
                self.map[tile_y][tile_x] = TileType.EMPTY.value
                if SFX_PICKUP: SFX_PICKUP.play()
            elif tile == TileType.ITEM_HEALTH_POTION.value:
                self.health = min(self.health + 25, self.max_health)
                self.map[tile_y][tile_x] = TileType.EMPTY.value
                if SFX_DRINK: SFX_DRINK.play()
            elif tile == TileType.ITEM_FOOD.value:
                self.stamina = min(self.stamina + 20, self.max_stamina)
                self.map[tile_y][tile_x] = TileType.EMPTY.value
                if SFX_DRINK: SFX_DRINK.play()
            elif tile == TileType.STAIRS.value:
                self.level_complete = True

    def run(self):
        """Main game loop"""
        # Load map
        self.map = self.get_initial_map_data()
        
        # Find player spawn point
        for y in range(MAP_SIZE):
            for x in range(MAP_SIZE):
                if self.map[y][x] == TileType.PLAYER_SPAWN.value:
                    self.player_x = x * TILE_SIZE + TILE_SIZE // 2
                    self.player_y = y * TILE_SIZE + TILE_SIZE // 2
                    break
        
        running = True
        while running:
            # Event handling
            for e in pygame.event.get():
                if e.type == pygame.QUIT or (e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE):
                    return
                elif e.type == pygame.KEYDOWN:
                    if e.key == pygame.K_c:
                        self.show_stat_screen = not self.show_stat_screen
            
            # Stat screen
            if self.show_stat_screen:
                self.render_stat_screen()
                pygame.display.flip()
                self.clock.tick(FPS)
                continue
            
            # Game over screen
            if self.game_over:
                self.screen.blit(self.game_over_overlay, (0, 0))
                game_over_text = self.font_massive.render("YOU DIED", True, (255, 0, 0))
                self.screen.blit(game_over_text, (WIDTH // 2 - game_over_text.get_width() // 2, HEIGHT // 2 - 50))
                restart_text = self.font.render("Press R to restart or ESC to quit", True, (200, 200, 200))
                self.screen.blit(restart_text, (WIDTH // 2 - restart_text.get_width() // 2, HEIGHT // 2 + 50))
                pygame.display.flip()
                
                for e in pygame.event.get():
                    if e.type == pygame.KEYDOWN:
                        if e.key == pygame.K_r:
                            self.game_over = False
                            self.health = self.max_health
                            self.run()  # Restart
                            return
                        elif e.key == pygame.K_ESCAPE:
                            return
                
                self.clock.tick(FPS)
                continue
            
            # Level complete screen
            if self.level_complete:
                self.screen.blit(self.level_complete_overlay, (0, 0))
                complete_text = self.font_massive_win.render("LEVEL COMPLETE!", True, (0, 255, 100))
                self.screen.blit(complete_text, (WIDTH // 2 - complete_text.get_width() // 2, HEIGHT // 2 - 50))
                next_text = self.font.render("Press SPACE to continue or ESC to quit", True, (200, 200, 200))
                self.screen.blit(next_text, (WIDTH // 2 - next_text.get_width() // 2, HEIGHT // 2 + 50))
                pygame.display.flip()
                
                for e in pygame.event.get():
                    if e.type == pygame.KEYDOWN:
                        if e.key == pygame.K_SPACE:
                            self.level_complete = False
                            self.current_level += 1
                            self.map = self.get_initial_map_data()
                        elif e.key == pygame.K_ESCAPE:
                            return
                
                self.clock.tick(FPS)
                continue
            
            # Normal gameplay
            keys = pygame.key.get_pressed()
            self.handle_player_movement(keys)
            self.check_item_pickup()
            
            # Render
            self.render_3d_view()
            self.render_ui()
            
            # Natural health/mana/stamina decay
            if self.stamina > 0:
                self.stamina = min(self.stamina + 0.05, self.max_stamina)
            if self.mana > 0:
                self.mana = min(self.mana + 0.1, self.max_mana)
            
            pygame.display.flip()
            self.clock.tick(FPS)
