# Security Console Frontend

The production console is a React + TypeScript + Vite application. It serves the checker at `/` and the local collection/training console at `/training.html`.

```powershell
npm install
npm run dev
```

The development server runs at `http://127.0.0.1:5173` and proxies `/api` plus `/api/ws` to FastAPI at `http://127.0.0.1:8000`. Use `npm run lint`, `npm test`, and `npm run build` before publishing.

Collection, training, cancellation, and rollback controls are enabled only when the page is opened on localhost and the API has `ENABLE_LOCAL_TRAINING=true`. A Netlify/static build remains read-only and can connect to a separately hosted API through `VITE_API_BASE_URL` or the Settings view.
