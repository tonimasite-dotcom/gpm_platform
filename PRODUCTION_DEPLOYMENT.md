# Production deployment

Production is deployed by the **Deploy production** GitHub Actions workflow.
The workflow is manual and always checks out `main`. It can deploy both services
or only `backend` / `frontend`.

## Required GitHub environment and secrets

Create the `production` environment in the repository and add these environment
secrets:

- `PROD_SSH_PRIVATE_KEY` — a dedicated Ed25519 private key accepted by both
  production servers.
- `PROD_SSH_KNOWN_HOSTS` — verified `known_hosts` lines for `46.149.71.147` and
  `186.246.10.163`.

Never commit either value to the repository. The frontend configuration created
by the workflow contains only the public API mode and URL.

## Deployment order and safeguards

For an `all` deployment the workflow:

1. analyzes and builds Flutter Web;
2. updates and verifies the backend;
3. uploads and atomically switches the frontend;
4. restores the previous frontend automatically if its public checks fail.

The backend deployment stops when tracked local changes exist on the production
checkout. Before updating it creates a Git bundle and records the previous commit
under `/opt/gpm/backups`. It installs the locked API dependencies into a
versioned virtualenv, validates the complete production runtime configuration,
runs backend tests and atomically switches `.venv`; rollback restores both the
previous commit and previous environment. The frontend is copied under
`/opt/gpm/front-backups` before every atomic switch.

Production must already contain three server-assigned accounts (`client`,
`worker`, `logist`) and must not contain legacy shared `GPM_APP_USERNAME`,
`GPM_APP_PASSWORD` or `GPM_APP_ROLE`. Account passwords remain only in the
root-owned server environment and never enter Actions logs or frontend assets.

## Run a deployment

Open **Actions → Deploy production → Run workflow**, keep the branch set to
`main`, choose `all`, `backend`, or `frontend`, and start the run. Only one
production deployment can run at a time.
