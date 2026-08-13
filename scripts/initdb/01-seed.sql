-- Dev seed data. Loaded by Postgres on first boot of the dev container.
-- Safe to run repeatedly because every INSERT is idempotent.

BEGIN;

INSERT INTO users (username, email, hashed_password, is_active, role)
VALUES (
    'admin',
    'admin@example.com',
    -- bcrypt hash of "admin" (cost 4) — DEV ONLY.
    '$2b$04$0HQ8X0HQ8X0HQ8X0HQ8X0OQ8X0HQ8X0HQ8X0HQ8X0HQ8X0HQ8X0HQ',
    TRUE,
    'admin'
)
ON CONFLICT (username) DO NOTHING;

INSERT INTO projects (title, description, status, priority, owner_id)
SELECT 'Welcome project', 'Seeded by docker-compose dev profile', 'active', 'medium', id
FROM users WHERE username = 'admin'
ON CONFLICT DO NOTHING;

COMMIT;
