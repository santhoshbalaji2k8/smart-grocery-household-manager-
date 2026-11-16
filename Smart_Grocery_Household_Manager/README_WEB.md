# Smart Grocery & Household Manager — Web Edition

This repository keeps the original Python desktop application and adds a browser-based edition.

## Run the web edition locally

```bash
python -m pip install -r requirements.txt -r web_backend/requirements.txt
python -m uvicorn web_backend.main:app --reload
```

Open `web_frontend/index.html` in a browser. The default API address is `http://localhost:8000`. On first use, create the one-time owner account. For local development, use setup key `local-only-setup-key-change-me`. The password must be at least 12 characters and include letters and numbers. For deployment, configure a private `OWNER_SETUP_KEY` on the backend first.

## Deployment

Read [WEB_DEPLOYMENT.md](WEB_DEPLOYMENT.md) for full Render backend and Netlify Drop frontend instructions. Do not upload the original ZIP directly to Netlify; upload the `web_frontend` folder after setting its API URL.

## Important account model

This release uses a first-owner-only login for a single shared household database. It is not a multi-tenant public service. Do not give the owner credentials to other people. Separate household accounts and tenant-scoped PostgreSQL storage are future work before broad public registration.

## Coverage

See [WEB_FEATURE_MATRIX.md](WEB_FEATURE_MATRIX.md) for what is connected in the browser and what still has UI work remaining. The original desktop application is retained and can still be launched using `python run_app.py`.

## Windows installation troubleshooting
The backend requirements intentionally use core `uvicorn` rather than `uvicorn[standard]`. The optional standard extras can pull in PyYAML and other optional packages that may trigger native wheel builds on some Python/Windows combinations. The core server is sufficient here. Install with:

```bash
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt -r web_backend/requirements.txt
```

Start the local API with `python -m uvicorn web_backend.main:app --reload`.
