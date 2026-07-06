# sTEAMdistics

Herramienta para docentes. Analiza el historial Git de un repo de alumnos y genera un reporte de participación con análisis de IA (Gemini).

---

## Requisitos

- Python 3
- API Key de Gemini (gratuita): [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey)

---

## Configuración (una sola vez)

### API Key de Gemini (requerida para `--ai`)

```bash
git config --global sTEAMdistics.ai-key "TU_CLAVE"
# o como variable de entorno:
export STEAMDISTICS_AI_KEY="TU_CLAVE"
```

### Token de GitHub (requerido para `-R` en repos privados)

```bash
git config --global sTEAMdistics.gh-token "TU_TOKEN"
# o como variable de entorno:
export STEAMDISTICS_GH_TOKEN="TU_TOKEN"
```

Para repos públicos no es necesario. El token necesita permiso de lectura sobre issues (`repo` scope o `public_repo`).

---

## Uso

Ejecutar **dentro del repo del alumno**:

```bash
python3 /ruta/a/sTEAMdistics/generate_stats.py [MODO] [--ai]
```

| Modo | Descripción |
|------|-------------|
| `-H` | Último tag → HEAD (entregas parciales) |
| `-T` | Penúltimo tag → último tag (entregas finales) |
| `-R` | Igual que `-T`, pero con prompt de reentrega — baja los issues abiertos de GitHub y analiza si fueron corregidos |
| *(sin modo)* | Lista los tags disponibles y permite elegir el rango de forma interactiva |

El flag `--ai` activa el análisis con Gemini. Sin él, genera solo las estadísticas de líneas por autor.

---

## Output

Se genera un archivo local `{repo}-stats-{fecha}.md` con:

- Tabla comparativa de actividad por autor (líneas agregadas/borradas, porcentaje)
- Distribución de aportes por capa (modelo, persistencia, servicios, etc.)
- Análisis de IA por autor (con `--ai`):
  - Desequilibrio de participación entre capas
  - Coherencia entre capas (ej: agrega modelos sin persistirlos)
  - Calidad del gitflow: nombres de commits, merges/reverts, commits inflados
  - En modo `-R`: qué issues fueron corregidos y si las correcciones son genuinas

El archivo **no se sube al repo del alumno** — corriendo el script manualmente, queda solo en tu máquina.

---

## Automatización con CI

Corrido así, a mano, el reporte no queda registrado en ningún lado más que tu máquina. Para que se genere automáticamente al crear un tag y quede centralizado en un repo de análisis aparte (accesible solo para docentes), ver: [docs/ci-setup.md](docs/ci-setup.md)
