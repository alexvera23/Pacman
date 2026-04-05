"""
Clyde.py — Fantasma naranja, cazador de manada.

Hereda toda la lógica de PackHunter.  Su comportamiento se basa en la
función de evaluación socio-céntrica H(S) compartida con Inky: ninguno
de los dos persigue a Pac-Man de forma individual; en cambio, coordinan
sus posiciones para reducir las vías de escape del objetivo.

Posición sugerida (main.py): esquina superior-izquierda (20, 20), dir=1.
"""

from PackHunter import PackHunter


class Clyde(PackHunter):
    def __init__(self, mapa, mc, x_mc, y_mc, xini, yini, direction):
        super().__init__(mapa, mc, x_mc, y_mc, xini, yini, direction)