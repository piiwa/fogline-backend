# Fogline Backend — Exploration Sync API

Minimal FastAPI service backing the exploration layer. It stores, per identity, a
**grow-only set of coarse H3 cells** and exposes a delta push/pull contract. The
merge is a set union — conflict-free across devices and offline replays (a G-Set
CRDT). It stores **only cell ids** — no coordinates, no routes, no movement times.

## Contract

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/v1/auth/device` | Exchange `{device_id}` for a JWT (mock auth). |
| `POST` | `/api/v1/exploration/cells` | Union `{cells:[...]}` into the identity's set (idempotent). |
| `GET`  | `/api/v1/exploration/cells?since=<cursor>` | Cells added since the cursor + a new cursor. |
| `GET`  | `/health` | Liveness. |

All `/exploration/*` routes require `Authorization: Bearer <token>`.

**Multi-device:** exploration is scoped by the JWT `sub`. In this mock, `sub` is
the device id, so two devices are isolated. In production `sub` is the
authenticated **user** id (shared across their devices) and the same endpoints
give multi-device merge for free — the sync logic is identical.

## Run

```bash
poetry install
make run          # uvicorn on :8250  (schema auto-created on boot)
make test         # pytest
make migrate      # alembic upgrade head (prod schema path)
```

Point the mobile app at it with `EXPO_PUBLIC_API_BASE_URL=http://localhost:8250/api/v1`.

## Layout

`app/main.py` (app + lifespan) · `app/api/v1/endpoints/*` (routers) ·
`app/repositories/exploration.py` (G-Set upsert + cursor pull) ·
`app/models/exploration_cell.py` (unique `(user_id, cell_id)`) ·
`app/core/{config,security}.py` · `alembic/` (migrations).
