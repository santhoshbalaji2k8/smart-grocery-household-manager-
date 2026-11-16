# Smart Grocery & Household Manager — Web Edition

## Architecture
- `web_frontend/`: responsive static browser interface, suitable for Netlify Drop.
- `web_backend/`: FastAPI service, reusing the existing Python database and business-rule layer.
- `app/`: original desktop application and SQLite domain logic. The desktop launcher remains available.

## Dependency installation note
The backend uses the core `uvicorn` package without the optional `[standard]` extras. This avoids pulling optional packages such as PyYAML that may require a local build toolchain on some Windows/Python setups. The core Uvicorn server is sufficient for this application.

## Run locally
1. From the project root, install dependencies:
   `python -m pip install -r requirements.txt -r web_backend/requirements.txt`
2. Start the API:
   `python -m uvicorn web_backend.main:app --reload`
3. Open `http://localhost:8000/api/health` to check the service.
4. Open `web_frontend/index.html` in a browser. The default API address is `http://localhost:8000`.
5. On first launch, create the owner account. Use setup key `local-only-setup-key-change-me` for local development. Passwords must be at least 12 characters and include letters and numbers. Only the first owner account can be registered; public registration is disabled.

## Deploy backend
1. Push the complete project folder to GitHub.
2. Create a Python web service on Render using the included `web_backend/render.yaml` blueprint, or configure the service manually.
3. Build command: `pip install -r requirements.txt -r web_backend/requirements.txt`
4. Start command: `python -m uvicorn web_backend.main:app --host 0.0.0.0 --port $PORT`
5. Set `DATABASE_PATH` to a persistent disk path (the included blueprint uses `/var/data/smart_grocery.db`).
6. Set a long random `AUTH_SECRET` (Render blueprint can generate one).
7. Set a unique, high-entropy `OWNER_SETUP_KEY` before first use. Enter the same value in the first-owner setup screen. Never publish this key or put it in frontend source code.
8. Set `CORS_ORIGINS` to the exact Netlify site origin, e.g. `https://your-site.netlify.app`.

## Deploy frontend with Netlify Drop
1. In `web_frontend/app.js`, replace the default `http://localhost:8000` API base with the deployed backend URL, e.g. `https://your-api.onrender.com`.
2. Open https://app.netlify.com/drop and drag the `web_frontend` folder onto the page.
3. Set the backend `CORS_ORIGINS` environment variable to the exact deployed Netlify origin, redeploy the backend, then test login and data operations.

## Security model and limitations
- This web edition has a single-owner sign-in gate. Passwords are stored as salted PBKDF2-HMAC-SHA256 hashes; API requests require a signed, expiring bearer token. The first owner account is created once; later public registration is disabled.
- This is **not multi-tenant**: the authenticated owner controls one shared household database. Do not share the owner password. Separate user accounts, household membership/roles, per-household data isolation, password reset, rate limiting, audit logging, HTTPS-only cookie sessions and CSRF protections are not implemented. For a multi-household public SaaS, migrate the schema and queries to tenant-scoped PostgreSQL before opening registration.
- SQLite must be stored on a persistent disk in hosted environments. Backups should be made before schema changes or deployment.
- Netlify hosts only the frontend. It does not execute Python or host the SQLite database.
- Store prices are manually entered; there is no live retailer price feed.
- Some desktop workflows and settings still require browser-side UI parity work. See `WEB_FEATURE_MATRIX.md`.

## Tests
Run original regression tests:
`python -m unittest discover -s tests -v`

Compile Python files:
`python -m compileall -q app web_backend`

For the API, install the web requirements and run the API tests:
`python -m unittest discover -s web_backend/tests -v`

A passing desktop test suite does not prove every browser workflow or hosted configuration. Test the actual deployed URL before sharing it.
