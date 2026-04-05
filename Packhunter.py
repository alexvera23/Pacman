"""
PackHunter.py — Clase base para Inky y Clyde (caza en manada).

Función de evaluación socio-céntrica H(S):
  · Componente 1: Presión por centroide distribuido
        Minimiza dist(centroide{Gi,Gc}, P*)  donde P* es la posición
        futura estimada de Pac-Man (lookahead en su dirección).
  · Componente 2: Efecto pinza (cobertura angular)
        Penaliza que ambos fantasmas estén muy cerca entre sí cuando se
        acercan a Pac-Man; los obliga a llegar por pasillos distintos.
  · Bono de movilidad
        Favorece celdas MC con más salidas para no quedar encañonado.

Pesos elegidos:
  W_CENTROID = 1.0  → prioridad máxima: reducir distancia al objetivo.
  W_OVERLAP  = 2.5  → penalización alta: evitar solapamiento entre cazadores.
  W_MOBILITY = 0.3  → bono suave: moverse hacia intersecciones ricas.

Tres estrategias complementarias:
  1. Move Ordering  — ordena candidatos por heurística rápida antes de
                      evaluar H(S) completo (explora primero lo mejor).
  2. Quiescence     — detecta oscilación A→B→A y añade penalización extra.
  3. Tabu K-FIFO    — cola FIFO de tamaño K; descarta posiciones MC
                      recientemente visitadas para forzar exploración.
"""

from collections import deque
from Ghost import Ghost


