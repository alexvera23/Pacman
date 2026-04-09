import random
from Ghost import Ghost


class Blinky(Ghost):
    """
    Blinky (fantasma rojo) — persigue a Pac-Man.

    Reglas de movimiento heredadas de Ghost:
      - Solo puede cambiar de dirección en intersecciones válidas.
      - No puede regresar por el camino por el que llegó (sin rebote).

    Estrategia de persecución:
      En cada intersección, de las direcciones disponibles (sin la inversa),
      elige la que más acerca a Blinky a la posición actual de Pac-Man.
      Si hay empate en distancia, elige aleatoriamente entre las empatadas
      para que el comportamiento no sea perfectamente predecible.
    """

    CATCH_THRESHOLD = 20   # distancia Manhattan (px) para considerar captura

    def __init__(self, mapa, mc, x_mc, y_mc, xini, yini, dir_ini):
        # tipo=0 para heredar la infraestructura de Ghost sin activar path-finding
        super().__init__(mapa, mc, x_mc, y_mc, xini, yini, dir_ini, tipo=0)

    # ── Lógica de intersección ────────────────────────────────────────────────
    def _chase(self, pacmanXY):
        """
        Reemplaza interseccion_random() con una elección dirigida.
        pacmanXY = pc.position = [px, py_altura, pz]
        """
        # Posición actual de Blinky en píxeles
        bx = self.position[0]
        bz = self.position[2]

        # Posición de Pac-Man (índices 0 y 2, igual que Blinky)
        px = pacmanXY[0]
        pz = pacmanXY[2]

        # Determinar celda de control actual
        self.positionMC[0] = self.XPxToMC[bx - 20]
        self.positionMC[1] = self.YPxToMC[bz - 20]
        celId = self.MC[self.positionMC[1]][self.positionMC[0]]

        # Obtener las opciones de dirección para esta celda (igual que el padre)
        options_map = {
            0:  [self.direction],
            10: [1, 2],
            11: [2, 3],
            12: [0, 1],
            13: [0, 3],
            21: [1, 2, 3],
            22: [0, 2, 3],
            23: [0, 1, 3],
            24: [0, 1, 2],
            25: [0, 1, 2, 3],
            26: [1],
            27: [3],
        }
        available = list(options_map.get(celId, [self.direction]))

        # Calcular dirección inversa y eliminarla (no regresar)
        inv = {0: 2, 1: 3, 2: 0, 3: 1}[self.direction]
        if celId not in (0, 26, 27) and inv in available:
            available.remove(inv)

        # Deltas de posición para cada dirección
        # 0=arriba(z-), 1=derecha(x+), 2=abajo(z+), 3=izquierda(x-)
        delta = {0: (0, -1), 1: (1, 0), 2: (0, 1), 3: (-1, 0)}

        # Elegir la dirección que minimiza la distancia Manhattan a Pac-Man
        best_dirs = []
        best_dist = float('inf')

        for d in available:
            dx, dz = delta[d]
            new_x = bx + dx
            new_z = bz + dz
            dist  = abs(new_x - px) + abs(new_z - pz)

            if dist < best_dist:
                best_dist  = dist
                best_dirs  = [d]
            elif dist == best_dist:
                best_dirs.append(d)

        # Desempate aleatorio (comportamiento menos predecible)
        chosen = random.choice(best_dirs)
        self.direction = chosen

        # Mover un paso en la dirección elegida
        if chosen == 0:
            self.position[2] -= 1
        elif chosen == 1:
            self.position[0] += 1
        elif chosen == 2:
            self.position[2] += 1
        elif chosen == 3:
            self.position[0] -= 1

        # Restaurar la opción inversa para la próxima intersección
        if celId not in (0, 26, 27) and inv not in available:
            available.append(inv)

    # ── Update principal ──────────────────────────────────────────────────────
    def update2(self, pacmanXY):
        """
        Se llama cada frame desde main.
        - En intersección: _chase() decide la dirección óptima hacia Pac-Man.
        - Fuera de intersección: sigue_adelante() avanza un paso en la misma dir.
        """
        en_interseccion = (
            self.YPxToMC[self.position[2] - 20] != -1 and
            self.XPxToMC[self.position[0] - 20] != -1
        )

        if en_interseccion:
            self._chase(pacmanXY)
        else:
            self.sigue_adelante()

        # ── Detección de captura ──────────────────────────────────────────────
        dist = abs(self.position[0] - pacmanXY[0]) + abs(self.position[2] - pacmanXY[2])
        if dist < self.CATCH_THRESHOLD:
            print(f"[BLINKY] ¡Atrapó a Pac-Man! "
                  f"[Blinky=({self.position[0]},{self.position[2]}) "
                  f"Pacman=({pacmanXY[0]},{pacmanXY[2]}) "
                  f"dist={dist}px]")