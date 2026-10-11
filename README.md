# KAYAN

An operations-visualisation project for a fictional AI-agent company: a
browser-based 3D office floor that renders the workforce, actor states, and a
scripted order workflow, driven by a pure event reducer so identical event
sequences always produce identical results.

![KAYAN Operations Floor](kayan-3d/docs/images/hero-wide.png)

## What's in this repo

| Path | What it is |
| --- | --- |
| `kayan-3d/` | The main app — React + TypeScript + Three.js / React Three Fiber. 3D office scene, event-sourced state, TrustGate, audit and experiment tooling. See [kayan-3d/README.md](kayan-3d/README.md). |
| `server/` | Python backend (FastAPI + PostgreSQL + Alembic). Event source, historical replay, live WebSocket delivery. See [server/README.md](server/README.md). |
| `docs/` | [DEFENSE-STATUS.md](docs/DEFENSE-STATUS.md) |
| `DEMO-SCRIPT.md` | Scripted walkthrough of the demo order. |
| `HANDOFF.md` | Current state and notes for whoever picks this up. |

`office-3d/` exists locally but is gitignored and not part of the repository.

## Quick start

### 3D scene (no backend needed)

```sh
cd kayan-3d
npm install
npm run dev          # http://localhost:5173
```

Other scripts: `npm run typecheck`, `npm run build`, `npm run preview`, and
`npm run check:e2e` (plus `check:mock`, `check:transport`, `check:command`,
`check:experiment`, `check:onboarding`).

### Backend (optional)

The scene runs standalone on the mock event source. To run against the real
backend, see [server/README.md](server/README.md) — the short version:

```sh
python -m venv .venv
pip install -r server/requirements.txt
python -m app.scripts.devdb start      # prints DATABASE_URL
python -m app.scripts.init_db --demo
python -m uvicorn app.main:app --reload --port 8000
```

## Scene highlights

- Five workstations on a 2×2+1 grid, each actor playing a native Mixamo
  sitting-typing animation.
- Frosted glass partitions with cyan base LEDs between pods.
- Floor LED cross — cyan Z-axis, warm X-axis — through the central aisle.
- Glass curtain wall with a procedurally generated night-city backdrop.
- Cinematic lighting: ambient 0.35, cool directional from the glazing, warm
  point lights on each desk lamp.
- Presentation and interior camera presets, solved numerically rather than
  eyeballed.

Geometry here is derived from measurement, not guesswork — see the scene
README's [architecture notes](kayan-3d/README.md#3d-scene--operations-floor).

## Documentation

- **[kayan-3d/README.md](kayan-3d/README.md)** — the app and 3D scene in full.
- **[server/README.md](server/README.md)** — backend setup, architecture, and
  tests.