# Puesta en marcha en la organización

Esta guía deja funcionando el análisis automático: cada vez que un equipo pushea un tag, `sTEAMdistics` analiza ese tag contra el anterior y guarda el reporte en la rama `reportes` de este repo. Los alumnos no ven ni el código ni los reportes.

## Cómo funciona

```
Repo del equipo                          sTEAMdistics (privado, solo docentes)
  steamdistics.yml  ── workflow_dispatch ──►  analizar.yml
  (avisa repo + tag)   (token Actions:write)    ├─ revalida repo y tag (GitHub App, solo lectura)
                                                 ├─ ¿es el último tag? si no, termina
                                                 ├─ analiza N-1..N (o desde la raíz si es el primero)
                                                 ├─ Gemini (key de la cátedra)
                                                 └─ commit en la rama `reportes`
```

| Credencial | Dónde vive | Qué permite |
|---|---|---|
| `STEAMDISTICS_DISPATCH_TOKEN` | Secret de la org, visible solo para los repos de equipos | Disparar workflows de `sTEAMdistics`. **No** lee código, reportes ni secrets. |
| `STEAMDISTICS_APP_CLIENT_ID` / `STEAMDISTICS_APP_PRIVATE_KEY` | Environment `produccion` de `sTEAMdistics` | Leer los repos de equipos (código, issues, teams). |
| `GEMINI_API_KEY` | Environment `produccion` de `sTEAMdistics` | Llamar a Gemini. |

Se asume que un alumno puede obtener el token de dispatch editando su workflow. Con ese token no puede ver nada: los inputs se revalidan, los secrets solo existen en `main` y los logs no muestran contenido.

---

## 1. Organización

En **Org settings**:

1. **Member privileges → Base permissions:** `No permission`.
2. **Member privileges → Repository forking:** deshabilitar el fork de repos privados.
3. Cada equipo en su propio **team**, con acceso solo a su repo y rol **Write** o **Maintain**, nunca **Admin**.
4. `sTEAMdistics` privado, con `main` como rama default. Solo los docentes tienen acceso.

## 2. Token de dispatch (cuenta de la cátedra)

Desde la **cuenta de la cátedra**, que tiene que ser miembro de la org:

1. **Settings → Developer settings → Fine-grained tokens → Generate new token.**
2. **Resource owner:** la org.
3. **Expiration:** 1 año. Anotar la fecha para renovarlo.
4. **Repository access:** *Only select repositories* → `sTEAMdistics`.
5. **Permissions → Repository → Actions:** `Read and write`. Nada más.
6. Si la org exige aprobación de fine-grained tokens, aprobarlo en **Org settings → Personal access tokens → Pending requests**.

Cargarlo en **Org settings → Secrets and variables → Actions → New organization secret**:
- Nombre: `STEAMDISTICS_DISPATCH_TOKEN`
- Repository access: *Selected repositories* → los repos de equipos.

## 3. GitHub App de lectura

**Org settings → Developer settings → GitHub Apps → New GitHub App:**

1. Nombre: por ejemplo `sTEAMdistics-lector`. Homepage URL: la del repo.
2. **Webhook:** desactivado (destildar *Active*).
3. **Repository permissions:** `Contents: Read-only`, `Issues: Read-only` (`Metadata: Read-only` se agrega solo).
4. **Organization permissions:** `Members: Read-only`, para leer los teams y detectar integrantes sin commits.
5. **Where can this GitHub App be installed?:** *Only on this account*.
6. Crear la App. Anotar el **Client ID** y generar una **private key** (descarga un `.pem`).
7. **Install App** → la org → *All repositories*, o solo los de equipos más `sTEAMdistics`.

## 4. Environment `produccion`

En `sTEAMdistics` → **Settings → Environments → New environment** → `produccion`:

1. **Deployment branches and tags:** *Selected branches and tags* → solo `main`.
2. **Environment secrets:**
   - `STEAMDISTICS_APP_CLIENT_ID`: el Client ID de la App.
   - `STEAMDISTICS_APP_PRIVATE_KEY`: el contenido completo del `.pem`.
   - `GEMINI_API_KEY`: la key de la cuenta de la cátedra ([aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey)).

## 5. Workflow en los repos de equipos

1. Copiar [`workflow-equipo.yml`](workflow-equipo.yml) a cada repo de equipo como `.github/workflows/steamdistics.yml`, reemplazando `<org>` por el nombre de la org.
2. **Org settings → Repository → Rulesets → New ruleset → New push ruleset**, aplicado a los repos de equipos:
   - **Restrict file paths:** `.github/workflows/steamdistics.yml`.
   - Sin bypass para los teams de alumnos.

## 6. Configuración de la cursada

En `config/cursada.toml` (en `main`):

- `anio` y `nombre`: carpeta donde se guardan los reportes.
- `patron_repo`: qué repos son de equipos y cómo se obtiene el nombre del equipo. Por defecto `^(?P<equipo>.+)-TP$`.
- `docentes`: logins de los docentes. Solo sus issues con label de severidad (`Grave`, `Corregir`, `Menor`, `Observación`) cuentan para la reentrega.
- `[equipos.integrantes]`: roster explícito. Si un equipo no figura, se usa el team de GitHub con el mismo nombre.

Las reglas de capas, los archivos generados y los modelos de Gemini están en `config/analisis.toml`.

## 7. Limpieza del esquema anterior

1. Revocar los tokens viejos (`STEAMDISTICS_READ_TOKEN` y `ANALISIS_REPO_TOKEN`).
2. Rotar la key de Gemini si alguna vez estuvo cargada en un repo de alumnos.
3. Borrar esos secrets y el workflow `ci-contributions.yml` de los repos de equipos.

---

## Verificación

Con un repo de equipo de prueba y una cuenta que simule ser alumno:

- [ ] La cuenta alumno no ve `sTEAMdistics`, ni sus Actions, ni la rama `reportes`.
- [ ] Pushear un tag genera `reportes/{anio}/{cursada}/{equipo}/{tag}.md` en la rama `reportes`.
- [ ] El primer tag de un repo se analiza desde la raíz.
- [ ] Pushear varios tags seguidos genera un solo reporte nuevo, el del último.
- [ ] Un tag más viejo que el último no genera reporte.
- [ ] Con el token de dispatch a mano: `gh workflow run analizar.yml -f repo=<org>/otro-repo -f tag=x` no genera nada, y `gh api repos/<org>/sTEAMdistics/contents/README.md` falla.
- [ ] Un disparo con `--ref` a otra rama no llega a correr el análisis (el job se saltea y el environment no entrega secrets).

## Operación

- **Reportes:** rama `reportes`, carpeta `{anio}/{cursada}/{equipo}/`. El estado por repo está en `state/` y los errores en `errores/`.
- **IA sin cuota:** el reporte sale con las métricas y un aviso. Para completarlo, hacer **Re-run** de esa corrida en Actions. Si el equipo ya pusheó otro tag, no hace nada.
- **Renovación anual:** regenerar el token de dispatch desde la cuenta de la cátedra y actualizar el secret de la org.
