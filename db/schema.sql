CREATE SCHEMA IF NOT EXISTS crud_usuarios;

CREATE TABLE IF NOT EXISTS crud_usuarios.users (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name varchar(100) NOT NULL,
    email varchar(150) NOT NULL,
    password varchar(255) NOT NULL,
    role varchar(20) NOT NULL CHECK (role IN ('ADMIN', 'MEMBER', 'REVIEWER')),
    status varchar(20) NOT NULL DEFAULT 'PENDING'
        CHECK (status IN ('ACTIVE', 'INACTIVE', 'PENDING', 'BLOCKED')),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_users_email UNIQUE (email)
);

CREATE OR REPLACE FUNCTION crud_usuarios.set_updated_at()
RETURNS trigger LANGUAGE plpgsql SET search_path = '' AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_users_set_updated_at ON crud_usuarios.users;
CREATE TRIGGER trg_users_set_updated_at BEFORE UPDATE ON crud_usuarios.users
FOR EACH ROW EXECUTE FUNCTION crud_usuarios.set_updated_at();

ALTER TABLE crud_usuarios.users ENABLE ROW LEVEL SECURITY;
