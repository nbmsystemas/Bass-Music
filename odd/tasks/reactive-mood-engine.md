# Reactive Mood Engine — Transformación audiovisual integral de Bass

- **Objetivo:** agregar a Bass un motor de Moods reactivo (atajo `M` o menú) que transforme en vivo el ecualizador, visualizador de espectro, paleta de colores y sugiera radios/generación de IA afines al mood del usuario para streaming.
- **Rama:** `main` · **Test runner:** `./venv/bin/python -m unittest`
- **Entrega:** commits por unidad de trabajo con tests.

## Specs

- **S1** — Atajo `M` y opción en el menú izquierdo de Library ("🌌 Mood Engine / Cambiar Mood").
- **S2** — Entrada de mood libre tipo prompt o presets rápidos: "Cyberpunk Night", "Lo-Fi Café", "Zen Chill", "Rock Energy", "Synthwave 80s", "Dark Trap".
- **S3** — Transformación reactiva de audio: aplica automáticamente el preset del ecualizador óptimo de 10 bandas para ese mood.
- **S4** — Transformación reactiva visual: cambia el estilo del visualizador FFT (`spec_style`) y los pares de colores de curses según la atmósfera del mood.
- **S5** — Curaduría reactiva: sugiere y permite encolar la radio online o disparar generación IA calibrada para ese mood con un solo enter.
- **S6** — Indicador de estado: la barra de estado y header muestran el mood activo `[Mood: 🌌 <nombre>]`.
- **S7** — Documentación y ayuda: entrada en overlay `?` y teclas documentadas.
- **S8** — Fusión Opción A + C: modo `AI Stream Continuo`: genera música del mood activo y va encadenando nuevos bloques automáticamente en segundo plano para que el stream en vivo nunca se corte.

## Tasks

- **T1** `config-moods` — Definición de estructuras de Moods, paletas de colores y presets en `config.py` — S2, S4.
- **T2** `mood-engine` — Motor `mood.py` para resolución de moods, presets de EQ, colores, sugerencias y stream continuo — S2, S3, S5, S8.
- **T3** `ui-reactive-palette` — Soporte de paletas dinámicas en curses y cambio de `spec_style` en `ui.py` — S4.
- **T4** `ui-mood-selector` — Menú selector de Mood (tecla `M` y click), prompt libre y estado activo — S1, S6.
- **T5** `smart-curation-and-stream` — Conexión con radios online y modo AI Stream Continuo de fondo — S5, S8.
- **T6** `tests` — Suite de tests unitarios `test_mood.py` — S1–S8.
- **T7** `docs` — Actualización de ayuda (`?`) y README con la feature — S7.

## Log

- **L1** — `a ver si podemes hacer una fiture relse de nuestro bass darle un toque asi como el de este repo pero mas a nuestro estilo no tan similar al de el https://github.com/nbmsystemas/gentle-stream`
- **L2** — Usuario aprobó "la C con la A": Fusión C + A — Reactive Mood Engine con atmósfera visual completa + AI Mood Radio continua sin cortes para streams.
