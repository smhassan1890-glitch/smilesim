# Deploying to Coolify

This Django project ships with a production-grade `Dockerfile`, an
`entrypoint.sh` that runs migrations + `collectstatic` and then boots
gunicorn, and WhiteNoise for static-file serving. Coolify only needs to:

1. Build the Dockerfile.
2. Inject environment variables.
3. Route traffic from the configured domains to port `8000`.

---

## 1. Prerequisites

- A running Coolify instance (v4+) with a publicly reachable IP.
- DNS `A`/`AAAA` records pointing at the Coolify server for every
  hostname you plan to use. Recommended set:
  - `prosim.ps` (apex / marketing — optional)
  - `s.prosim.ps` (admin / management panel — **required**)

---

## 2. Create the Postgres database

1. In the Coolify UI: **New Resource → Database → PostgreSQL**.
2. Pick a name (e.g. `recharge-db`), accept defaults (Postgres 16 is fine),
   and create.
3. After it boots, open the database page and copy the **internal**
   `postgres://...` connection string. That is your `DATABASE_URL`.

> Use the **internal** URL (it resolves over Coolify's docker network)
> unless your app runs in a different project; only then use the public URL.

**Critical — persistent database:** Link the application to this Postgres
resource and set `DATABASE_URL` to its **internal** connection string.
Do **not** point production at SQLite (e.g. `sqlite:///app/db.sqlite3`) —
the app container filesystem is recreated on every deploy, so any SQLite
file is wiped and `migrate` re-seeds default settings from scratch.

In Coolify: open the Postgres service → confirm **Persistent Storage** is
enabled (a named volume on `/var/lib/postgresql/data`). If the database
is recreated on each deploy, all admin settings (system settings,
branding, users) will reset even though the code is correct.

---

## 3. Create the application

1. **New Resource → Application → Public Repository** (or **Private** if your
   GitHub repo is private — Coolify will walk you through the GitHub App
   install).
2. Repository: `https://github.com/smhassan1890-glitch/smilesim.git` (or whichever
   remote you push to).
3. Branch: `main` (or whatever branch you push to).
4. Build pack: **Dockerfile** (Coolify will autodetect the `Dockerfile` at
   the repo root).
5. Port: **8000**.
6. Health check path: `/healthz/` (returns `ok`).

---

## 4. Environment variables

Open the application → **Environment Variables** → paste in the keys
below. Replace placeholder values with your real ones. Every variable below is
documented in `.env.example` in the same order.

```env
# Django
DJANGO_SETTINGS_MODULE=config.settings.production
DJANGO_SECRET_KEY=<run: python -c "import secrets; print(secrets.token_urlsafe(64))">
DJANGO_DEBUG=0
DJANGO_ALLOWED_HOSTS=prosim.ps,s.prosim.ps
DJANGO_CSRF_TRUSTED_ORIGINS=https://prosim.ps,https://s.prosim.ps

# Database (paste the Postgres internal URL from step 2)
DATABASE_URL=postgres://USER:PASS@HOST:5432/DBNAME

# Coolify terminates TLS; do not let gunicorn issue another 301.
DJANGO_SECURE_SSL_REDIRECT=0
SECURE_HSTS_SECONDS=3600
SECURE_HSTS_INCLUDE_SUBDOMAINS=1
```

Optional knobs (defaults are fine for most deployments):

```env
GUNICORN_WORKERS=3
GUNICORN_THREADS=2
GUNICORN_TIMEOUT=60
DJANGO_LOG_LEVEL=INFO

# Sky Sales Portal (sales-ps.sky5g.ps) — Runtime only
SKY_SALES_USER=your_username
SKY_SALES_PASSWORD=your_password
SKY_SALES_TOTP_SECRET=XXXXXXXXXXXXXXXX
SKY_SALES_PROXY=http://LOGIN_s_skysales:PASSWORD@res.geonix.com:10000
SKY_SALES_SESSION_FILE=/app/data/.sky_sales_session.json
```

These are read from the real environment (or from the file named by
`SKY_SALES_ENV_FILE`); the old `sky_lab/.env` file is no longer read.
They are only needed for the Sky supplier reconcile page.

Use a **sticky session** in the Geonix username (e.g. `LOGIN_s_skysales`) so
login and report fetches share the same exit IP. Optional geo: `LOGIN_c_IL_s_skysales`.

Set **`SKY_SALES_PROXY`** from your Geonix residential list. Use **Runtime
only** in Coolify (never bake into the Docker image). Mount a persistent volume
at `/app/data` so `SKY_SALES_SESSION_FILE` survives redeploys.

> **Sky provider**: HTTP login + TOTP to `sales-ps.sky5g.ps:8888` — no browser
> required. Residential proxy required — datacenter IPs are rejected by Sky.

> **Important**: `DJANGO_ALLOWED_HOSTS` must list every hostname Coolify
> will route to this container. Forget one and Django answers `400 Bad
> Request` for that host.

---

## 5. Domains

In the application → **Domains** tab add the public hostname:

- `https://s.prosim.ps` → admin / management panel.

Coolify will request Let's Encrypt certificates automatically. Let it
issue them on its own — the first request can take a minute.

You can add `https://prosim.ps` too if the apex should also serve the
panel; just make sure it appears in `DJANGO_ALLOWED_HOSTS` /
`DJANGO_CSRF_TRUSTED_ORIGINS`.

---

## 6. Deploy

Hit **Deploy**. Watch the **Build Logs** then **Runtime Logs** tabs. On a
healthy boot you will see, in order:

```
[entrypoint] Running migrations...
Operations to perform: ...
[entrypoint] Collecting static files...
[entrypoint] Starting gunicorn on 0.0.0.0:8000
[INFO] Booting worker with pid: ...
```

Subsequent deploys redo migrations idempotently; Coolify handles the
rolling restart automatically.

---

## 7. First-time superuser

Coolify ships a per-container shell. Open the application → **Terminal**
(or **Commands → Open shell**) and run:

```bash
python manage.py createsuperuser
```

Enter username / email / password. Then visit
`https://s.prosim.ps/management/` (or your equivalent admin URL) and log in.

---

## 8. Smoke checks

Tick all of these before announcing the deploy is done:

- [ ] `curl -fsS https://s.prosim.ps/healthz/` → `ok`.
- [ ] `https://s.prosim.ps/` → login screen renders with CSS (proves
      WhiteNoise is serving static assets).
- [ ] Login as the superuser; open the operational snapshot, record one
      sale from the employee screen, and approve it.
- [ ] Open a Sky company → supplier reconcile and confirm the report loads.

---

## Updating / redeploying

1. **Back up the database first** (Coolify Postgres → **Backups → Backup
   now**, or `pg_dump -Fc "$DATABASE_URL" > before-deploy.dump`). Some
   releases drop tables — the release that removed phone refresh, the SMS
   gateway and SIM inventory drops all of their tables — so the backup is
   the only way back.
2. Push to the connected branch.
3. Coolify auto-deploys (or click **Redeploy**).
4. Migrations run automatically on container start via `entrypoint.sh`.

No extra steps unless you added a new env var — if you did, add it in
the **Environment Variables** tab before redeploying.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `DisallowedHost at /` | Hostname missing from `DJANGO_ALLOWED_HOSTS` | Add it, redeploy. |
| `CSRF verification failed` | Origin not in `DJANGO_CSRF_TRUSTED_ORIGINS` (and must be `https://`) | Add the `https://` origin, redeploy. |
| 502 from Coolify proxy | Container crashed during boot | Open **Runtime Logs**: usually a missing env var or DB unreachable. |
| Static files 404 / unstyled UI | `collectstatic` did not run | Check entrypoint logs; WhiteNoise needs `staticfiles/` populated. |
| Settings reset after every redeploy | `DATABASE_URL` uses SQLite inside the container, or Postgres has no persistent volume | Point `DATABASE_URL` at the Coolify Postgres internal URL; enable persistent storage on the DB service. Runtime logs show `Database engine=...postgresql...` on boot. |
| Sky reconcile fails with login/proxy error | Missing credentials, bad TOTP, or proxy rejected | Set `SKY_SALES_USER`, `SKY_SALES_PASSWORD`, `SKY_SALES_TOTP_SECRET`, and `SKY_SALES_PROXY` (Runtime only); check Runtime Logs for `proxy_error` / `login_error`. |
