# sTEAMdistics

Herramienta para docentes. Analiza el historial Git de un repo de alumnos y genera un reporte de participación con análisis de IA (Gemini).

---

## Requisitos

- Python 3
- API Key de Gemini (gratuita): [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey)

---

## Configuración (una sola vez)

Guardá la clave en tu configuración global de Git:

```bash
git config --global sTEAMdistics.ai-key "TU_CLAVE"
```

O como variable de entorno si preferís:

```bash
export STEAMDISTICS_AI_KEY="TU_CLAVE"
```

---

## Uso

Ejecutar **dentro del repo del alumno**:

**Desde el último tag hasta HEAD** (entregas parciales):
```bash
python3 /ruta/a/sTEAMdistics/generate_stats_ai.py -H --ai
```

**Entre los dos últimos tags** (entregas finales):
```bash
python3 /ruta/a/sTEAMdistics/generate_stats_ai.py -T --ai
```

El flag `--ai` activa el análisis con Gemini. Sin él, genera solo las estadísticas de líneas por autor.

---

## Output

Se genera un archivo local `{repo}-stats-{fecha}.md` con:

- Tabla comparativa de actividad por autor (líneas agregadas/borradas, porcentaje)
- Distribución de aportes por capa (modelo, persistencia, servicios, etc.)
- Análisis de IA por autor:
  - Qué clases y capas tocó realmente
  - Calidad y veracidad de los mensajes de commit
  - Comparación de participación vs. el resto del equipo
  - Detección de commits repetidos sobre los mismos archivos

El archivo **no se sube al repo** — queda solo en tu máquina.

---

## Automatización con CI

Para que el reporte se genere automáticamente al crear un tag en el repo del alumno, ver: [docs/ci-setup.md](docs/ci-setup.md)
