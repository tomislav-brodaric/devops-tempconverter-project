# Docker Swarm deployment

Docker Swarm is the simpler orchestration system used by TempConverter. The
stack demonstrates the course requirements with three services:

- one MySQL 8.4 database on the manager node;
- two application replicas, with at most one replica per node;
- one small Nginx proxy on every node, publishing TCP port 80.

The proxy is retained because the nested Docker-in-Docker lab does not provide
reliable Swarm routing-mesh forwarding. Nginx uses Docker DNS to distribute
requests across the application replicas.

## Prerequisites

- one manager and at least two worker-capable Docker Engine nodes;
- three eligible nodes for the scale-to-three demonstration;
- the `tomislavb16/tempconverter:dev` image available from Docker Hub;
- the three external Secrets named in `stack.yaml`;
- port 80 available on every node.

Do not store passwords, join tokens, registry credentials, or Secret values in
this repository or in screenshots.

## Prepare the cluster privately

This is setup, not recording material. Both initialization and token commands
can print a Swarm join token, so run this section before OBS starts and keep the
output out of screenshots and transcripts.

Initialize a new manager only when it is not already part of a Swarm:

```text
docker swarm init --advertise-addr <MANAGER_IP>
docker swarm join-token worker
```

Run the generated join command privately on the workers, then verify the
cluster. Rotate the worker token privately after all workers have joined:

```text
docker swarm join-token --rotate worker
```

Only the following read-only check belongs in the demonstration:

```text
docker node ls
```

All three nodes must be `Ready` and `Active`.

## Create Secrets once

The existing course lab already contains these Secrets. For a new lab, create
them on the manager with the helper, without displaying their values:

```powershell
.\deploy\swarm\new_swarm_secret.ps1 -Name tempconverter_db_password
.\deploy\swarm\new_swarm_secret.ps1 -Name tempconverter_db_root_password
.\deploy\swarm\new_swarm_secret.ps1 -Name tempconverter_flask_secret_key
```

Confirm only their names:

```text
docker secret ls
```

## Validate and deploy

Set the public assignment image and the two non-secret identity values:

```powershell
$env:TEMPCONVERTER_IMAGE = "docker.io/tomislavb16/tempconverter:dev"
$env:STUDENT = "Tomislav Brodarić"
$env:COLLEGE = "Algebra Bernays University"
```

From the manager, validate and deploy:

```text
docker stack config --compose-file deploy/swarm/stack.yaml
docker stack deploy --compose-file deploy/swarm/stack.yaml tempconverter
```

## Verify the assignment baseline

```text
docker node ls
docker stack services tempconverter
docker service ps --filter desired-state=running tempconverter_app
```

In the nested three-node course lab, verify every published node endpoint:

The outer ports `8080`, `8081`, and `8082` map to port `80` on the three
nested Swarm nodes.

```powershell
Invoke-RestMethod http://127.0.0.1:8080/health
Invoke-RestMethod http://127.0.0.1:8081/health
Invoke-RestMethod http://127.0.0.1:8082/health
```

Expected baseline:

- `tempconverter_app` is `2/2` on two different nodes;
- `tempconverter_db` is `1/1`;
- `tempconverter_proxy` is `3/3` in the three-node lab;
- `/health` is healthy through port 80;
- a real conversion such as `100 -> 212` is stored.

## Scale from two to three and back

```text
docker service scale tempconverter_app=3
docker service ps --filter desired-state=running tempconverter_app
docker service scale tempconverter_app=2
docker stack services tempconverter
docker service ps --filter desired-state=running tempconverter_app
```

Repeat the three `/health` requests after scaling back down.

At three replicas, each task must run on a different node. Finish with the
`2/2`, `1/1`, and `3/3` baseline restored.

## Data boundary

`docker stack rm tempconverter` removes the services but intentionally leaves
the external Secrets and MySQL volume. Removing the volume, the manager data,
or the Secrets is a separate destructive action and is not part of the normal
demo procedure.

The local lab uses three Docker-in-Docker engines inside one Podman Machine.
It demonstrates real Swarm scheduling and scaling, but not physical-host high
availability.
