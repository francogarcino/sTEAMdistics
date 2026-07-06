# Configuración del CI

Cuando un alumno hace push de un tag, el workflow genera el reporte automáticamente y lo sube a un repo privado de análisis al que solo acceden los docentes.

El workflow real vive en `sTEAMdistics` (privado). En el repo del alumno solo va un archivo de 7 líneas que lo llama — sin lógica visible.

> **Prerequisito para que funcione:** `sTEAMdistics` debe estar en un repo privado **dentro de la misma organización** que los repos de los alumnos. Mientras esté en una cuenta personal, los reusable workflows no cruzan el contexto de org.

---

## Antes de empezar

Ambos repos deben ser **privados**:
- `sTEAMdistics` — para que los alumnos no vean el script ni el workflow
- El repo de análisis — donde van a quedar los reportes

---

## Paso 1 — Generar los tokens

Ir a [GitHub → Developer settings → Fine-grained tokens](https://github.com/settings/tokens?type=beta) → **Generate new token**.

### Token de lectura de sTEAMdistics

- **Repository access:** solo `sTEAMdistics`
- **Permissions → Contents:** Read-only

### Token de escritura al repo de análisis

- **Repository access:** solo el repo de análisis
- **Permissions → Contents:** Read and write

Ambos tokens: expiration 1 año, copiarlos al crearlos (se muestran una sola vez).

---

## Paso 2 — Agregar secrets al repo del alumno

**Settings → Secrets and variables → Actions** en el repo del alumno:

| Secret | Valor |
| :--- | :--- |
| `STEAMDISTICS_READ_TOKEN` | Token de lectura (Paso 1) |
| `STEAMDISTICS_AI_KEY` | API Key de Gemini (`AIzaSy...`) |
| `ANALISIS_REPO_TOKEN` | Token de escritura (Paso 1) |
| `ANALISIS_REPO` | Path del repo de análisis (ej: `org/analisis-epers`) |

---

## Paso 3 — Agregar el workflow al repo del alumno

Copiar `docs/student-workflow-template.yml` al repo del alumno como `.github/workflows/ci-contributions.yml`.

El archivo llama al workflow de `sTEAMdistics` directamente. Los alumnos solo ven esto:

```yaml
name: Auditoría de participación

on:
  push:
    tags: ['*']

jobs:
  audit:
    # TODO: cambiar por URL del repo en la organización
    uses: francogarcino/sTEAMdistics/.github/workflows/ci-contributions.yml@develop
    secrets: inherit
```

---

## Verificación

El repo necesita al menos dos tags. Para probar desde cero:

```bash
git tag -a v1.0 -m "Entrega 1" && git push origin v1.0
git tag -a v1.1 -m "Entrega 2" && git push origin v1.1
```

Verificar en **Actions** que el job completa, y que en el repo de análisis aparece el archivo en `{año}/{cursada}/{equipo}/v1.1.md`.

---

## Notas

- El nombre del equipo se infiere quitando el sufijo `-TP` del nombre del repo.
- El semestre se deduce de la fecha: meses 3–7 → `primer-cursada`, resto → `segunda-cursada`.
- El script no queda en el repo del alumno — se descarga en runtime y desaparece al terminar el job.
