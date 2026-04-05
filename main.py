import pygame
from pygame.locals import *

from OpenGL.GL import *
from OpenGL.GLU import *

import os
import numpy as np
import pandas as pd

import sys
sys.path.append('..')
from Pacman import Pacman
from Ghost  import Ghost
from Blinky import Blinky   # rojo  — persecución directa (distancia Manhattan)
from Pinky  import Pinky    # rosa  — emboscada con poda alfa-beta

# ── Ventana ───────────────────────────────────────────────────────────────────
screen_width  = 720
screen_height = 720

# ── Archivos ──────────────────────────────────────────────────────────────────
BASE_PATH  = os.path.abspath(os.path.dirname(__file__))
file_map   = os.path.join(BASE_PATH, 'mapa.bmp')
img_pacman = os.path.join(BASE_PATH, 'pacman.bmp')
img_ghost1 = os.path.join(BASE_PATH, 'fantasma1.bmp')   # rojo  → Blinky
img_ghost2 = os.path.join(BASE_PATH, 'fantasma2.bmp')   # rosa  → Pinky
img_ghost3 = os.path.join(BASE_PATH, 'fantasma3.bmp')
img_ghost4 = os.path.join(BASE_PATH, 'fantasma4.bmp')

file_csv = os.path.join(BASE_PATH, 'mapa.csv')
matrix   = np.array(pd.io.parsers.read_csv(file_csv, header=None)).astype("int")

# ── Matrices de control ───────────────────────────────────────────────────────
MC = [
    [10,0,21,0,11,10,0,21,0,11],
    [24,0,25,21,23,23,21,25,0,22],
    [12,0,22,12,11,10,13,24,0,13],
    [0,0,0,10,23,23,11,0,0,0],
    [26,0,25,22,0,0,24,25,0,27],
    [0,0,0,24,0,0,22,0,0,0],
    [10,0,25,23,11,10,23,25,0,11],
    [12,11,24,21,23,23,21,22,10,13],
    [10,23,13,12,11,10,13,12,23,11],
    [12,0,0,0,23,23,0,0,0,13]
]

XPxToMC = np.full(359, -1, dtype=int)
for px, mc_idx in zip([0,30,71,114,156,199,242,286,328,358], range(10)):
    XPxToMC[px] = mc_idx

YPxToMC = np.full(361, -1, dtype=int)
for px, mc_idx in zip([0,51,90,130,168,208,244,282,320,360], range(10)):
    YPxToMC[px] = mc_idx

# ── Objetos del juego ─────────────────────────────────────────────────────────
pc = Pacman(matrix, MC, XPxToMC, YPxToMC)

# Blinky — esquina inferior-derecha, dirección inicial 2 (abajo)
blinky = Blinky(matrix, MC, XPxToMC, YPxToMC, 378, 380, 2)

# Pinky — esquina superior-derecha, dirección inicial 0 (arriba)
pinky = Pinky(matrix, MC, XPxToMC, YPxToMC, 378, 20, 0)

# Fantasmas aleatorios restantes
ghosts = []
ghosts.append(Ghost(matrix, MC, XPxToMC, YPxToMC, 20, 380, 3, 0))
ghosts.append(Ghost(matrix, MC, XPxToMC, YPxToMC, 20,  20, 1, 0))

MAP_SIZE    = 400
SPRITE_HALF = 18

textures = []

# ── Carga de textura ──────────────────────────────────────────────────────────
def load_texture(filepath, use_colorkey=False):
    tid = glGenTextures(1)
    textures.append(tid)
    glBindTexture(GL_TEXTURE_2D, tid)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
    image = pygame.image.load(filepath).convert()
    if use_colorkey:
        image.set_colorkey((0, 0, 0), pygame.RLEACCEL)
        image = image.convert_alpha()
    w, h       = image.get_rect().size
    image_data = pygame.image.tostring(image, "RGBA")
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, w, h, 0, GL_RGBA,
                 GL_UNSIGNED_BYTE, image_data)
    glGenerateMipmap(GL_TEXTURE_2D)

