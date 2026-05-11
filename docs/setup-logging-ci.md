# Configuración de Logging de Contribuciones en CI

Este documento detalla cómo configurar la automatización para que, cada vez que un alumno (o docente) cree un **tag** en este repositorio, se genere un reporte de participación por IA y se envíe automáticamente a un repositorio centralizado de auditoría.

## 1. Configuración de Secretos y Variables en GitHub

Para que el Workflow de GitHub Actions funcione, debes configurar los siguientes elementos en **Settings > Secrets and variables > Actions** del repositorio:

### Secretos (Secrets)
| Nombre | Descripción | Ejemplo |
| :--- | :--- | :--- |
| `AI_API_KEY` | Tu clave de API de Google Gemini. | `AIzaSy...` |
| `ANALISIS_REPO_TOKEN` | Un **Personal Access Token (PAT)** con permisos de `repo` (escritura). | `ghp_...` |
| `ANALISIS_REPO` | Path completo del repositorio de destino. | `francogarcino/repos-contributions-test` |

---

## 2. Creación del Personal Access Token (PAT)

Para que un repositorio pueda escribir en otro, GitHub requiere un token:
1. Ve a **GitHub Settings > Developer settings > Personal access tokens > Tokens (classic)**.
2. Genera un nuevo token con el scope `repo`.
3. Copia el token y pégalo como el secreto `ANALISIS_REPO_TOKEN` en este repositorio.

---

## 3. Cómo Probar el Flujo

Una vez configurados los secretos y variables, puedes disparar la automatización siguiendo estos pasos:

1.  **Asegúrate de tener al menos dos tags** en tu repositorio (ya que el script usa `-T` para comparar entre los últimos dos tags).
2.  **Crea y sube un nuevo tag:**
    ```bash
    git tag -a v1.0.test -m "Prueba de CI"
    git push origin v1.0.test
    ```
3.  **Verifica en GitHub Actions:** Entra a la pestaña **Actions** para ver el progreso del job "Generar resumen de participación".
4.  **Verifica el destino:** Si el job finaliza correctamente, el reporte aparecerá en el repositorio definido en `ANALISIS_REPO` bajo una estructura de carpetas similar a:
    `2026/primer-cursada/NombreDelRepo/v1.0.test.md`

---

## 4. Notas Técnicas

- El script utiliza la variable de entorno `STEAMDISTICS_AI_KEYS` dentro del contenedor de CI.
- El workflow deduce automáticamente el nombre del equipo y el semestre basándose en la fecha actual y el nombre del repositorio.
- El nombre del equipo se infiere del nombre del repo, removiendo el sufijo `-TP` si existe.
