Pac-Man AI: Implementación de Poda Alfa-Beta y Caza en Manada

Este proyecto corresponde al Segundo Parcial de la asignatura Técnicas de Inteligencia Artificial. El objetivo principal es transformar el comportamiento básico de los fantasmas de Pac-Man en agentes inteligentes capaces de anticipar movimientos, colaborar entre sí y optimizar sus rutas mediante el algoritmo de búsqueda Poda Alfa-Beta y diversas heurísticas avanzadas.

 Características Principales

El sistema cuenta con cuatro personalidades distintas para los fantasmas, cada una basada en diferentes paradigmas de IA:

Blinky (Rojo) - Perseguidor Directo:

Utiliza una lógica Greedy (Voraz) basada en la Distancia de Manhattan.

En cada intersección, elige el camino que minimiza la distancia lineal al objetivo.

Pinky (Rosa) - Emboscada Inteligente:

Implementa Poda Alfa-Beta con una profundidad de 3 niveles.

Su objetivo es un punto proyectado 4 celdas por delante de Pac-Man.

Cuenta con Anticipación Dinámica: si Pac-Man se detiene, el objetivo colapsa hacia la posición real del jugador para evitar errores de evasión.

Inky (Cian) y Clyde (Naranja) - Caza en Manada:

Utilizan la clase base PackHunter con una Función de Evaluación Socio-céntrica.

Presión por Centroide: Optimizan la posición del punto medio entre ambos respecto a Pac-Man.

Efecto Pinza: Incluye una penalización por solapamiento que obliga a los fantasmas a tomar rutas distintas para rodear al jugador.

 Optimizaciones del Algoritmo Alfa-Beta

Para garantizar un rendimiento de 60 FPS y una toma de decisiones coherente, se implementaron las siguientes mejoras:

Tabú con Horizonte Limitado (K-FIFO): Una cola de memoria que impide a los fantasmas regresar a posiciones visitadas recientemente, eliminando vibraciones y bucles infinitos.

Move Ordering (Búsqueda Sesgada): Los nodos del árbol se ordenan mediante una heurística rápida antes de la evaluación completa, lo que aumenta drásticamente la tasa de poda de ramas irrelevantes.

Gestión de Estados Inestables: El sistema detecta cuando el jugador está inmóvil y ajusta los pesos de las heurísticas en tiempo real para mantener la agresividad de la caza.

 Requisitos e Instalación

Requisitos Previos

Python 3.x

Pygame

PyOpenGL

Pandas y Numpy

Instalación de Dependencias

pip install pygame PyOpenGL PyOpenGL_accelerate pandas numpy


Ejecución

Para iniciar el juego, ejecuta el archivo principal:

python main.py

Controles

W / S / A / D: Movimiento de Pac-Man (Arriba, Abajo, Izquierda, Derecha).

Flechas de dirección: Control de la cámara (rotación y zoom).

ESC: Salir del juego.

Estructura del Código

main.py: Punto de entrada, configuración de OpenGL y ciclo principal.

Ghost.py: Clase base con la infraestructura de movimiento y colisiones.

Blinky.py / Pinky.py: Implementaciones de búsqueda individual.

PackHunter.py: Lógica compartida para la colaboración de Inky y Clyde.

mapa.csv: Definición estructural del laberinto.

Desarrollado para el 2do Parcial de Técnicas de Inteligencia Artificial.