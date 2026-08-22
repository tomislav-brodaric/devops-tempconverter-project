# TempConverter DevOps Project

[![CI](https://github.com/tomislav-brodaric/devops-tempconverter-project/actions/workflows/ci.yml/badge.svg)](https://github.com/tomislav-brodaric/devops-tempconverter-project/actions/workflows/ci.yml)

TempConverter is a small Flask application that converts Celsius values to
Fahrenheit and stores valid conversions in MySQL. The page displays the ten
most recent records.

This repository is the technical deliverable for the **Intro to DevOps**
course at Algebra Bernays University, prepared by **Tomislav Brodarić**. Its
scope follows the assignment: a containerized application, automated tests,
CI, resource measurements, Docker Swarm, Kubernetes, and a comparison of the
two orchestration approaches.

## What the project contains

| Area | Implementation |
| --- | --- |
| Application | Flask form, Celsius-to-Fahrenheit conversion and MySQL persistence |
| Local deployment | Podman Compose with one app and one MySQL container |
| Tests | 4 unit/route tests and 2 MySQL integration tests |
| CI | One GitHub Actions job that tests and builds the image |
| Docker Swarm | 1 database, 2 app replicas, Nginx on port 80 and `2 -> 3 -> 2` scaling |
| Kubernetes | 1 database, 2 app replicas on different nodes, Ingress on port 80 and `2 -> 3 -> 2` scaling |
| Measurements | Container workload compared with the enclosing Podman Machine |

Generated reports, course templates, `.env` files, raw recordings and edited
videos are kept outside the public source history.

## Architecture

```text
Local:      browser -> Flask app -> MySQL

Swarm:     browser -> Nginx :80 -> 2 Flask replicas -> 1 MySQL replica

Kubernetes: browser -> Traefik Ingress :80 -> Service
                                      -> 2 Flask pods -> 1 MySQL pod + PVC
```

The application container runs as the non-root `appuser` account. The MySQL
application uses the non-root database account `tempconverter`.

## Prerequisites

- Podman Desktop with a running Podman Machine and Compose provider, or Docker
  Desktop with Docker Compose;
- Git;
- PowerShell for the included Windows measurement scripts;
- Node.js only when repeating the recorded HTTP load measurement;
- three Docker Engine nodes for the Swarm demonstration;
- a three-node Kubernetes cluster with Traefik for the Kubernetes scale
  demonstration.

## Local Compose deployment

Create the local configuration once:

```powershell
Copy-Item .env.example .env
```

Replace all example credentials and the student identity values in `.env`.
The file is ignored by Git and must never be committed.

Build and start the application:

```powershell
podman compose up --build --detach
podman compose ps
Invoke-RestMethod http://127.0.0.1:5000/health
```

Open `http://127.0.0.1:5000`, enter `100`, and confirm that the application
stores and displays `212` Fahrenheit.

Stop the containers without deleting the database volume:

```powershell
podman compose down
```

Do not add `--volumes` unless the stored local conversions may be permanently
deleted. Docker users can replace `podman compose` with `docker compose`.

## Configuration

| Variable | Purpose |
| --- | --- |
| `APP_BIND_ADDRESS` | Host address used by Compose, normally `127.0.0.1` |
| `APP_PORT` | Host application port, normally `5000` |
| `DB_NAME` | MySQL database name |
| `DB_USER` | Non-root MySQL application user |
| `DB_PASS` | MySQL application password |
| `DB_ROOT_PASS` | MySQL root password used only by the database container |
| `SECRET_KEY` | Flask form and session signing key |
| `STUDENT` | Student name displayed by the app |
| `COLLEGE` | College name displayed by the app |

The database is not published to a host port. Only the application is bound
to loopback by the local Compose configuration.

## Build and tests

Build the local validation image:

```powershell
podman build --file Dockerfile --tag localhost/tempconverter:dev .
```

Run the four unit and route tests inside that image:

```powershell
podman run --rm `
  --network none `
  --volume "${PWD}:/workspace:ro" `
  --workdir /workspace `
  --entrypoint python `
  localhost/tempconverter:dev `
  -m unittest discover -s tests/unit -p "test_*.py" -v
```

The two integration tests use a real but temporary MySQL 8.4 instance and a
non-root test account. The same sequence is automated in CI, where the test
database exists only for the duration of the job.

Run that isolated database and the two integration tests locally:

```powershell
podman network create tempconverter-test
podman run --detach --name tempconverter-test-db `
  --network tempconverter-test `
  --env MYSQL_DATABASE=tempconverter_test `
  --env MYSQL_USER=tempconverter_test `
  --env MYSQL_PASSWORD=integration_test_password `
  --env MYSQL_ROOT_PASSWORD=integration_root_password `
  mysql:8.4

podman exec tempconverter-test-db mysqladmin ping `
  --host=127.0.0.1 --user=root `
  --password=integration_root_password --wait=60

podman run --rm --network tempconverter-test `
  --env TEST_DATABASE_URL=mysql+pymysql://tempconverter_test:integration_test_password@tempconverter-test-db:3306/tempconverter_test `
  --volume "${PWD}:/workspace:ro" --workdir /workspace `
  --entrypoint python localhost/tempconverter:dev `
  -m unittest discover -s tests/integration -t . -p "test_*.py" -v

podman rm --force tempconverter-test-db
podman network rm tempconverter-test
```

The credentials above belong only to the disposable test database.

## Continuous integration

The workflow in [`.github/workflows/ci.yml`](.github/workflows/ci.yml) runs on
pushes, pull requests and manual dispatches. One readable job performs these
steps in order:

1. starts an ephemeral MySQL 8.4 service;
2. installs the Python requirements;
3. runs 4 unit/route tests;
4. runs 2 MySQL integration tests;
5. builds the application image.

The workflow has read-only repository permission and contains only disposable
test credentials.

## Container image

The course image repository is
[`tomislavb16/tempconverter`](https://hub.docker.com/r/tomislavb16/tempconverter).
The assignment-facing `latest` and `dev` tags are mutable demonstration tags.
Build and test a new candidate before updating either tag.

```powershell
podman build --file Dockerfile --tag tomislavb16/tempconverter:dev .
podman tag `
  tomislavb16/tempconverter:dev `
  tomislavb16/tempconverter:latest
podman push tomislavb16/tempconverter:dev
podman push tomislavb16/tempconverter:latest
```

Do not put registry credentials in the repository, screenshots or report.

## Resource measurement

The repository contains a PowerShell sampler, a small HTTP load generator and
a Python summarizer. The current image measurement and its limitations are
documented in
[`docs/measurements/2026-08-21-resource-comparison.md`](docs/measurements/2026-08-21-resource-comparison.md).
This is the single assignment-facing resource measurement result.

The comparison is intentionally modest: it contrasts the app/database
container workload with the complete Podman Machine working set. It is not a
claim that the difference is solely virtualization overhead.

## Docker Swarm

The simple-orchestrator template is in
[`deploy/swarm/stack.yaml`](deploy/swarm/stack.yaml). It deploys:

- one MySQL replica on the manager;
- two application replicas with at most one per node;
- one global Nginx proxy on every node, publishing host port 80;
- one overlay network and persistent MySQL storage.

Nginx is retained because the course lab runs three nested Docker nodes inside
one Podman Machine; it provides the reliable port-80 path that a normal
multi-host Swarm routing mesh would otherwise provide.

The complete deploy, verification and scale procedure is in
[`deploy/swarm/README.md`](deploy/swarm/README.md). The required evidence is
app `2/2`, database `1/1`, proxy `3/3`, a real conversion, scale to three app
replicas and return to two.

## Kubernetes

The complex-orchestrator template is in
[`deploy/kubernetes/stack.yaml`](deploy/kubernetes/stack.yaml). It deploys:

- one MySQL Deployment using the existing persistent claim;
- two application pods with required hostname anti-affinity;
- an internal Service and Traefik Ingress on port 80;
- a runtime Secret whose values are never committed.

The complete fresh-deployment, safety, verification and scale procedure is in
[`deploy/kubernetes/README.md`](deploy/kubernetes/README.md). The required
evidence is three Ready nodes, one database pod, two app pods on different
nodes, a real conversion, scale to three app pods and return to two.

## Swarm and Kubernetes comparison

Swarm is easier to understand and deploy for a small Docker-based stack.
Kubernetes uses more resource types and concepts, but offers a broader
ecosystem and more explicit scheduling and service abstractions. Both are
implemented here because the assignment asks for one simpler and one more
complex orchestration approach.

The recorded comparison is in
[`docs/2026-07-30-orchestrator-comparison.md`](docs/2026-07-30-orchestrator-comparison.md).

## Repository layout

```text
.
|-- .github/workflows/ci.yml   one test-and-build workflow
|-- app.py                     Flask application and SQLAlchemy model
|-- compose.yaml               local app and MySQL deployment
|-- deploy/
|   |-- swarm/                 Swarm stack, Nginx config and instructions
|   `-- kubernetes/            Kubernetes manifests and instructions
|-- docs/                      measurements and dated technical evidence
|-- scripts/                   measurement and load utilities
|-- templates/index.html       application interface
`-- tests/                     4 unit/route + 2 MySQL integration tests
```

## Data and security boundaries

- Every valid conversion is stored with a peer IP address and a shortened
  User-Agent; the page displays only the ten newest rows.
- There is no automatic retention policy, so the app should not be exposed as
  a public production service without one.
- Local `.env`, Swarm Secrets and the Kubernetes runtime Secret must remain
  outside source history.
- `compose down --volumes`, deletion of the Swarm database volume, deletion of
  the Kubernetes PVC/namespace, and cluster/volume pruning destroy data.

See [`SECURITY.md`](SECURITY.md) for the reporting and secret-handling policy.

## Provenance and licensing

This repository began from the
[`jstanesic/tempconverter`](https://github.com/jstanesic/tempconverter) course
starter and was extended for the assignment. See [`NOTICE.md`](NOTICE.md) for
the attribution boundary.

Neither the referenced starter nor this repository currently contains a
software license. Public visibility supports academic review but does not by
itself grant redistribution rights.
