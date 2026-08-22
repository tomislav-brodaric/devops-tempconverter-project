# Kubernetes deployment

Kubernetes is the complex orchestration system used for the TempConverter
course project. This directory intentionally contains a small deployment that
matches the assignment requirements:

- one MySQL 8.4 database instance;
- two TempConverter application replicas;
- required pod anti-affinity so app replicas run on different nodes;
- Traefik Ingress and an internal Service that expose the app through TCP
  port 80;
- a documented scale operation from two to three app replicas.

The database credentials and Flask signing key remain in a runtime Kubernetes
Secret. The 2 GiB claim keeps demonstration data across database pod
replacement.

## Tracked resources

[`namespace.yaml`](namespace.yaml) creates the `tempconverter` namespace.

[`stack.yaml`](stack.yaml) contains six resources:

1. the existing `mysql-data-tempconverter-db-0` persistent volume claim;
2. the internal MySQL Service;
3. one MySQL Deployment replica;
4. the internal application Service on port 80;
5. two application Deployment replicas with required pod anti-affinity;
6. the Traefik Ingress.

The Secret is created at runtime and is not stored in Git.

## Prerequisites

- A Kubernetes cluster with at least two schedulable nodes for the baseline
  and three schedulable nodes for the scale demonstration.
- A `local-path` StorageClass. This is the default in the verified k3d/k3s
  lab. On another cluster, intentionally adapt the claim to its StorageClass.
- A Traefik IngressClass and a load-balancer entrypoint mapped to host port
  80.
- The public image
  `docker.io/tomislavb16/tempconverter:dev` available in the registry.
- `kubectl` and a POSIX shell for the Secret helper.

Do not put a password, Secret value, kubeconfig key, registry credential, CSRF
token, or cookie in this repository, a screenshot, or the project document.

## Fresh deployment

Create the namespace:

```sh
kubectl apply --filename deploy/kubernetes/namespace.yaml
```

Create the runtime Secret. The helper generates three independent random
hexadecimal values without printing them:

```sh
sh deploy/kubernetes/create-secrets.sh tempconverter
```

Validate and apply the deployment:

```sh
kubectl apply \
  --dry-run=server \
  --filename deploy/kubernetes/stack.yaml

kubectl apply --filename deploy/kubernetes/stack.yaml
```

Wait for the database and application:

```sh
kubectl rollout status \
  deployment/tempconverter-db \
  --namespace tempconverter \
  --timeout 5m

kubectl rollout status \
  deployment/tempconverter-app \
  --namespace tempconverter \
  --timeout 5m
```

The app can restart briefly if it reaches MySQL while MySQL is still starting.
Kubernetes retries the container, and the rollout converges after the database
accepts connections. On a fresh node, a slow first MySQL image pull can leave
the app in a longer backoff. After the database rollout is complete, restart
only the app Deployment and wait for its two replicas:

```sh
kubectl rollout restart \
  deployment/tempconverter-app \
  --namespace tempconverter

kubectl rollout status \
  deployment/tempconverter-app \
  --namespace tempconverter \
  --timeout 5m
```

## Verify the assignment baseline

Show all three nodes and the actual pod placement:

```sh
kubectl get nodes --output wide

kubectl get pods \
  --namespace tempconverter \
  --output wide
```

The expected baseline is one running database pod and two running app pods on
two different node names.

Show the persistent claim and port-80 Ingress:

```sh
kubectl get pvc,ingress \
  --namespace tempconverter \
  --output wide
```

Verify the complete Ingress -> Service -> app -> MySQL path:

```sh
curl --fail --show-error http://127.0.0.1/health
```

Expected response:

```text
{"status":"healthy"}
```

Open `http://127.0.0.1`, submit `100` Celsius, and confirm that the application
stores and displays `212` Fahrenheit.

## Scale to three replicas

```sh
kubectl scale \
  deployment/tempconverter-app \
  --namespace tempconverter \
  --replicas 3

kubectl rollout status \
  deployment/tempconverter-app \
  --namespace tempconverter \
  --timeout 5m

kubectl get pods \
  --namespace tempconverter \
  --selector app.kubernetes.io/component=application \
  --output wide
```

Required anti-affinity places the three pods on three different node names.
Return to the declared two-replica baseline after capturing the evidence:

```sh
kubectl scale \
  deployment/tempconverter-app \
  --namespace tempconverter \
  --replicas 2

kubectl rollout status \
  deployment/tempconverter-app \
  --namespace tempconverter \
  --timeout 5m

kubectl get pods \
  --namespace tempconverter \
  --selector app.kubernetes.io/component=application \
  --output wide

curl --fail --show-error http://127.0.0.1/health
```

## Existing deployment safety boundary

The fresh-deployment commands above are not a migration procedure for an
existing database workload. A live transition requires a verified logical
MySQL backup outside the cluster, a retained PVC and Secret, stopped
application writes, confirmation that the previous database pod has fully
stopped, and a tested rollback procedure. Review that plan separately before
changing an existing cluster. Never delete the namespace, PVC, PV, runtime
Secret, k3d cluster, or outer Podman volumes as part of a normal deployment.

## Secret helper boundary

For a fresh cluster, pass the target namespace:

```sh
sh deploy/kubernetes/create-secrets.sh tempconverter
```

The helper refuses to overwrite an existing Secret. Secret rotation is a
separate database-administration operation because changing the Kubernetes
value alone does not change a password stored inside an initialized MySQL data
directory.
