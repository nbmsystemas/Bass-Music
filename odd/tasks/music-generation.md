# Music Generation — generación de música sin copyright

- **Objetivo:** agregar a Bass la generación de música (cloud vía OpenRouter + fallback local MusicGen) disparada por atajo o click, integrada a la playlist con loop, para fondo de streams.
- **Rama:** `feature/music-generation` · **Test runner:** `./venv/bin/python -m unittest`
- **Entrega:** feature-branch (un PR), commits por tarea.

## Specs

- **S1** — El usuario dispara la generación **"por atajo o click"** (nuevo keybinding `g` + entrada en ayuda).
- **S2** — Prompt de texto libre tipo **"genera un tema de jazz o rap asi cualquier genero"**: el usuario escribe un género/mood y Bass genera.
- **S3** — Generación con **"un modelo de generacion ... por medio de auth o apiky"**: backend cloud vía **OpenRouter (Google Lyria 3)** autenticado con `OPENROUTER_API_KEY`.
- **S4** — **"selecionar modelos ... dejariamos uno de forma predetrmianda que sea bueno ... que no consuma nada"**: modelos seleccionables (`google/lyria-3-clip-preview` = clip 30s $0.04 default barato; `google/lyria-3-pro-preview` = canción ~3min $0.08). Default = Clip (el más económico).
- **S5** — Fallback local **gratis**: MusicGen (Meta, `facebook/musicgen-small`), import perezoso, dependencias opcionales. *Supuesto: el usuario eligió "Asumir el riesgo, los dos igual" — sin distinción en la UI.*
- **S6** — **"que se peuda repetir"**: el tema generado se añade a la playlist, se reproduce y respeta el modo Repeat (off/una/todas).
- **S7** — **"es para los fondos de mis vivos"**: uso orientado a fondo de streams YouTube/Twitch. Se documenta disclaimer legal factual.

## Tasks

- **T1** `config` — ajustes de generación + keybinding `g` (y `G` para ciclar modelo) — S1, S4.
- **T2** `cloud-backend` — `generator.py`: backend OpenRouter Lyria 3 (clip/pro), streaming base64 → archivo — S3, S4.
- **T3** `local-backend` — `generator.py`: backend MusicGen (lazy import, deps opcionales) — S5.
- **T4** `async-service` — servicio de generación en background thread + polling (no bloquea el TUI) — S3.
- **T5** `ui-integration` — handler de tecla, prompt, status, auto-add + auto-play + loop — S1, S2, S6.
- **T6** `docs` — overlay de ayuda, footer, README + disclaimer legal — S1, S7.
- **T7** `tests` — `unittest` con HTTP mockeado, selección de backend y loop — S1–S7.

## Log

- **L1** — `quiero que a nuestro reproductor le agregemos una nueva fiture esta nueva funcione sera para que el usario pueda generar musica sin copi righ ni derechos de eautor utilizar un modelo de generacion el mas barto y economico utlziando suscripcioens de openia opencode openrouter clarude el que quiera por medio de aut o apiky y selecionar modelos que sean para esto dejariamos uno de forma predetrmianda que sea bueno para esta tarea per oque no consuma nada.`
- **L2** — `o sea el usario tiene que por atajo o click poder decirle a bass genera un tema de jazz o rap asi cualquier genero y lo genere y que se peuda repetir solo es para los strmin de youtube o twch cualquier genreo de musica tiene que generar es para los fondos de mis vivos`
- **L3** — Decisión backend: híbrido (OpenRouter Lyria 3 + MusicGen local) → usuario eligió **"Asumir el riesgo, los dos igual"** (sin distinción UI). Uso: streaming YouTube/Twitch, potencialmente comercial. Premisas verificadas: OpenAI/Claude/Opencode no generan música; OpenRouter expone Lyria 3; MusicGen es CC-BY-NC (no comercial); Lyria 3 permite uso comercial.
- **L4** — Commit `f8d5886` (feat: add AI music generation) cierra T1–T7. Evidencia: `./venv/bin/python -m unittest test_generator` → 13 tests OK; `py_compile` OK en config/generator/ui. Bug real encontrado por los tests y corregido: deadlock en `GenerationService.start()` (`threading.Lock` → `RLock`). Riesgo: item 2 (credenciales) → verificación independiente.
- **L5** — Verificador independiente (item 2, credenciales): **NO DISPONIBLE** — `gentle-ai-verify` falló por `quota`. Self-verification del escritor: key solo desde `os.environ` (generator.py:53), solo en header `Authorization` hacia endpoint HTTPS fijo (generator.py:138), sin print/log del key (verificado con `rg`). 13 tests OK.