class PackHunter(Ghost):

    # ── Pesos de H(S) ──────────────────────────────────────────────────────
    W_CENTROID = 1.0    # reducir distancia centroide → P*
    W_OVERLAP  = 2.5    # penalización alta por solapamiento
    W_MOBILITY = 0.3    # bono por movilidad

    # ── Parámetros Tabu ────────────────────────────────────────────────────
    TABU_K = 5          # tamaño de la cola FIFO de posiciones MC

    # ── Parámetros Quiescence ──────────────────────────────────────────────
    OSC_PENALTY = 500   # costo extra al detectar patrón oscilatorio A→B→A
    HIST_LEN    = 4     # posiciones MC que se recuerdan para detectar oscilación

    # ── Look-ahead para P* ─────────────────────────────────────────────────
    PAC_LOOKAHEAD = 40  # píxeles delante de Pac-Man que define P*

    # ── Umbrales para el efecto pinza ──────────────────────────────────────
    PINZA_PROXIMITY = 120  # radio centroide↔Pac-Man que activa la penalización
    PINZA_RADIUS    = 60   # distancia mínima deseable entre los dos fantasmas

    # ── Dirección → delta en espacio MC (col, fila) ────────────────────────
    DIR_DELTA = {0: (0, -1), 1: (1, 0), 2: (0, 1), 3: (-1, 0)}
    DIR_INV   = {0: 2, 1: 3, 2: 0, 3: 1}

    # ── celId → lista de direcciones disponibles ───────────────────────────
    CEL_DIRS = {
        0:  [],              # falsa intersección: continuar recto
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

    # ══════════════════════════════════════════════════════════════════════════
    def __init__(self, mapa, mc, x_mc, y_mc, xini, yini, direction):
        # tipo=1 para que la clase base Ghost use path_ia si se llama a su update2
        super().__init__(mapa, mc, x_mc, y_mc, xini, yini, direction, tipo=1)

        self.partner = None   # referencia al otro PackHunter; asignar con set_partner()

        # Ghost.sigue_adelante() incrementa path_n cuando tipo==1;
        # lo inicializamos aquí para evitar AttributeError.
        self.path_n = 0

        # Cola FIFO Tabu — últimas K posiciones MC visitadas
        self.tabu = deque(maxlen=self.TABU_K)

        # Historial de posiciones MC para detectar oscilación (Quiescence)
        self.pos_history = deque(maxlen=self.HIST_LEN)

        # Tabla inversa MC_index → coordenada píxel real (incluye +20 del offset de mapa)
        self.MCToXPx = self._build_reverse(x_mc)
        self.MCToYPx = self._build_reverse(y_mc)

    # ══════════════════════════════════════════════════════════════════════════
    # Utilidades internas
    # ══════════════════════════════════════════════════════════════════════════

    @staticmethod
    def _build_reverse(arr):
        """
        Construye la tabla inversa MC_index (0-9) → coordenada píxel real.
        'arr' es XPxToMC o YPxToMC (longitud ≤ 361, valores -1 ó 0..9).
        El desplazamiento +20 reproduce el offset de inicio del mapa.
        """
        rev = [-1] * 10
        for offset, mc in enumerate(arr):
            if mc != -1 and 0 <= mc < 10:
                rev[mc] = offset + 20
        return rev

    def _mc_to_px(self, mx, mz):
        """Convierte índices MC (columna, fila) a coordenadas píxel (x, z).
        Devuelve (None, None) si las coordenadas están fuera del rango."""
        if 0 <= mx < 10 and 0 <= mz < 10:
            return self.MCToXPx[mx], self.MCToYPx[mz]
        return None, None

    def _get_dirs(self, celId):
        """Devuelve una copia de las direcciones disponibles para celId."""
        return list(self.CEL_DIRS.get(celId, []))

    def _next_mc(self, mx, mz, d):
        """Coordenadas MC del siguiente paso en dirección d."""
        dmx, dmz = self.DIR_DELTA[d]
        return mx + dmx, mz + dmz

    def _pressure_point(self, pacman):
        """
        P* = posición actual de Pac-Man + vector dirección × PAC_LOOKAHEAD píxeles.
        Representa el punto 'estratégico' al que deben converger los cazadores.
        """
        dvx, dvz = self.DIR_DELTA.get(pacman.direction, (0, 0))
        return (pacman.position[0] + dvx * self.PAC_LOOKAHEAD,
                pacman.position[2] + dvz * self.PAC_LOOKAHEAD)

    def set_partner(self, partner):
        """Vincula al compañero de caza. Llamar desde main.py tras instanciar ambos."""
        self.partner = partner

    # ══════════════════════════════════════════════════════════════════════════
    # Función de evaluación socio-céntrica H(S)
    # ══════════════════════════════════════════════════════════════════════════

    def _eval_H(self, cand_mx, cand_mz, pacman):
        """
        Evalúa H(S) asumiendo que ESTE fantasma se mueve a (cand_mx, cand_mz).

        S = { posición candidata de este fantasma,
              posición actual del compañero,
              estado de Pac-Man }

        Retorna un escalar: MENOR → MEJOR.
        """
        my_px, my_pz = self._mc_to_px(cand_mx, cand_mz)
        if my_px is None:
            return float('inf')

        # Posición del compañero de caza (píxeles)
        if self.partner is not None:
            par_px = self.partner.position[0]
            par_pz = self.partner.position[2]
        else:
            # Sin compañero: actuar solo (degrada a persecución de centroide)
            par_px, par_pz = my_px, my_pz

        pac_px = pacman.position[0]
        pac_pz = pacman.position[2]

        # ── Componente 1: presión por centroide distribuido ────────────────
        # Minimizar dist(centroide, P*) — ambos fantasmas "empujan" hacia P*
        ps_x, ps_z = self._pressure_point(pacman)
        cx = (my_px + par_px) / 2.0      # centroide X
        cz = (my_pz + par_pz) / 2.0      # centroide Z
        d_centroid = abs(cx - ps_x) + abs(cz - ps_z)

        # ── Componente 2: efecto pinza (cobertura angular) ─────────────────
        # Penalizar que los dos fantasmas estén muy cerca cuando acorralan
        d_pac    = abs(cx - pac_px) + abs(cz - pac_pz)  # centroide ↔ Pac-Man
        d_ghosts = abs(my_px - par_px) + abs(my_pz - par_pz)  # dist. entre cazadores
        if d_pac < self.PINZA_PROXIMITY:
            # Solapamiento: penalizar si están más cerca que PINZA_RADIUS
            overlap_penalty = max(0.0, self.PINZA_RADIUS - d_ghosts)
        else:
            overlap_penalty = 0.0

        # ── Bono de movilidad ──────────────────────────────────────────────
        # Más salidas disponibles en la celda candidata → mejor posición táctica
        if 0 <= cand_mz < 10 and 0 <= cand_mx < 10:
            celId = self.MC[cand_mz][cand_mx]
        else:
            celId = 0
        mobility = len(self._get_dirs(celId))

        H = (self.W_CENTROID * d_centroid
             + self.W_OVERLAP  * overlap_penalty
             - self.W_MOBILITY * mobility)
        return H

    # ══════════════════════════════════════════════════════════════════════════
    # Estrategia 1 — Tabu con horizonte limitado
    # ══════════════════════════════════════════════════════════════════════════

    def _apply_tabu(self, candidates, mx, mz):
        """
        Descarta direcciones candidatas cuyo destino MC aparezca en la cola Tabu.
        Si todas las opciones son tabú (callejón sin salida), el filtro se ignora
        para no bloquear al fantasma.
        """
        filtered = [d for d in candidates
                    if self._next_mc(mx, mz, d) not in self.tabu]
        return filtered if filtered else candidates   # fallback: ignorar Tabu

    # ══════════════════════════════════════════════════════════════════════════
    # Estrategia 2 — Quiescence Search (Búsqueda del Reposo)
    # ══════════════════════════════════════════════════════════════════════════

    def _quiescence_cost(self, next_mx, next_mz):
        """
        Devuelve OSC_PENALTY si la celda candidata ya aparece en el historial
        de posiciones recientes, detectando el patrón de oscilación A→B→A.
        Esto penaliza los movimientos que llevan al fantasma a "rebotar".
        """
        if (next_mx, next_mz) in self.pos_history:
            return self.OSC_PENALTY
        return 0.0

    # ══════════════════════════════════════════════════════════════════════════
    # Estrategia 3 — Move Ordering (Búsqueda Sesgada)
    # ══════════════════════════════════════════════════════════════════════════

    def _order_moves(self, candidates, mx, mz, pacman):
        """
        Ordena los movimientos candidatos de MEJOR a PEOR mediante una
        heurística rápida (distancia Manhattan del siguiente MC a P*).

        El orden garantiza que la evaluación completa de H(S) explore primero
        las opciones más prometedoras, maximizando la calidad de la decisión
        cuando el número de candidatos es alto.  En un árbol minimax equivale
        al 'move ordering' que mejora la eficacia de la poda alfa-beta.
        """
        ps_x, ps_z = self._pressure_point(pacman)

        def quick_h(d):
            nmx, nmz = self._next_mc(mx, mz, d)
            px, pz   = self._mc_to_px(nmx, nmz)
            if px is None:
                return float('inf')
            return abs(px - ps_x) + abs(pz - ps_z)

        return sorted(candidates, key=quick_h)

    # ══════════════════════════════════════════════════════════════════════════
    # Lógica de decisión en intersección
    # ══════════════════════════════════════════════════════════════════════════

    def path_ia(self, pacman):
        """
        Núcleo de la IA.  Se ejecuta cada vez que el fantasma alcanza una
        intersección válida (tanto XPxToMC como YPxToMC son != -1).

        Flujo:
          1. Actualiza posición MC.
          2. Obtiene direcciones disponibles y elimina la inversa (no retroceder).
          3. [Tabu]         Descarta posiciones MC recientemente visitadas.
          4. [Move Ordering] Ordena candidatos por heurística rápida.
          5. [H(S)+Quiescence] Evalúa cada candidato y elige el menor costo.
          6. Mueve un píxel en la dirección elegida.
          7. Registra la posición actual en Tabu e historial.
        """
        # ── 1. Actualizar posición MC ──────────────────────────────────────
        self.positionMC[0] = self.XPxToMC[self.position[0] - 20]
        self.positionMC[1] = self.YPxToMC[self.position[2] - 20]
        mx    = self.positionMC[0]
        mz    = self.positionMC[1]
        celId = self.MC[mz][mx]

        # Falsa intersección (celId 0): continuar recto sin tomar decisión
        if celId == 0:
            self.sigue_adelante()
            return

        # ── 2. Direcciones disponibles y eliminación de la inversa ─────────
        available = self._get_dirs(celId)
        if not available:
            self.sigue_adelante()
            return

        dir_inv = self.DIR_INV.get(self.direction, -1)
        if dir_inv in available and len(available) > 1:
            available.remove(dir_inv)
        if not available:  # caso límite: solo tenía la inversa
            available = self._get_dirs(celId)

        # ── 3. Estrategia Tabu: filtrar destinos recientes ─────────────────
        candidates = self._apply_tabu(available, mx, mz)

        # ── 4. Move Ordering: ordenar de más a menos prometedor ─────────────
        candidates = self._order_moves(candidates, mx, mz, pacman)

        # ── 5. Evaluar H(S) + penalización Quiescence ─────────────────────
        best_dir   = candidates[0]   # default: el mejor según move ordering
        best_score = float('inf')

        for d in candidates:
            nmx, nmz = self._next_mc(mx, mz, d)
            score  = self._eval_H(nmx, nmz, pacman)     # H(S) socio-céntrico
            score += self._quiescence_cost(nmx, nmz)    # penalización oscilación
            if score < best_score:
                best_score = score
                best_dir   = d

        # ── 6. Registrar en Tabu e historial antes de moverse ─────────────
        self.tabu.append((mx, mz))
        self.pos_history.append((mx, mz))

        # ── 7. Ejecutar movimiento (1 píxel) ──────────────────────────────
        self.direction = best_dir
        if best_dir == 0:
            self.position[2] -= 1
        elif best_dir == 1:
            self.position[0] += 1
        elif best_dir == 2:
            self.position[2] += 1
        elif best_dir == 3:
            self.position[0] -= 1

    # ══════════════════════════════════════════════════════════════════════════
    # update2: reemplaza al de Ghost para recibir el objeto Pacman completo
    #Hola 
    # ══════════════════════════════════════════════════════════════════════════

    def update2(self, pacman):
        """
        Recibe el objeto Pacman completo (no solo la posición) para poder leer
        pacman.direction, necesario para calcular P*.
        """
        px_off = self.position[0] - 20
        pz_off = self.position[2] - 20
        x_ok = (0 <= px_off < len(self.XPxToMC)) and (self.XPxToMC[px_off] != -1)
        z_ok = (0 <= pz_off < len(self.YPxToMC)) and (self.YPxToMC[pz_off] != -1)

        if x_ok and z_ok:
            self.path_ia(pacman)
        else:
            self.sigue_adelante()