# ── Inicialización OpenGL ─────────────────────────────────────────────────────
def Init():
    pygame.init()
    pygame.display.set_mode((screen_width, screen_height), DOUBLEBUF | OPENGL)
    pygame.display.set_caption("Pac-Man Clásico")

    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    glOrtho(0, MAP_SIZE, MAP_SIZE, 0, -1, 1)

    glMatrixMode(GL_MODELVIEW)
    glLoadIdentity()

    glClearColor(0, 0, 0, 1)
    glDisable(GL_DEPTH_TEST)
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

    load_texture(file_map,   use_colorkey=False)  # textures[0] mapa
    load_texture(img_ghost1, use_colorkey=True)   # textures[1] Blinky (rojo)
    load_texture(img_ghost2, use_colorkey=True)   # textures[2] Pinky  (rosa)
    load_texture(img_pacman, use_colorkey=True)   # textures[3] Pac-Man
    load_texture(img_ghost3, use_colorkey=True)   # textures[4] fantasma aleatorio 1
    load_texture(img_ghost4, use_colorkey=True)   # textures[5] fantasma aleatorio 2

    blinky.loadTextures(textures, 5)
    pinky.loadTextures(textures, 4)
    pc.loadTextures(textures, 3)
    ghosts[0].loadTextures(textures, 1)
    ghosts[1].loadTextures(textures, 2)

# ── Dibujo del mapa ───────────────────────────────────────────────────────────
def draw_map():
    glColor4f(1, 1, 1, 1)
    glEnable(GL_TEXTURE_2D)
    glBindTexture(GL_TEXTURE_2D, textures[0])
    glBegin(GL_QUADS)
    glTexCoord2f(0, 0); glVertex2f(0,        0)
    glTexCoord2f(1, 0); glVertex2f(MAP_SIZE, 0)
    glTexCoord2f(1, 1); glVertex2f(MAP_SIZE, MAP_SIZE)
    glTexCoord2f(0, 1); glVertex2f(0,        MAP_SIZE)
    glEnd()
    glDisable(GL_TEXTURE_2D)

# ── Dibujo de un sprite ───────────────────────────────────────────────────────
def draw_sprite(tex_id, x, z):
    h = SPRITE_HALF
    glColor4f(1, 1, 1, 1)
    glEnable(GL_TEXTURE_2D)
    glBindTexture(GL_TEXTURE_2D, tex_id)
    glBegin(GL_QUADS)
    glTexCoord2f(0, 0); glVertex2f(x - h, z - h)
    glTexCoord2f(1, 0); glVertex2f(x + h, z - h)
    glTexCoord2f(1, 1); glVertex2f(x + h, z + h)
    glTexCoord2f(0, 1); glVertex2f(x - h, z + h)
    glEnd()
    glDisable(GL_TEXTURE_2D)

# ── Frame ─────────────────────────────────────────────────────────────────────
def display():
    glClear(GL_COLOR_BUFFER_BIT)
    draw_map()

    # Blinky — update2 recibe solo la posición (compatibilidad original)
    blinky.update2(pc.position)
    draw_sprite(textures[blinky.Id], blinky.position[0], blinky.position[2])

    # Pinky — update2 recibe el objeto Pacman completo (necesita .direction)
    pinky.update2(pc)
    draw_sprite(textures[pinky.Id], pinky.position[0], pinky.position[2])

    # Fantasmas aleatorios
    for g in ghosts:
        g.update2(pc.position)
        draw_sprite(textures[g.Id], g.position[0], g.position[2])

    # Pac-Man siempre al frente
    draw_sprite(textures[pc.Id], pc.position[0], pc.position[2])

# ── Main loop ─────────────────────────────────────────────────────────────────
Init()
clock = pygame.time.Clock()
done  = False

while not done:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            done = True
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                done = True

    keys = pygame.key.get_pressed()
    if   keys[pygame.K_w] or keys[pygame.K_UP]:
        pc.update(0)
    elif keys[pygame.K_d] or keys[pygame.K_RIGHT]:
        pc.update(1)
    elif keys[pygame.K_s] or keys[pygame.K_DOWN]:
        pc.update(2)
    elif keys[pygame.K_a] or keys[pygame.K_LEFT]:
        pc.update(3)
    else:
        pc.update(-1)

    display()
    pygame.display.flip()
    clock.tick(60)

pygame.quit()