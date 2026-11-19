# users-management-fastapi-hexagonal

Microservicio de gestión de usuarios construido con Python, FastAPI y arquitectura hexagonal. Implementa los endpoints de la Guía 1 y está preparado para PostgreSQL local o Supabase mediante variables de entorno.

## Requisitos

- Python 3.12 o superior (el proyecto también es compatible con Python 3.13).
- PostgreSQL 15 o superior, local o administrado. Docker es opcional.
- Git.

## Instalación en Windows (PowerShell)

```powershell
py -3 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
Copy-Item .env.example .env
```

Edita `.env` con los datos de tu base de datos y genera el secreto JWT:

```powershell
python scripts\generate_jwt_secret.py
```

Copia el valor generado en `JWT_SECRET` y define `DB_PASSWORD` y `ADMIN_PASSWORD`. No subas `.env` a Git.

## Base de datos

Ejecuta `db/schema.sql` en PostgreSQL o en el SQL Editor de Supabase. Para Supabase usa **Connect → Session pooler** y copia los parámetros del proyecto:

```dotenv
DB_HOST=aws-<region>.pooler.supabase.com
DB_PORT=5432
DB_NAME=postgres
DB_USERNAME=postgres.<project-ref>
DB_PASSWORD=<solo-la-database-password>
DB_SSL_MODE=require
DB_SCHEMA=crud_usuarios
```

`DB_PASSWORD` contiene solamente la contraseña de base de datos, no la URI completa. Para conexión local sin TLS usa `DB_SSL_MODE=disable`.

## Crear el administrador y arrancar

```powershell
python scripts\seed_admin.py
uvicorn users_management.main:app --app-dir src --port 8080 --reload
```

La API está en `http://localhost:8080`; Swagger en `/swagger-ui/index.html` y OpenAPI en `/v3/api-docs`.

## Endpoints

| Método | Ruta | Acceso |
|---|---|---|
| POST | `/api/auth/login` | Público |
| POST | `/api/users` | Público |
| GET | `/api/users` | Bearer JWT |
| GET | `/api/users/{id}` | Bearer JWT |
| PUT | `/api/users/{id}` | Bearer JWT |
| DELETE | `/api/users/{id}` | Bearer JWT |

El proveedor de correo predeterminado es `console`: los mensajes se registran en la consola. `smtp` usa Gmail y una contraseña de aplicación. Las contraseñas nunca aparecen en las respuestas de usuario.

## Verificación

```powershell
pytest
ruff check .
```

La suite exige una cobertura mínima del 90 %.

## Postman

Importa `postman/users-management.postman_collection.json` y los entornos `Local.postman_environment.json` y `Remoto.postman_environment.json`. En el entorno Local completa `adminEmail` y `adminPassword`; la colección guarda el token después del login y `userId` después de crear el usuario. Completa `baseUrl` del entorno Remoto cuando la API se despliegue.

## Docker Compose local

`compose.yaml` levanta PostgreSQL y la API en contenedores. Define `LOCAL_DB_PASSWORD` en `.env` (puede ser distinta de la contraseña de Supabase) y ejecuta:

```powershell
docker compose up --build
```

## Despliegue en Render

Conecta el repositorio de GitHub en Render o crea un Blueprint usando `render.yaml`. Completa los valores `sync: false` del servicio con las variables de conexión de Supabase y secretos nuevos; no copies el `.env` local al panel. El despliegue automático sigue los cambios en `main`. Swagger permanece público y `GET /` requiere Bearer JWT, como en el contrato del taller.
