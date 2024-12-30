import pygame
import math
from constants import *

def draw_sunflower(surface, x, y, size):
    # Get animation offset based on time
    time = pygame.time.get_ticks()
    sway = math.sin(time * 0.003) * 3
    petal_spin = time * 0.002
    
    # Draw stem with swaying animation
    stem_points = [
        (x + size//2 + sway, y + size*3//4),
        (x + size//2, y + size*7//8),
        (x + size//2, y + size)
    ]
    pygame.draw.lines(surface, GREEN, False, stem_points, 3)
    
    # Draw leaves
    leaf_color = (34, 139, 34)  # Forest green
    leaf_points = [
        (x + size//2, y + size*3//4),
        (x + size//3, y + size*7//8),
        (x + size//2, y + size*13//16)
    ]
    pygame.draw.polygon(surface, leaf_color, leaf_points)
    leaf_points = [
        (x + size//2, y + size*3//4),
        (x + size*2//3, y + size*7//8),
        (x + size//2, y + size*13//16)
    ]
    pygame.draw.polygon(surface, leaf_color, leaf_points)
    
    # Draw center with gradient
    center_x, center_y = x + size//2 + sway, y + size//2
    pygame.draw.circle(surface, (160, 82, 45), (center_x, center_y), size//4)  # Dark brown
    pygame.draw.circle(surface, (139, 69, 19), (center_x, center_y), size//5)  # Medium brown
    pygame.draw.circle(surface, (101, 67, 33), (center_x, center_y), size//6)  # Light brown
    
    # Draw petals with rotation animation
    petal_colors = [(255, 218, 0), (255, 200, 0), (255, 182, 0)]  # Different yellow shades
    for i, angle in enumerate(range(0, 360, 45)):
        rad = math.radians(angle + petal_spin)
        petal_x = center_x + math.cos(rad) * size//3
        petal_y = center_y + math.sin(rad) * size//3
        # Draw each petal with multiple layers for depth
        pygame.draw.circle(surface, petal_colors[i % 3], (int(petal_x), int(petal_y)), size//6)
        pygame.draw.circle(surface, petal_colors[(i + 1) % 3], (int(petal_x), int(petal_y)), size//8)

def draw_peashooter(surface, x, y, size):
    # Get animation offset
    time = pygame.time.get_ticks()
    sway = math.sin(time * 0.003) * 3
    
    # Draw stem with swaying animation
    stem_points = [
        (x + size//2 + sway, y + size*2//3),
        (x + size//2, y + size*7//8),
        (x + size//2, y + size)
    ]
    pygame.draw.lines(surface, GREEN, False, stem_points, 3)
    
    # Draw leaves
    leaf_color = (34, 139, 34)
    leaf_points = [
        (x + size//2, y + size*3//4),
        (x + size//3, y + size*7//8),
        (x + size//2, y + size*13//16)
    ]
    pygame.draw.polygon(surface, leaf_color, leaf_points)
    
    # Draw head with gradient
    head_x = x + size//2 + sway
    head_color = (0, 200, 0)
    pygame.draw.ellipse(surface, head_color, (head_x - size//4, y + size//4, size//2, size//2))
    pygame.draw.ellipse(surface, (0, 180, 0), (head_x - size//5, y + size//3, size//2.5, size//2.5))
    
    # Draw shooter with highlight
    shooter_x = head_x + size//4
    shooter_color = (0, 100, 0)
    pygame.draw.circle(surface, shooter_color, (int(shooter_x), y + size//2), size//7)
    pygame.draw.circle(surface, (0, 150, 0), (int(shooter_x), y + size//2), size//10)
    
    # Draw eyes
    eye_color = (0, 0, 0)
    eye_x = head_x - size//8
    pygame.draw.ellipse(surface, eye_color, (eye_x, y + size//3, size//10, size//8))
    pygame.draw.ellipse(surface, eye_color, (eye_x + size//6, y + size//3, size//10, size//8))

def draw_wallnut(surface, x, y, size):
    # Get animation offset
    time = pygame.time.get_ticks()
    wobble = math.sin(time * 0.004) * 2
    
    # Draw main body with gradient and texture
    nut_colors = [(139, 69, 19), (160, 82, 45), (205, 133, 63)]
    for i, color in enumerate(nut_colors):
        offset = i * 4
        pygame.draw.ellipse(surface, color, 
                          (x + size//6 + offset + wobble, 
                           y + size//6 + offset, 
                           size*2//3 - offset*2, 
                           size*2//3 - offset*2))
    
    # Draw crack details
    crack_color = (101, 67, 33)
    crack_points = [
        (x + size//2, y + size//4),
        (x + size*2//3, y + size//3),
        (x + size//2, y + size//2)
    ]
    pygame.draw.lines(surface, crack_color, False, crack_points, 2)
    
    # Draw face with expression
    eye_color = BLACK
    blink = (time % 3000) < 200  # Blink every 3 seconds
    if not blink:
        # Draw eyes
        pygame.draw.ellipse(surface, eye_color, (x + size//3, y + size//3, size//6, size//6))
        pygame.draw.ellipse(surface, eye_color, (x + size//2, y + size//3, size//6, size//6))
        # Draw white highlights in eyes
        pygame.draw.circle(surface, WHITE, (x + size//3 + size//12, y + size//3 + size//12), size//20)
        pygame.draw.circle(surface, WHITE, (x + size//2 + size//12, y + size//3 + size//12), size//20)
    else:
        # Draw closed eyes
        pygame.draw.line(surface, eye_color, (x + size//3, y + size//3), (x + size//3 + size//6, y + size//3), 2)
        pygame.draw.line(surface, eye_color, (x + size//2, y + size//3), (x + size//2 + size//6, y + size//3), 2)
    
    # Draw smile that changes with wobble
    smile_rect = pygame.Rect(x + size//3 + wobble, y + size//2, size//3, size//6)
    pygame.draw.arc(surface, eye_color, smile_rect, 0, math.pi, 2)

def draw_chomper(surface, x, y, size):
    # Get animation offset
    time = pygame.time.get_ticks()
    chomp = abs(math.sin(time * 0.004)) * size//4
    sway = math.sin(time * 0.003) * 3
    
    # Draw stem with swaying animation
    stem_points = [
        (x + size//2 + sway, y + size*2//3),
        (x + size//2, y + size*7//8),
        (x + size//2, y + size)
    ]
    pygame.draw.lines(surface, GREEN, False, stem_points, 4)
    
    # Draw head
    head_color = (148, 0, 211)  # Purple
    head_x = x + size//2 + sway
    
    # Draw back of mouth
    pygame.draw.ellipse(surface, (101, 0, 148), 
                       (head_x - size//3, y + size//4, size*2//3, size//2))
    
    # Draw tongue
    tongue_color = (255, 105, 180)
    tongue_points = [
        (head_x, y + size//2),
        (head_x - size//4, y + size//2 + size//4),
        (head_x + size//4, y + size//2 + size//4)
    ]
    pygame.draw.polygon(surface, tongue_color, tongue_points)
    
    # Draw mouth (upper and lower jaw)
    jaw_points_upper = [
        (head_x - size//3, y + size//3),
        (head_x + size//3, y + size//3),
        (head_x + size//2, y + size//2),
        (head_x - size//2, y + size//2)
    ]
    jaw_points_lower = [
        (head_x - size//3, y + size//2 + chomp),
        (head_x + size//3, y + size//2 + chomp),
        (head_x + size//2, y + size*2//3 + chomp),
        (head_x - size//2, y + size*2//3 + chomp)
    ]
    pygame.draw.polygon(surface, head_color, jaw_points_upper)
    pygame.draw.polygon(surface, head_color, jaw_points_lower)
    
    # Draw teeth
    teeth_color = WHITE
    tooth_width = size//8
    for tooth_x in range(int(head_x - size//3), int(head_x + size//3), tooth_width):
        # Upper teeth
        pygame.draw.polygon(surface, teeth_color, [
            (tooth_x, y + size//2),
            (tooth_x + tooth_width//2, y + size//2 - size//8),
            (tooth_x + tooth_width, y + size//2)
        ])
        # Lower teeth
        pygame.draw.polygon(surface, teeth_color, [
            (tooth_x, y + size//2 + chomp),
            (tooth_x + tooth_width//2, y + size//2 + size//8 + chomp),
            (tooth_x + tooth_width, y + size//2 + chomp)
        ])

def draw_snow_pea(surface, x, y, size):
    # Get animation offset
    time = pygame.time.get_ticks()
    sway = math.sin(time * 0.003) * 3
    ice_spin = time * 0.003
    
    # Draw stem with swaying animation
    stem_points = [
        (x + size//2 + sway, y + size*2//3),
        (x + size//2, y + size*7//8),
        (x + size//2, y + size)
    ]
    pygame.draw.lines(surface, GREEN, False, stem_points, 3)
    
    # Draw leaves with frost effect
    leaf_color = (150, 200, 150)
    leaf_points = [
        (x + size//2, y + size*3//4),
        (x + size//3, y + size*7//8),
        (x + size//2, y + size*13//16)
    ]
    pygame.draw.polygon(surface, leaf_color, leaf_points)
    
    # Draw head with ice effect
    head_x = x + size//2 + sway
    head_colors = [(0, 191, 255), (135, 206, 235), (176, 224, 230)]
    for i, color in enumerate(head_colors):
        offset = i * 3
        pygame.draw.ellipse(surface, color,
                          (head_x - size//4 + offset, 
                           y + size//4 + offset,
                           size//2 - offset*2, 
                           size//2 - offset*2))
    
    # Draw ice crystals with rotation
    crystal_color = (200, 232, 255)
    for i in range(4):
        angle = ice_spin + i * (math.pi/2)
        crystal_x = head_x + math.cos(angle) * size//3
        crystal_y = y + size//2 + math.sin(angle) * size//3
        crystal_points = [
            (crystal_x, crystal_y - size//8),
            (crystal_x + size//8, crystal_y),
            (crystal_x, crystal_y + size//8),
            (crystal_x - size//8, crystal_y)
        ]
        pygame.draw.polygon(surface, crystal_color, crystal_points)
    
    # Draw frost particles
    for i in range(3):
        particle_x = head_x + math.cos(time * 0.001 + i * 2) * size//4
        particle_y = y + size//2 + math.sin(time * 0.001 + i * 2) * size//4
        pygame.draw.circle(surface, (255, 255, 255, 128), 
                         (int(particle_x), int(particle_y)), size//16)

def draw_normal_zombie(surface, x, y, size):
    # Get animation offset
    time = pygame.time.get_ticks()
    wobble = math.sin(time * 0.004) * 3
    
    # Draw shadow
    shadow_surface = pygame.Surface((size*2//3, size//4), pygame.SRCALPHA)
    pygame.draw.ellipse(shadow_surface, (0, 0, 0, 64), (0, 0, size*2//3, size//4))
    surface.blit(shadow_surface, (x + size//6, y + size - size//8))
    
    # Draw legs with walking animation
    leg_color = (100, 100, 100)
    leg_offset = abs(math.sin(time * 0.004)) * 5
    pygame.draw.line(surface, leg_color, 
                    (x + size//2, y + size*2//3),
                    (x + size//3, y + size - leg_offset), 4)
    pygame.draw.line(surface, leg_color,
                    (x + size//2, y + size*2//3),
                    (x + size*2//3, y + size - leg_offset), 4)
    
    # Draw tattered clothes
    clothes_color = (50, 50, 50)
    clothes_points = [
        (x + size//3, y + size//2),
        (x + size*2//3, y + size//2),
        (x + size*2//3, y + size*3//4),
        (x + size//3, y + size*3//4)
    ]
    pygame.draw.polygon(surface, clothes_color, clothes_points)
    
    # Draw arms with swaying animation
    arm_color = (100, 100, 100)
    arm_sway = math.sin(time * 0.004) * 10
    pygame.draw.line(surface, arm_color,
                    (x + size//2, y + size//2),
                    (x + size//4 + arm_sway, y + size*2//3), 4)
    pygame.draw.line(surface, arm_color,
                    (x + size//2, y + size//2),
                    (x + size*3//4 + arm_sway, y + size*2//3), 4)
    
    # Draw body with details
    body_color = (169, 169, 169)
    pygame.draw.ellipse(surface, body_color, 
                       (x + size//3 + wobble, y + size//3, size//3, size//2))
    
    # Draw head with details
    head_color = (169, 169, 169)
    pygame.draw.circle(surface, head_color, 
                      (int(x + size//2 + wobble), int(y + size//3)), size//4)
    
    # Draw facial features
    eye_color = (255, 0, 0)  # Red eyes
    pygame.draw.circle(surface, eye_color, 
                      (int(x + size//2 - size//8 + wobble), int(y + size//3)), size//12)
    pygame.draw.circle(surface, eye_color,
                      (int(x + size//2 + size//8 + wobble), int(y + size//3)), size//12)
    
    # Draw mouth
    mouth_color = (100, 0, 0)
    mouth_points = [
        (x + size//2 - size//6 + wobble, y + size//3 + size//6),
        (x + size//2 + size//6 + wobble, y + size//3 + size//6),
        (x + size//2 + wobble, y + size//3 + size//4)
    ]
    pygame.draw.polygon(surface, mouth_color, mouth_points)

def draw_cone_zombie(surface, x, y, size):
    # Draw base zombie
    draw_normal_zombie(surface, x, y, size)
    
    # Get animation offset
    time = pygame.time.get_ticks()
    wobble = math.sin(time * 0.004) * 3
    
    # Draw cone with details and shading
    cone_colors = [(139, 69, 19), (160, 82, 45), (205, 133, 63)]  # Different shades of brown
    for i, color in enumerate(cone_colors):
        offset = i * 2
        points = [
            (x + size//2 + wobble, y - size//6 + offset),
            (x + size//3 + offset, y + size//3),
            (x + size*2//3 - offset, y + size//3)
        ]
        pygame.draw.polygon(surface, color, points)
    
    # Draw cone damage (dents and scratches)
    scratch_color = (101, 67, 33)
    scratch_points = [
        (x + size//2 - size//8 + wobble, y + size//6),
        (x + size//2 + size//8 + wobble, y + size//4)
    ]
    pygame.draw.lines(surface, scratch_color, False, scratch_points, 2)

def draw_bucket_zombie(surface, x, y, size):
    # Draw base zombie
    draw_normal_zombie(surface, x, y, size)
    
    # Get animation offset
    time = pygame.time.get_ticks()
    wobble = math.sin(time * 0.004) * 3
    
    # Draw bucket with metallic effect
    bucket_colors = [(192, 192, 192), (169, 169, 169), (128, 128, 128)]
    for i, color in enumerate(bucket_colors):
        offset = i * 2
        pygame.draw.rect(surface, color,
                        (x + size//4 + offset + wobble, 
                         y - size//6 + offset,
                         size//2 - offset*2, 
                         size//3))
    
    # Draw bucket rim
    rim_color = (211, 211, 211)
    pygame.draw.rect(surface, rim_color,
                    (x + size//4 - 2 + wobble, y - size//6, size//2 + 4, 4))
    
    # Draw bucket highlights
    highlight_color = (255, 255, 255)
    pygame.draw.line(surface, highlight_color,
                    (x + size//3 + wobble, y),
                    (x + size*2//3 + wobble, y), 2)
    
    # Draw dents and damage
    dent_color = (128, 128, 128)
    pygame.draw.arc(surface, dent_color,
                   (x + size//3 + wobble, y, size//4, size//6),
                   0, math.pi, 2)

def draw_newspaper_zombie(surface, x, y, size):
    # Draw base zombie
    draw_normal_zombie(surface, x, y, size)
    
    # Get animation offset
    time = pygame.time.get_ticks()
    wobble = math.sin(time * 0.004) * 3
    paper_shake = math.sin(time * 0.008) * 2
    
    # Draw newspaper with animated shaking
    paper_color = (255, 255, 255)
    pygame.draw.rect(surface, paper_color,
                    (x + size//6 + paper_shake, 
                     y + size//3,
                     size//2,
                     size//2))
    
    # Draw newspaper content (headlines and text)
    text_color = (0, 0, 0)
    for i in range(4):
        y_pos = y + size//3 + i*size//8
        pygame.draw.line(surface, text_color,
                        (x + size//5 + paper_shake, y_pos),
                        (x + size*2//3 + paper_shake, y_pos), 1)
    
    # Draw newspaper damage
    if time % 2000 < 1000:  # Animate paper damage
        tear_points = [
            (x + size//3 + paper_shake, y + size//3),
            (x + size//2 + paper_shake, y + size//2),
            (x + size//3 + paper_shake, y + size*2//3)
        ]
        pygame.draw.lines(surface, (200, 200, 200), False, tear_points, 2)

def draw_dancing_zombie(surface, x, y, size):
    # Get animation offset
    time = pygame.time.get_ticks()
    dance_move = math.sin(time * 0.006) * 10
    spin = math.sin(time * 0.003) * 0.3
    
    # Draw shadow
    shadow_surface = pygame.Surface((size*2//3, size//4), pygame.SRCALPHA)
    pygame.draw.ellipse(shadow_surface, (0, 0, 0, 64), (0, 0, size*2//3, size//4))
    surface.blit(shadow_surface, (x + size//6, y + size - size//8))
    
    # Draw legs in dancing pose
    leg_color = (100, 100, 100)
    pygame.draw.line(surface, leg_color,
                    (x + size//2, y + size//2),
                    (x + size//4 + dance_move, y + size), 4)
    pygame.draw.line(surface, leg_color,
                    (x + size//2, y + size//2),
                    (x + size*3//4 - dance_move, y + size), 4)
    
    # Draw disco outfit
    outfit_color = (148, 0, 211)  # Purple
    outfit_points = [
        (x + size//3 + dance_move/2, y + size//3),
        (x + size*2//3 + dance_move/2, y + size//3),
        (x + size*2//3 - dance_move/2, y + size*3//4),
        (x + size//3 - dance_move/2, y + size*3//4)
    ]
    pygame.draw.polygon(surface, outfit_color, outfit_points)
    
    # Draw arms in dancing pose
    arm_color = (100, 100, 100)
    pygame.draw.line(surface, arm_color,
                    (x + size//2, y + size//2),
                    (x + size//4 - dance_move, y + size//3), 4)
    pygame.draw.line(surface, arm_color,
                    (x + size//2, y + size//2),
                    (x + size*3//4 + dance_move, y + size//3), 4)
    
    # Draw body with disco moves
    body_color = (169, 169, 169)
    body_rect = pygame.Rect(x + size//3 + dance_move/2, y + size//4,
                          size//3, size//2)
    rotated_surface = pygame.Surface((size, size), pygame.SRCALPHA)
    pygame.draw.ellipse(rotated_surface, body_color, body_rect)
    
    # Draw head with cool hair
    head_color = (169, 169, 169)
    pygame.draw.circle(rotated_surface, head_color,
                      (int(x + size//2 + dance_move/2), int(y + size//3)),
                      size//4)
    
    # Draw spiky hair with animation
    hair_color = (0, 0, 0)
    for i in range(6):
        angle = i * math.pi/3 + spin
        hair_x = x + size//2 + math.cos(angle) * size//3 + dance_move/2
        hair_y = y + size//3 + math.sin(angle) * size//4
        pygame.draw.line(surface, hair_color,
                        (x + size//2 + dance_move/2, y + size//3),
                        (hair_x, hair_y), 3)
    
    # Draw sunglasses
    glasses_color = (0, 0, 0)
    pygame.draw.rect(surface, glasses_color,
                    (x + size//3 + dance_move/2, y + size//4,
                     size//3, size//8))
    
    # Draw disco ball effect
    for i in range(8):
        angle = i * math.pi/4 + time * 0.01
        sparkle_x = x + size//2 + math.cos(angle) * size//2
        sparkle_y = y + size//3 + math.sin(angle) * size//2
        pygame.draw.circle(surface, (255, 255, 255),
                         (int(sparkle_x), int(sparkle_y)), 2)

def draw_rose_shooter(surface, x, y, size):
    # Get animation offset
    time = pygame.time.get_ticks()
    sway = math.sin(time * 0.003) * 3
    petal_spin = time * 0.002
    
    # Draw stem with swaying animation
    stem_points = [
        (x + size//2 + sway, y + size*2//3),
        (x + size//2, y + size*7//8),
        (x + size//2, y + size)
    ]
    pygame.draw.lines(surface, GREEN, False, stem_points, 3)
    
    # Draw leaves
    leaf_color = (34, 139, 34)  # Forest green
    leaf_points = [
        (x + size//2, y + size*3//4),
        (x + size//3, y + size*7//8),
        (x + size//2, y + size*13//16)
    ]
    pygame.draw.polygon(surface, leaf_color, leaf_points)
    
    # Draw thorns
    thorn_color = (139, 69, 19)  # Brown
    thorn_points = [
        [(x + size//2 - 5, y + size*3//4), (x + size//2 - 10, y + size*3//4 - 5), (x + size//2 - 5, y + size*3//4 - 5)],
        [(x + size//2 + 5, y + size*3//4), (x + size//2 + 10, y + size*3//4 - 5), (x + size//2 + 5, y + size*3//4 - 5)]
    ]
    for points in thorn_points:
        pygame.draw.polygon(surface, thorn_color, points)
    
    # Draw rose head with gradient
    head_x = x + size//2 + sway
    head_y = y + size//2
    rose_colors = [(255, 192, 203), (255, 182, 193), (255, 105, 180)]  # Pink gradients
    
    # Draw petals in layers
    for i, color in enumerate(rose_colors):
        offset = i * 3
        for angle in range(0, 360, 45):
            rad = math.radians(angle + petal_spin)
            petal_x = head_x + math.cos(rad) * (size//4 - offset)
            petal_y = head_y + math.sin(rad) * (size//4 - offset)
            pygame.draw.circle(surface, color, (int(petal_x), int(petal_y)), size//6 - offset)
    
    # Draw center
    pygame.draw.circle(surface, (139, 0, 0), (int(head_x), int(head_y)), size//8)  # Dark red center
    
    # Draw shooter with highlight
    shooter_x = head_x + size//4
    shooter_color = (255, 20, 147)  # Deep pink
    pygame.draw.circle(surface, shooter_color, (int(shooter_x), head_y), size//7)
    pygame.draw.circle(surface, (255, 105, 180), (int(shooter_x), head_y), size//10)  # Highlight

# Dictionary mapping plant types to their drawing functions
PLANT_DRAWINGS = {
    PlantType.SUNFLOWER: draw_sunflower,
    PlantType.PEASHOOTER: draw_peashooter,
    PlantType.ROSE_SHOOTER: draw_rose_shooter,
    PlantType.CHOMPER: draw_chomper,
    PlantType.SNOW_PEA: draw_snow_pea
}

# Dictionary mapping zombie types to their drawing functions
ZOMBIE_DRAWINGS = {
    ZombieType.NORMAL: draw_normal_zombie,
    ZombieType.CONE: draw_cone_zombie,
    ZombieType.BUCKET: draw_bucket_zombie,
    ZombieType.NEWSPAPER: draw_newspaper_zombie,
    ZombieType.DANCING: draw_dancing_zombie
} 