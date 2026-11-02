# KAYAN operations office

The sole active frontend, inside the canonical project. Run `npm ci`, then `npm run dev -- --host 127.0.0.1 --port 5173 --strictPort`. The source defaults to the console at `http://127.0.0.1:8001`; `VITE_KAYAN_API_URL` may override its URL. No mock/business-company backend fallback remains.

Prepared geometry, four FBX assets, current-task screens, live sessions, operator input and TA planning/reporting controls are retained. AUDIT reads the actual console transcript and audit IDs; it does not make authorization decisions or verify the backend audit chain.

`npm run build` type-checks and builds. Retained `check:*` commands cover transport/reconnect, sessions, audit escaping, TA presentation, geometry/picking and metric arithmetic. `check:trustgate:live` reads the running backend without starting an assessment. `/?profile=1` retains the opt-in development profiler. Existing FBX and bundle warnings remain.
