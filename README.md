# 🤖 sTEAMdistics: Auditoría de Participación con IA

Este script (`generate_stats_ai.py`) es una herramienta **exclusiva para docentes**. Analiza el historial de Git de los alumnos y utiliza la IA de Google (Gemini) para comparar lo que dicen los mensajes de commit contra el código real que escribieron (diffs), generando un reporte de integridad y un resumen técnico detallado.

### 📋 Requisitos
*   **Python 3** instalado.
*   Una **API Key de Gemini** (es gratuita y se obtiene en segundos).

---

### 1️⃣ Configuración Inicial (Solo una vez)

Para no tener que pegar tu clave cada vez que corres el script, vamos a guardarla en tu configuración global de Git. Esto es seguro y no entra en conflicto con otras herramientas de trabajo.

1.  Obtén tu clave en: [Google AI Studio - API Keys](https://aistudio.google.com/app/apikey).
2.  Copia la clave (empieza con `AIza...`).
3.  Ejecuta el siguiente comando en tu terminal (reemplazando por tu clave):

```bash
git config --global sTEAMdistics.ai-keys "TU_CLAVE_AQUI"
```

4.  **Verifica que se guardó correctamente:**
```bash
git config --get sTEAMdistics.ai-keys
```
> Si el comando anterior te devuelve tu clave, ¡ya estás listo!

> **Alternativa:** También podés exportar la clave como variable de entorno en lugar de usar git config:
> ```bash
> export EPERS_STATS_AI_KEYS="TU_CLAVE_AQUI"
> ```

---

### 2️⃣ Cómo Correrlo

El script se debe ejecutar **dentro de la carpeta del proyecto del alumno**.

#### Caso A: Desde el último Tag hasta HEAD (Ideal para entregas parciales)
```bash
python3 path/to/sTEAMdistics/generate_stats_ai.py -h --ai
```

#### Caso B: Entre los últimos dos Tags (Ideal para entregas finales)
```bash
python3 path/to/sTEAMdistics/generate_stats_ai.py -T --ai
```

---

### 3️⃣ Resultado: `{repo}-stats-{fecha}.md`

El script generará un archivo local con el nombre del repositorio y la fecha, por ejemplo: `mi-repo-stats-2026-04-23.md`. Este reporte incluye:

*   **Resumen de Participación:** Porcentaje de líneas agregadas/borradas por usuario, con links clickeables a la sección de cada uno.
*   **Distribución por Package:** Cuánto aportó cada uno en Modelo, Persistencia, Servicios, etc.
*   **Auditoría de IA (Confidencial):**
    *   **Resumen técnico:** Un desglose de qué clases y capas tocó el alumno realmente.
    *   **Análisis de Integridad:** Evaluación de si los commits son veraces o si hay "ruido" (commits vacíos, mensajes genéricos como "fix", etc.).
    *   **Distribución vs. equipo:** Comparación de la participación en cada capa contra el resto del grupo, detectando si alguien se especializó en una sola capa en lugar de pasar por todas.
    *   **Patrón de refactors:** Detección de commits repetidos sobre los mismos archivos, evaluando si el alumno se trabó con una implementación o si infló artificialmente su actividad anterior.

---

### ⚠️ Notas Importantes para Docentes

*   **Privacidad:** El script **NO sube nada a GitHub**. El reporte es 100% local para que los alumnos no vean el análisis de la IA. No compartas el `.md` generado con ellos.
*   **Aislamiento:** Esta configuración usa la clave `sTEAMdistics.ai-keys` de Git, por lo que no interfiere con ninguna otra configuración de Gemini que tengas en tu PC de trabajo.
*   **Costo:** Usamos `gemini-2.5-flash` (con fallback a `gemini-2.0-flash` y `gemini-2.0-flash-lite`), todos **gratuitos** hasta un límite muy alto. No deberían tener problemas de costos.