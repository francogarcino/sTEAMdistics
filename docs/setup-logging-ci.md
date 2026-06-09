# Configuración del CI de Auditoría de Contribuciones

Cuando un equipo crea un tag en su repo, el CI genera automáticamente un reporte de participación con IA y lo sube al repo privado de análisis.

---

## Paso 1 — Hacer privados los repos necesarios

Antes de instalar el workflow en repos de alumnos:

- **sTEAMdistics** debe ser **privado** (GitHub → Settings → Danger Zone → Change visibility). Así los alumnos no pueden ver el script de análisis.
- **El repo de análisis** (donde van los reportes) también debe ser **privado**, accesible solo para docentes.

---

## Paso 2 — Generar los tokens

### Token de lectura de sTEAMdistics (`STEAMDISTICS_READ_TOKEN`)

Permite que el CI de cada repo de alumno descargue el script sin exponerlo.

1. Ir a [GitHub Settings → Developer settings → Fine-grained tokens](https://github.com/settings/tokens?type=beta) → **Generate new token**
2. Configurar:
   - **Token name:** `steamdistics-ci-read`
   - **Expiration:** 1 año
   - **Repository access:** Only selected → elegir `sTEAMdistics`
   - **Permissions → Contents:** Read-only
3. Generar y copiar el token (`github_pat_...`). **Solo se muestra una vez.**

### Token de escritura al repo de análisis (`ANALISIS_REPO_TOKEN`)

Permite que el CI suba los reportes al repo privado.

1. Mismo flujo de fine-grained tokens
2. Configurar:
   - **Token name:** `steamdistics-ci-write`
   - **Expiration:** 1 año
   - **Repository access:** Only selected → elegir el repo de análisis
   - **Permissions → Contents:** Read and write
3. Generar y copiar el token.

---

## Paso 3 — Instalar el workflow en cada repo de alumno

### 3a. Agregar los secrets

En el repo del alumno → **Settings → Secrets and variables → Actions → New repository secret**:

| Secret | Valor |
| :--- | :--- |
| `STEAMDISTICS_READ_TOKEN` | Token de lectura de sTEAMdistics (Paso 2) |
| `STEAMDISTICS_AI_KEY` | Clave de API de Google Gemini (`AIzaSy...`) |
| `ANALISIS_REPO_TOKEN` | Token de escritura al repo de análisis (Paso 2) |
| `ANALISIS_REPO` | Path del repo de análisis (ej: `francogarcino/repos-contributions-test`) |

### 3b. Agregar el workflow

Copiar el archivo `.github/workflows/ci-contributions.yml` de este repo al repo del alumno, en la misma ruta. Sin modificaciones.

---

## Cómo probar el flujo

1. Asegurarse de tener **al menos dos tags** en el repo de prueba (el script compara entre los dos últimos).
2. Crear y pushear un nuevo tag:
   ```bash
   git tag -a v1.0 -m "Entrega 1"
   git push origin v1.0
   git tag -a v1.1 -m "Entrega 2"
   git push origin v1.1
   ```
3. Verificar en **Actions** del repo que el job pasa todos los steps.
4. Verificar que en el repo de análisis apareció el archivo bajo:
   `{año}/{cursada}/{equipo}/v1.1.md`

---

## Notas

- El nombre del equipo se infiere del nombre del repo quitando el sufijo `-TP`.
- El semestre se deduce de la fecha: meses 3–7 → `primer-cursada`, resto → `segunda-cursada`.
- El script nunca queda en el repo del alumno — se descarga en runtime y desaparece al terminar el job.
