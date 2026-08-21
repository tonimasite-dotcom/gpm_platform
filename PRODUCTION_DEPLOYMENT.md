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
under `/opt/gpm/backups`. The frontend is copied under `/opt/gpm/front-backups`
before every switch.

## Run a deployment

Open **Actions → Deploy production → Run workflow**, keep the branch set to
`main`, choose `all`, `backend`, or `frontend`, and start the run. Only one
production deployment can run at a time.
