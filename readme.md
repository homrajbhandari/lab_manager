# Research Laboratory Management System

A FastAPI + SQLAlchemy backend for managing research-laboratory resources: **projects**, **tasks**, **inventory**, and **samples**.

## Prerequisites

- Python 3.10+
- `pip` and `venv`

## Project layout

```
lab-manager/
├── app/
│   ├── main.py          # FastAPI app and route definitions
│   ├── crud.py          # Database access helpers
│   ├── models.py        # SQLAlchemy models
│   ├── schemas.py       # Pydantic request/response schemas
│   ├── database.py      # Engine, session, Base
│   ├── utils.py         # Response envelope + APIError
│   └── auth.py, dependencies.py   # (reserved for future auth work)
├── tests/               # pytest suite
├── requirements.txt
└── readme.md
```

## Install

```bash
# from the lab-manager/ directory
python -m venv venv

# activate
# Windows (PowerShell)
.\venv\Scripts\Activate.ps1
# Windows (Git Bash)
source venv/Scripts/activate
# macOS / Linux
source venv/bin/activate

pip install -r requirements.txt
```

The app uses SQLite by default and writes `lab_manager.db` in the project root. To use a different database, set `DATABASE_URL` in a `.env` file.

## Run the server

```bash
uvicorn app.main:app --reload
```

The server listens on `http://127.0.0.1:8000` by default.

Useful URLs:

| URL | Purpose |
| --- | --- |
| `http://127.0.0.1:8000/` | Welcome message |
| `http://127.0.0.1:8000/health` | Health check |
| `http://127.0.0.1:8000/docs` | Interactive Swagger UI |
| `http://127.0.0.1:8000/redoc` | ReDoc API reference |

To run on a different port:

```bash
uvicorn app.main:app --port 8001
```

## Endpoints

All routes are mounted under the four resource collections. Each supports list, get, create, update, and delete with `skip` / `limit` pagination on list endpoints.

| Resource | Routes |
| --- | --- |
| Projects | `GET/POST /projects/`, `GET/PUT/DELETE /projects/{project_id}` |
| Tasks | `GET/POST /tasks/`, `GET/PUT/DELETE /tasks/{task_id}` |
| Inventory | `GET/POST /inventory/`, `GET/PUT/DELETE /inventory/{inventory_id}` |
| Samples | `GET/POST /samples/`, `GET/PUT/DELETE /samples/{sample_id}` |

`tasks` and `samples` require a valid `project_id`; the API returns `404 NOT_FOUND` if the referenced project does not exist.

## Response envelope

Every endpoint — success or error — returns the same shape:

```jsonc
// Success (single resource or delete)
{
  "success": true,
  "message": "Project created",
  "data": { "id": 1, "title": "...", "...": "..." },
  "total": null
}

// Success (list)
{
  "success": true,
  "message": "OK",
  "data": [ { "id": 1, "...": "..." } ],
  "total": 1
}

// Error
{
  "success": false,
  "message": "Project not found",
  "error": { "code": "NOT_FOUND", "details": null }
}
```

For validation errors (HTTP 422), `error.details` contains the Pydantic error list.

## Testing

### Pytest suite

```bash
pytest
```

The suite under `tests/` covers the CRUD helpers and the FastAPI routes, including the response envelope.

## Troubleshooting

- **`ModuleNotFoundError: No module named 'app'`** — run commands from the `lab-manager/` directory (the one containing `app/`), not from inside `app/`.
- **Port already in use** — pass `--port <other>` to uvicorn.
- **Stale schema** — delete `lab_manager.db` to recreate tables from the current models on the next startup.