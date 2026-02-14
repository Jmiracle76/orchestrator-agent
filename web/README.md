# Web Interface Scaffold

Thin Flask shell for the Orchestrator Agent UI with blueprints for core, documents, and health routes. Tailwind CSS powers the Codex-inspired layout.

## Running locally

```bash
pip install -r web/requirements.txt
export WEB_CONFIG=development  # or production
python -m web.app
```

Point your browser at `http://127.0.0.1:8000`.

## Configuration

- `WEB_CONFIG` / `FLASK_ENV`: `development` (debug, template reload) or `production`
- `WEB_LOG_FILE`: override log path (defaults to `web/logs/app.log`)
- `WEB_SECRET_KEY`: Flask secret key override
- `WEB_SESSION_DIR`: server-side session directory (defaults to `/tmp/orchestrator_sessions`, create with `700` perms)
- `WEB_SESSION_TTL_SECONDS`: session lifetime and cleanup horizon in seconds (defaults to 7 days)

## Logging

Logs write to both console and a rotating file with the format `%Y-%m-%d %H:%M:%S | LEVEL | logger | message`. Ensure the log directory is writable by the service user.

## CLI Wrapper

`web.cli_wrapper.run_requirements_cli` runs the requirements automation CLI as a subprocess, accepting the full set of CLI options (`--repo-root`, `--template`, `--doc`, `--dry-run`, `--no-commit`, `--log-level`, `--max-steps`, `--handler-config`, `--validate`, `--strict`). It captures stdout/stderr logs and any JSON payloads, returning a structured result with `status` (`success`, `error`, or `timeout`), exit code, parsed JSON blocks, and raw streams. Timeouts surface partial output with `status="timeout"` so API routes can relay what happened.

## Layout

- `web/__init__.py`: app factory, blueprint registration, logging
- `web/session_store.py`: Flask-Session setup, file-based storage, cleanup helpers
- `web/blueprints/session_api.py`: workflow session API (`/api/session/workflow`) backed by server-side session storage
- `web/config.py`: dev/prod config classes
- `web/blueprints/`: core, document, and health blueprints
- `web/templates/` and `web/static/`: Tailwind-backed UI shell
- `web/systemd/orchestrator-web.service`: systemd unit template

## Deployment

Install `web/systemd/orchestrator-web.service`, adjust `WorkingDirectory` and paths, then run:

```bash
sudo systemctl daemon-reload
sudo systemctl enable orchestrator-web
sudo systemctl start orchestrator-web
```
