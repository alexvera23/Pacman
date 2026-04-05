import pygame
from pygame.locals import *

from OpenGL.GL import *
from OpenGL.GLU import *

import math
import os
import numpy as np
import pandas as pd
import random

class Ghost:
    def __init__(self, mapa, mc, x_mc, y_mc, xini, yini, dir, tipo):
        self.MC = mc
        self.XPxToMC = x_mc
        self.YPxToMC = y_mc
        self.mapa = mapa
        self.position = []
        self.position.append(xini)
        self.position.append(1)  # YPos
        self.position.append(yini)
        self.positionMC = []
        self.positionMC.append(self.XPxToMC[self.position[0] - 20])
        self.positionMC.append(self.YPxToMC[self.position[2] - 20])
        self.direction = dir
        self.tipo = tipo
        self.options = [
            [1, 2],       # 0  → celId 10
            [2, 3],       # 1  → celId 11
            [0, 1],       # 2  → celId 12
            [0, 3],       # 3  → celId 13
            [1, 2, 3],    # 4  → celId 21
            [0, 2, 3],    # 5  → celId 22
            [0, 1, 3],    # 6  → celId 23
            [0, 1, 2],    # 7  → celId 24
            [0, 1, 2, 3], # 8  → celId 25
            [1],          # 9  → celId 26
            [3],          # 10 → celId 27
        ]
        self.option = []
        self.dir_inv = 0

    def loadTextures(self, texturas, id):
        self.texturas = texturas
        self.Id = id

    def drawFace(self, x1, y1, z1, x2, y2, z2, x3, y3, z3, x4, y4, z4):
        glBegin(GL_QUADS)
        glTexCoord2f(0.0, 0.0)
        glVertex3f(x1, y1, z1)
        glTexCoord2f(0.0, 1.0)
        glVertex3f(x2, y2, z2)
        glTexCoord2f(1.0, 1.0)
        glVertex3f(x3, y3, z3)
        glTexCoord2f(1.0, 0.0)
        glVertex3f(x4, y4, z4)
        glEnd()

    def sigue_adelante(self):
        if self.direction == 0:
            self.position[2] -= 1
        elif self.direction == 1:
            self.position[0] += 1
        elif self.direction == 2:
            self.position[2] += 1
        else:
            self.position[0] -= 1
        if self.tipo == 1:
            self.path_n += 1

    def path_ia(self, pacmanXY):
        self.interseccion_random()

    def interseccion_random(self):
        self.positionMC[0] = self.XPxToMC[self.position[0] - 20]
        self.positionMC[1] = self.YPxToMC[self.position[2] - 20]
        celId = self.MC[self.positionMC[1]][self.positionMC[0]]

        if celId == 0:
            self.option = [self.direction]
        elif celId == 10:
            self.option = list(self.options[0])
        elif celId == 11:
            self.option = list(self.options[1])
        elif celId == 12:
            self.option = list(self.options[2])
        elif celId == 13:
            self.option = list(self.options[3])
        elif celId == 21:
            self.option = list(self.options[4])
        elif celId == 22:
            self.option = list(self.options[5])
        elif celId == 23:
            self.option = list(self.options[6])
        elif celId == 24:
            self.option = list(self.options[7])
        elif celId == 25:
            self.option = list(self.options[8])
        elif celId == 26:
            self.option = list(self.options[9])
        elif celId == 27:
            self.option = list(self.options[10])

        # Calcular dirección inversa
        if self.direction == 0:
            self.dir_inv = 2
        elif self.direction == 1:
            self.dir_inv = 3
        elif self.direction == 2:
            self.dir_inv = 0
        else:
            self.dir_inv = 1

        # ── FIX: solo eliminar dir_inv si realmente está en la lista ─────────
        # El original hacía remove() sin verificar, causando ValueError cuando
        # la celda solo admite una dirección (ej: celId 26 → solo [1]) y esa
        # dirección coincide con dir_inv (el fantasma venía de la derecha).
        if celId not in (0, 26, 27):
            if self.dir_inv in self.option:
                self.option.remove(self.dir_inv)

        # Si después de eliminar dir_inv la lista quedó vacía (caso borde),
        # permitir cualquier dirección disponible para la celda para no trabar.
        if not self.option:
            self.option = [self.direction]

        # Elegir dirección aleatoria entre las disponibles
        size = len(self.option)
        dir_rand = random.randint(0, size - 1)
        self.direction = self.option[dir_rand]

        if self.direction == 0:
            self.position[2] -= 1
        elif self.direction == 1:
            self.position[0] += 1
        elif self.direction == 2:
            self.position[2] += 1
        elif self.direction == 3:
            self.position[0] -= 1

        # Restaurar dir_inv en la lista para la próxima intersección
        if celId not in (0, 26, 27):
            if self.dir_inv not in self.option:
                self.option.append(self.dir_inv)

    def update2(self, pacmanXY):
        if ((self.YPxToMC[self.position[2] - 20] != -1) and
                (self.XPxToMC[self.position[0] - 20] != -1)):
            if self.tipo == 1:
                self.path_ia(pacmanXY)
            else:
                self.interseccion_random()
        else:
            self.sigue_adelante()

    def draw(self):
        glPushMatrix()
        glColor3f(1.0, 1.0, 1.0)
        glTranslatef(self.position[0], self.position[1], self.position[2])
        glScaled(10, 1, 10)
        glEnable(GL_TEXTURE_2D)
        glBindTexture(GL_TEXTURE_2D, self.texturas[self.Id])
        self.drawFace(-1.0, 1.0, -1.0, -1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, -1.0)
        glDisable(GL_TEXTURE_2D)
        glPopMatrix()