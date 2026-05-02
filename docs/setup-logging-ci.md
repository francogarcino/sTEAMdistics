# Setup: CI de Resumen de Participación

## Prerequisitos

- Tener el script `generate_stats_ai.py` en la raíz del repo del equipo
- Tener un repo privado de análisis creado con al menos un commit (ej: un `README.md`)

---

## 1. Crear el Personal Access Token (PAT)

1. GitHub → tu avatar → **Settings**
2. **Developer settings** → **Personal access tokens** → **Tokens (classic)**
3. **Generate new token**
4. Scope mínimo: `repo`
5. Copiarlo — no se vuelve a mostrar

---

## 2. Configurar secrets y variables en el repo del equipo

Ir a **Settings → Secrets and variables → Actions** del repo del equipo.

### Secrets

| Nombre | Valor |
|--------|-------|
| `AI_API_KEY` | Tu clave de API (Gemini/Anthropic/etc) |
| `ANALISIS_REPO_TOKEN` | El PAT creado en el paso anterior |

### Variables

| Nombre | Valor |
|--------|-------|
| `ANALISIS_REPO` | `tu-usuario/nombre-repo-privado` |

---

## 3. Agregar el workflow

Crear el archivo `.github/workflows/generar-resumen.yml` en el repo del equipo con el contenido del workflow.

---

## 4. Probar

```bash
git tag v0.1
git push origin v0.1
```

Verificar en **Actions** del repo del equipo que el workflow corra. Si todo va bien, el repo de análisis debería tener la estructura:

```
/2026
  /primer-cursada
    /repo-generico
      v0.1.md
```

---

## Estructura del repo de análisis

Los reportes se organizan automáticamente por año, cursada y equipo:

```
/2026
  /primer-cursada        ← marzo a julio
    /nombre-equipo
      v1.0.md
      v2.0.md
  /segunda-cursada       ← agosto a diciembre
    /nombre-equipo
      v1.0.md
/2025
  ...
```

El nombre del equipo se infiere del nombre del repo, removiendo el sufijo `-TP` si existe.

---

## Notas

- El workflow se dispara con **cualquier tag**. Si se quiere filtrar, cambiar `'*'` en el trigger por un patrón como `'v*'`.
- El repo del equipo puede ser público — los secrets nunca se exponen en los logs.
- Si hay múltiples repos de equipos, repetir el paso 2 para cada uno. Si están en una organización, los secrets pueden configurarse a nivel org en **Organization Settings → Secrets and variables → Actions**.
