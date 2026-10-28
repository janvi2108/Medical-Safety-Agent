# Vercel Deployment (React frontend)

The React/Vite frontend is deployed as a Vercel project. The FastAPI backend
must be deployed separately to Render; follow [Render deployment](render-deployment.md)
before connecting the frontend.

## Vercel project settings

1. Import the repository in Vercel.
2. Set **Root Directory** to `Medication-Safety-Agent/frontend` (or `frontend`
   when `Medication-Safety-Agent` is itself the repository root).
3. Keep the Vite framework preset. Use:
   - **Install Command:** `npm ci` (or Vercel's npm lockfile detection)
   - **Build Command:** `npm run build`
   - **Output Directory:** `dist`
4. In **Settings → Environment Variables**, add the required public API URL:

   ```text
   VITE_API_BASE_URL=https://<your-render-service>.onrender.com
   ```

   Set it for Production and any Preview environment you plan to use, then
   redeploy so Vite embeds the value in the build. This variable contains only
   the backend URL. Never put the Groq API key or other credentials in a
   `VITE_` variable.

The API client strips trailing slashes and appends the existing `/analyze`
path. Development falls back to `http://127.0.0.1:8001`; production has no
localhost fallback, so an omitted production variable produces an actionable
configuration error.

## Backend CORS

Set Render's `CORS_ORIGINS` to the exact Vercel origin, for example
`https://<your-vercel-project>.vercel.app`. For previews, explicitly list
each allowed origin as a comma-separated value. Wildcard origins are rejected.
Local development origins remain in the repository-root `.env.example` and
should be configured only for local backend development.

## Verify

After both services are deployed, open the Vercel URL and use a synthetic
clinical note. In browser Developer Tools → Network, confirm the request is
`POST https://<your-render-service>.onrender.com/analyze`, inspect its status
and response shape, and check the browser console for CORS errors. Also check
the Render `/health` endpoint; it confirms process liveness but not database
or LLM readiness.
