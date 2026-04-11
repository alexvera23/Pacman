import random
from collections import deque
from Ghost import Ghost


class Pinky(Ghost):
    """
    Pinky (fantasma rosa) — emboscada con poda alfa-beta.
    """

    # ── Pesos de la función de evaluación ────────────────────────────────────
    W_DIST      = 1.0    # distancia al target (factor primario)
    W_MOB_4     = 12.0   # bono por intersección con 4 salidas  (celId 25)
    W_MOB_3     = 9.0    # bono por intersección con 3 salidas  (celId 21-24)
    W_MOB_2     = 3.0    # bono por esquina / 2 salidas         (celId 10-13)
    W_TABU      = 300.0  # penalización por posición tabú
                         #  de distancia grande; evita que alfa-beta recomiende
                         #  volver a una celda recientemente visitada)

    # ── Parámetros del algoritmo ──────────────────────────────────────────────
    DEPTH          = 4    # profundidad de búsqueda en el árbol
    CELL_PX        = 40   # píxeles por "celda" para el vector de anticipación
    AHEAD_CELLS    = 4    # celdas de anticipación máximas delante de Pacman
    TABU_HORIZON   = 6    # últimas N intersecciones que Pinky evitará
    QUIESCE_THRESH = 60   # distancia Manhattan para activar quiescence search
    QUIESCE_EXT    = 2    # niveles extra máximos de quiescence

    # ── Anticipación dinámica ─────────────────────────────────────────────────
    IDLE_GRACE = 45       # frames quietos tras los cuales el lookahead es 0.
                          # A 60 fps ≈ 0.75 s de quietud → persecución directa.

    # Deltas de posición: 0=arriba(z-), 1=derecha(x+), 2=abajo(z+), 3=izquierda(x-)
    _DELTA = {0: (0, -1), 1: (1, 0), 2: (0, 1), 3: (-1, 0)}
    _INV   = {0: 2, 1: 3, 2: 0, 3: 1}

    # Tabla celId → lista de direcciones posibles
    _OPTIONS_MAP = {
        0:  None,                  # pseudo-intersección: se maneja aparte
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

    # ── Estados de Pinky ─────────────────────────────────────────────────────
    HUNTING = 'CAZANDO'
    CAUGHT  = 'ATRAPADO'

    # Distancia Manhattan (px) para considerar que Pinky alcanzó a Pacman
    CATCH_THRESHOLD = 20

    # Frames de espera tras atrapar a Pacman antes de volver a cazar (60 fps → 3 s)
    WAIT_FRAMES = 180

    def __init__(self, mapa, mc, x_mc, y_mc, xini, yini, dir_ini):
        super().__init__(mapa, mc, x_mc, y_mc, xini, yini, dir_ini, tipo=0)
        # Historial tabú: deque con capacidad TABU_HORIZON
        self._tabu = deque(maxlen=self.TABU_HORIZON)

        # ── Máquina de estados ────────────────────────────────────────────────
        self._state = self.HUNTING

        # Contador de frames de espera tras atrapar a Pacman
        self._wait_counter = 0

        # Evitar spam en consola: solo imprime cuando el estado cambia
        self._last_printed_state = None

        # ── Anticipación dinámica ─────────────────────────────────────────────
        self._pac_last_pos    = None  # (x, z) de Pacman en el frame anterior
        self._pac_idle_frames = 0     # frames consecutivos sin movimiento
        self._current_ahead   = self.AHEAD_CELLS  # lookahead efectivo [0, AHEAD_CELLS]

    # =========================================================================
    # Utilidades del laberinto
    # =========================================================================

    def _cel_id(self, x, z):
        """
        Devuelve el celId de la Matriz de Control para la posición (x, z).
        Retorna -1 si (x, z) no es una intersección válida.
        """
        xi, zi = x - 20, z - 20
        if xi < 0 or xi >= len(self.XPxToMC):
            return -1
        if zi < 0 or zi >= len(self.YPxToMC):
            return -1
        cx = self.XPxToMC[xi]
        cz = self.YPxToMC[zi]
        if cx == -1 or cz == -1:
            return -1
        return self.MC[cz][cx]

    def _get_options(self, x, z, came_from):
        """
        Devuelve las direcciones válidas en la intersección (x, z),
        excluyendo la dirección inversa a `came_from` (regla: sin rebote).
        """
        cel_id = self._cel_id(x, z)
        if cel_id == -1:
            return [came_from]

        if cel_id == 0:
            return [came_from]

        opts = list(self._OPTIONS_MAP.get(cel_id, [came_from]))
        inv  = self._INV[came_from]

        if cel_id not in (0, 26, 27) and inv in opts:
            opts.remove(inv)

        return opts if opts else [came_from]

    def _walk_to_next(self, x, z, direction):
        """
        Simula el avance píxel a píxel desde (x, z) en `direction`
        hasta llegar a la siguiente intersección válida.
        Retorna (nx, nz) o None si sale del mapa antes de encontrarla.
        """
        dx, dz = self._DELTA[direction]
        cx, cz = x + dx, z + dz

        for _ in range(250):
            xi, zi = cx - 20, cz - 20
            if xi < 0 or xi >= len(self.XPxToMC):
                return None
            if zi < 0 or zi >= len(self.YPxToMC):
                return None
            if self.XPxToMC[xi] != -1 and self.YPxToMC[zi] != -1:
                return (cx, cz)
            cx += dx
            cz += dz

        return None

    # =========================================================================
    # Función de evaluación
    # =========================================================================

    def _mobility_bonus(self, cel_id):
        """
        Componente 2 — Heurística de movilidad:
        Premia estar en intersecciones con más salidas disponibles.
        """
        if cel_id == 25:                   # 4 salidas
            return self.W_MOB_4
        if cel_id in (21, 22, 23, 24):     # 3 salidas
            return self.W_MOB_3
        if cel_id in (10, 11, 12, 13):     # 2 salidas (esquina)
            return self.W_MOB_2
        return 0.0

    def _evaluate(self, px, pz, tx, tz, cel_id, tabu_set):
        """
        Evalúa el estado desde la perspectiva de Pinky.
        Valor más alto = mejor para Pinky.

        Componentes:
          · Distancia al target      → factor primario (escala W_DIST)
          · Bono de movilidad        → factor secundario significativo
          · Penalización tabú        → anti-ciclado (W_TABU=300, fuerte)
        """
        dist  = abs(px - tx) + abs(pz - tz)
        score = -dist * self.W_DIST
        score += self._mobility_bonus(cel_id)
        if (px, pz) in tabu_set:
            score -= self.W_TABU
        return score

    def _get_target(self, pac_x, pac_z, pac_dir):
        """
        Componente 1 — Anticipación cinemática dinámica (Emboscada):

        Calcula el target = `_current_ahead` celdas por delante de Pacman.

        Esto evita el efecto horizonte estático: cuando Pacman se para,
        el target ficticio que estaba 4 celdas adelante desaparece y los
        fantasmas persiguen directamente su posición real.
        """
        dx, dz = self._DELTA[pac_dir]
        tx = pac_x + dx * self._current_ahead * self.CELL_PX
        tz = pac_z + dz * self._current_ahead * self.CELL_PX
        # Clamp dentro de los límites del mapa
        tx = max(20, min(378, tx))
        tz = max(20, min(380, tz))
        return tx, tz

    # =========================================================================
    # Poda Alfa-Beta con las 3 mejoras
    # =========================================================================

    def _alpha_beta(self,
                    px, pz, p_dir,        # estado Pinky
                    qx, qz, q_dir,        # estado Pacman
                    depth, alpha, beta,
                    is_max,
                    tx, tz,               # target actual
                    tabu_set,
                    q_ext):               # extensiones quiescence restantes
        """
        Árbol alfa-beta de profundidad `depth`.

        Nodos MAX : Pinky elige la mejor dirección.
        Nodos MIN : Pacman elige la peor dirección para Pinky (huida).
        """
        cel_id = self._cel_id(px, pz)

        # ── Mejora 3: Quiescence Search ──────────────────────────────────────
        # Si llegamos a profundidad 0 pero la situación es "inestable"
        # (Pinky muy cerca del target), extendemos para evitar el efecto
        # horizonte: una decisión aparentemente buena que colapsa en el
        # siguiente nivel.
        if depth == 0:
            dist = abs(px - tx) + abs(pz - tz)
            if dist < self.QUIESCE_THRESH and q_ext > 0:
                # Extender un nivel más
                depth  = 1
                q_ext -= 1
            else:
                return self._evaluate(px, pz, tx, tz, cel_id, tabu_set)

        # ── Generación de movimientos ────────────────────────────────────────
        if is_max:
            candidates = self._get_options(px, pz, p_dir)
        else:
            candidates = self._get_options(qx, qz, q_dir)

        if not candidates:
            return self._evaluate(px, pz, tx, tz, cel_id, tabu_set)

        # ── Mejora 2: Move Ordering (Búsqueda Sesgada) ───────────────────────
        # Evaluación superficial (sin recursión) de cada movimiento candidato.
        # Ordenar: MAX → mejores primero (↓ α),  MIN → peores primero (↑ β).
        # Esto coloca los movimientos más prometedores al frente del árbol,
        # maximizando las podas α y β.
        def shallow_score(d):
            if is_max:
                nxt = self._walk_to_next(px, pz, d)
                if nxt is None:
                    return -9999.0
                nx, nz = nxt
                return self._evaluate(nx, nz, tx, tz, self._cel_id(nx, nz), tabu_set)
            else:
                # Para MIN estimamos cuánto aleja a Pacman de Pinky
                nxt = self._walk_to_next(qx, qz, d)
                if nxt is None:
                    return 9999.0
                nx, nz = nxt
                return -(abs(px - nx) + abs(pz - nz))  # más lejos = peor para Pinky

        candidates.sort(key=shallow_score, reverse=is_max)

        # ── Recursión ────────────────────────────────────────────────────────
        if is_max:
            best = -float('inf')
            for d in candidates:
                nxt = self._walk_to_next(px, pz, d)
                if nxt is None:
                    continue
                nx, nz = nxt

                # Mejora 1: Tabú — la nueva posición se añade al conjunto tabú
                # del hijo, de modo que Pinky no vuelva a pasar por aquí en
                # el resto de esta rama de búsqueda.
                child_tabu = tabu_set | {(nx, nz)}

                val = self._alpha_beta(
                    nx, nz, d,
                    qx, qz, q_dir,
                    depth - 1, alpha, beta, False,
                    tx, tz, child_tabu, q_ext
                )
                if val > best:
                    best = val
                alpha = max(alpha, best)
                if beta <= alpha:
                    break   # ✂ poda β

            return best if best > -float('inf') else \
                   self._evaluate(px, pz, tx, tz, cel_id, tabu_set)

        else:  # MIN — turno de Pacman
            best = float('inf')
            for d in candidates:
                nxt = self._walk_to_next(qx, qz, d)
                if nxt is None:
                    continue
                nx, nz = nxt

                # El target se recalcula con la nueva dirección de Pacman.
                # _get_target usa self._current_ahead (ya actualizado en update2)
                # así el lookahead dinámico es consistente en todo el árbol.
                new_tx, new_tz = self._get_target(nx, nz, d)

                val = self._alpha_beta(
                    px, pz, p_dir,
                    nx, nz, d,
                    depth - 1, alpha, beta, True,
                    new_tx, new_tz, tabu_set, q_ext
                )
                if val < best:
                    best = val
                beta = min(beta, best)
                if beta <= alpha:
                    break   # ✂ poda α

            return best if best < float('inf') else \
                   self._evaluate(px, pz, tx, tz, cel_id, tabu_set)

    # =========================================================================
    # Decisión en intersección
    # =========================================================================

    def _decide(self, pac_x, pac_z, pac_dir):
        """
        Punto de entrada del algoritmo: evalúa todos los movimientos posibles
        en la intersección actual con alfa-beta y devuelve la mejor dirección.

        El target usa self._current_ahead (ya calculado en update2) para que
        el lookahead dinámico sea coherente con el estado actual de Pacman.
        """
        px, pz   = self.position[0], self.position[2]
        moves    = self._get_options(px, pz, self.direction)
        tx, tz   = self._get_target(pac_x, pac_z, pac_dir)

        # El conjunto tabú incluye las posiciones reales visitadas por Pinky
        # (self._tabu) para que alfa-beta las penalice (W_TABU=300) en toda
        # la búsqueda, no solo en la evaluación hoja.
        tabu_set = set(self._tabu)

        best_dir   = moves[0]
        best_score = -float('inf')

        for d in moves:
            nxt = self._walk_to_next(px, pz, d)
            if nxt is None:
                continue
            nx, nz     = nxt
            child_tabu = tabu_set | {(nx, nz)}

            score = self._alpha_beta(
                nx, nz, d,
                pac_x, pac_z, pac_dir,
                self.DEPTH - 1, -float('inf'), float('inf'), False,
                tx, tz, child_tabu, self.QUIESCE_EXT
            )
            if score > best_score:
                best_score = score
                best_dir   = d

        # Registrar posición actual en la lista tabú para futuros frames
        self._tabu.append((px, pz))
        return best_dir

    # =========================================================================
    # Consola — log de estado
    # =========================================================================

    def _log(self, msg):
        """Imprime en consola solo cuando el estado cambia."""
        if msg != self._last_printed_state:
            print(f"[PINKY] {msg}")
            self._last_printed_state = msg

    # =========================================================================
    # Update — llamado cada frame desde main
    # =========================================================================

    def update2(self, pacman):
        """
        Recibe el objeto Pacman completo (necesita position Y direction).

        Antes de la lógica de movimiento, actualiza el contador de quietud
        de Pacman y recalcula _current_ahead
        """
        pac_x   = pacman.position[0]
        pac_z   = pacman.position[2]
        pac_dir = pacman.direction

        # ── Anticipación dinámica: detectar si Pacman se movió ────────────────
        pac_now = (pac_x, pac_z)
        if pac_now == self._pac_last_pos:
            # Pacman quieto: acumular frames hasta IDLE_GRACE
            self._pac_idle_frames = min(self._pac_idle_frames + 1, self.IDLE_GRACE)
        else:
            # Pacman se movió: resetear contador
            self._pac_idle_frames = 0
            self._pac_last_pos    = pac_now

        # Lookahead escala linealmente de AHEAD_CELLS (0 idle) a 0 (IDLE_GRACE idle)
        idle_ratio            = self._pac_idle_frames / self.IDLE_GRACE
        self._current_ahead   = int(self.AHEAD_CELLS * (1.0 - idle_ratio))

        # ── Distancia Manhattan actual entre Pinky y Pacman ───────────────────
        dist = abs(self.position[0] - pac_x) + abs(self.position[2] - pac_z)

        # ── Transiciones de estado ────────────────────────────────────────────
        if self._state == self.HUNTING:
            if dist < self.CATCH_THRESHOLD:
                self._state        = self.CAUGHT
                self._wait_counter = self.WAIT_FRAMES
                self._log(
                    f"¡Atrapó a Pac-Man! Esperando {self.WAIT_FRAMES} frames "
                    f"[Pinky=({self.position[0]},{self.position[2]}) "
                    f"Pacman=({pac_x},{pac_z}) dist={dist}px]"
                )

        elif self._state == self.CAUGHT:
            self._wait_counter -= 1
            frames_seg = self._wait_counter / 60
            # self._log(
            #     f"Esperando... {self._wait_counter} frames ({frames_seg:.1f}s) "
            #     f"para reanudar la caza"
            # )
            if self._wait_counter <= 0:
                self._state = self.HUNTING
                self._tabu.clear()   # tabú limpio para una caza fresca
                # self._log(
                #     f"¡Reanudando caza! "
                #     f"[Pinky=({self.position[0]},{self.position[2]}) "
                #     f"Pacman=({pac_x},{pac_z})]"
                # )

        # ── Comportamiento según estado ───────────────────────────────────────
        if self._state == self.CAUGHT:
            # Pinky se queda quieta en su posición actual (no se mueve)
            pass

        else:  # HUNTING
            # ahead_info = (f"ahead={self._current_ahead}celdas"
            #               if self._current_ahead > 0 else "modo=DIRECTO")
            # self._log(
            #     f"Cazando — dist={dist}px | {ahead_info} | "
            #     f"idle={self._pac_idle_frames}f | "
            #     f"Pinky=({self.position[0]},{self.position[2]}) "
            #     f"target≈({pac_x + self._DELTA[pac_dir][0]*self._current_ahead*self.CELL_PX},"
            #     f"{pac_z + self._DELTA[pac_dir][1]*self._current_ahead*self.CELL_PX})"
            # )

            en_interseccion = (
                self.YPxToMC[self.position[2] - 20] != -1 and
                self.XPxToMC[self.position[0] - 20] != -1
            )

            if en_interseccion:
                chosen         = self._decide(pac_x, pac_z, pac_dir)
                self.direction = chosen
                dx, dz         = self._DELTA[chosen]
                self.position[0] += dx
                self.position[2] += dz
            else:
                self.sigue_adelante()