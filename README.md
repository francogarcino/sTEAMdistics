# sTEAMdistics

Herramienta para docentes de Estrategias de Persistencia. Analiza el historial Git de los repos de equipos y genera un reporte de participación por alumno: métricas determinísticas más un análisis con Gemini. El análisis es una primera pasada para detectar participación dispareja o baja; no reemplaza la corrección.

Funciona de dos formas:

- **Automática (CI):** cada tag que pushea un equipo dispara el análisis de ese tag contra el anterior. El reporte queda en la rama `reportes` de este repo, que los alumnos no pueden ver. Puesta en marcha: [docs/setup-org.md](docs/setup-org.md).
- **Manual:** un docente lo corre en su máquina dentro del repo de un equipo.

---

## Qué analiza

**Métricas** (sin IA, iguales para todos los equipos):

- Líneas agregadas y borradas por integrante, sin contar líneas en blanco, reindentados ni archivos generados (`target/`, `.idea/`, lockfiles, etc.).
- Distribución por capa (modelo, persistencia, servicio, controller, test, otros). Las reglas están en `config/analisis.toml`.
- Commits, commits en pareja (`Co-authored-by`), días activos y porcentaje del trabajo hecho en las últimas 24 y 48 h antes del tag.
- Merges y reverts.
- Integrantes del equipo sin actividad en el período (con roster configurado o tomado de los teams de GitHub).
- Tags movidos: si un tag ya analizado pasa a apuntar a otro commit, se reanaliza y el reporte lo marca.

**Análisis con IA** (una llamada por equipo):

- Por integrante: participación en las capas centrales (servicio y persistencia), integridad de los commits y calidad del gitflow.
- Observaciones generales del equipo.
- **Reentrega:** si hay issues con label de severidad (`Grave`, `Corregir`, `Menor`, `Observación`) abiertos por docentes, evalúa si cada corrección es genuina, superficial o no tiene evidencia. Considera también los issues cerrados e informa quién los cerró.

A Gemini se le mandan los integrantes con alias ("Integrante A", ...), sin nombres ni emails. Los diffs van delimitados con un nonce aleatorio para que el contenido de los alumnos no pueda inyectar instrucciones.

---

## Uso manual

Requisitos: Python 3.11 o superior. No hay dependencias externas.

Ejecutar **dentro del repo del equipo**:

```bash
python3 /ruta/a/sTEAMdistics/generate_stats.py [MODO] [--ai] [--sin-github]
```

| Modo | Rango |
|------|-------|
| `-T` | Penúltimo tag → último tag (lo mismo que hace el CI) |
| `-H` | Último tag → HEAD (para mirar una entrega en curso) |
| *(sin modo)* | Lista los tags y permite elegir el rango |

- `--ai` activa el análisis con Gemini.
- `--sin-github` evita consultar la API de GitHub. Sin la API no se vinculan logins, no hay roster ni análisis de reentrega.

El reporte se guarda como `{repo}-stats-{fecha}.md` en el directorio actual.

### Credenciales para uso manual

```bash
# API Key de Gemini (para --ai)
git config --global sTEAMdistics.ai-key "TU_CLAVE"      # o STEAMDISTICS_AI_KEY

# Token de GitHub con lectura del repo (necesario para repos privados)
git config --global sTEAMdistics.gh-token "TU_TOKEN"    # o STEAMDISTICS_GH_TOKEN
```

---

## Configuración

| Archivo | Contenido |
|---|---|
| `config/cursada.toml` | Año y cursada, patrón de nombre de los repos de equipos, logins de docentes, roster por equipo |
| `config/analisis.toml` | Reglas de capas, archivos generados, presupuesto de diffs, modelos de Gemini |
| `config/mailmap` | Unificación manual de identidades (formato `.mailmap` de git) |

## Desarrollo

```bash
python3 -m unittest discover -s tests -t .
```

| Módulo | Responsabilidad |
|---|---|
| `steamdistics/orchestrator.py` | Entrada del CI: valida, aplica la regla del último tag, escribe reporte y estado |
| `steamdistics/cli.py` | Entrada manual |
| `steamdistics/pipeline.py` | Análisis completo de un rango (compartido por ambos modos) |
| `steamdistics/gitrepo.py`, `gitlog.py` | Tags, rangos y lectura de commits y diffs |
| `steamdistics/identity.py`, `metrics.py` | Agrupación de identidades y métricas por integrante |
| `steamdistics/context.py`, `gemini.py`, `prompts/` | Armado del prompt, seudonimización y llamada a Gemini |
| `steamdistics/reentrega.py`, `github.py` | Issues de corrección y API de GitHub |
| `steamdistics/report.py`, `state.py` | Render del Markdown y estado por repo |
