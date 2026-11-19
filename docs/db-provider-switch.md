# Guía 4 — Cambiar el proveedor de base de datos

La aplicación usa SQLAlchemy y el mismo adaptador PostgreSQL para Supabase o cualquier servicio PostgreSQL compatible. Para cambiar de proveedor, cambia la configuración; el dominio y los casos de uso no cambian.

## Variables que cambian

| Variable | Valor del proveedor de destino |
|---|---|
| `DB_HOST` | Host directo o pooler del proveedor |
| `DB_PORT` | Puerto publicado por el proveedor |
| `DB_NAME` | Base de datos (en Supabase normalmente `postgres`) |
| `DB_USERNAME` | Usuario PostgreSQL, incluido el sufijo del proyecto si el pooler lo requiere |
| `DB_PASSWORD` | Contraseña de la base de datos de destino, nunca una URI completa |
| `DB_SSL_MODE` | `require` cuando el proveedor exige TLS; `disable` solo para una instancia local |
| `DB_SCHEMA` | `crud_usuarios` |

No cambies `JWT_SECRET`, `ADMIN_EMAIL`, `ADMIN_PASSWORD` ni `EMAIL_PROVIDER` por el solo hecho de cambiar el host. No copies valores secretos entre proveedores sin una razón.

## Procedimiento

1. Crea la base y obtén sus parámetros de conexión. Para Supabase en una red IPv4, usa **Connect → Session pooler**.
2. Actualiza las variables anteriores en `.env` local o en el panel de variables del servicio Render.
3. Ejecuta `db/schema.sql` en la base de destino. El esquema y sus datos no se transfieren automáticamente desde la base anterior.
4. Crea el administrador inicial en esa base con `python scripts/seed_admin.py`.
5. Reinicia la API y verifica `POST /api/auth/login`, `GET /api/users` con token y `GET /api/users` sin token (401).

## Evidencia de arquitectura

El adaptador de persistencia recibe el host, puerto, base, usuario, contraseña y SSL al construirse. El puerto de salida del repositorio no depende del proveedor. Para la demostración del taller, captura las variables previas y posteriores y las mismas pruebas HTTP exitosas.

> Este cambio solo apunta la aplicación a otra base. Si necesitas migrar datos, exporta e importa explícitamente usando herramientas PostgreSQL; cambiar variables no copia registros.
