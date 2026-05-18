# Travelers Archive

A No Man's Sky community archive: news room, civilizations encyclopedia, long-form historical inquisitions, and a collaborative drafting tool.

Lives at `archive.havenmap.online` (subdomain of the existing Haven setup) once Phase 6 is complete.

## Layout

```
archive/                                 ← this folder, inside Master-Haven repo
├── docker-compose.yml                   ← stand-alone compose (not the Pi's master compose)
├── Dockerfile                           ← Python 3.12 image
├── entrypoint.sh                        ← runs alembic, then uvicorn
├── requirements.txt
├── alembic.ini
├── alembic/
│   ├── env.py
│   └── versions/                        ← migrations
├── sql/
│   └── initial_schema.sql               ← Phase 3 schema, applied by migration 0001
├── app/
│   ├── main.py                          ← FastAPI app
│   ├── config.py                        ← env var loading
│   ├── db.py                            ← SQLAlchemy engine + session
│   ├── deps.py                          ← FastAPI auth/role dependencies (Phase 3)
│   ├── auth_dev.py                      ← fake-login dev auth (Phase 3)
│   ├── auth_discord.py                  ← real OAuth (Phase 7)
│   ├── routes/                          ← one module per resource
│   ├── jobs/                            ← APScheduler background jobs (Phase 7)
│   └── models/                          ← Pydantic schemas
├── docs/
│   ├── v0.9-mockup.html                 ← design contract for the frontend
│   └── discord-roles.md                 ← role-mapping config, filled before Phase 7
└── frontend/                            ← Vite + React (added in Phase 5)
```

## Where state lives

- **Code** (this folder): git-tracked, committed to Master-Haven
- **Database**: on the Pi only, at `~/docker/archive-data/archive.db` (NOT in this repo)
- **Media uploads**: on the Pi only, at `~/docker/archive-data/media/`

## Local dev

The build prompt assumes deploy-to-Pi. Local dev is possible but secondary:

```bash
cd archive
python -m venv .venv
source .venv/bin/activate              # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
export DATABASE_PATH=$PWD/.local.db    # or set in .env
export ENV=dev
alembic upgrade head
uvicorn app.main:app --reload --port 8020
```

## Deploy (Pi, via Tailscale)

```bash
# from desktop, after committing changes
git add archive/
git commit -m "phase N: <description>"
git push

# on Pi
ssh pi8gb@pi8gb \
  "cd ~/docker/haven-ui/Master-Haven && git pull && \
   cd archive && docker compose up -d --build"
```

## Ports

- Container listens on **8020** internally
- Published on the host as **8020** until Phase 6 puts NPM in front of it
- Phase 6 puts NPM in front and the public surface becomes `https://archive.havenmap.online`

## Phase status

See top-level build prompt for phase definitions. As of Phase 1: foundation only — no read or write endpoints yet.
