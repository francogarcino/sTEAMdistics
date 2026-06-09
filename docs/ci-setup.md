# Configuración del CI

Cuando un alumno hace push de un tag, el workflow genera el reporte automáticamente y lo sube a un repo privado de análisis al que solo acceden los docentes.

---

## Antes de empezar

Ambos repos deben ser **privados**:
- `sTEAMdistics` — para que los alumnos no vean el script
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
| `ANALISIS_REPO` | Path del repo de análisis (ej: `francogarcino/analisis-epers`) |

---

## Paso 3 — Agregar el workflow

Copiar `.github/workflows/ci-contributions.yml` de este repo al repo del alumno en la misma ruta. Sin modificaciones.

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
