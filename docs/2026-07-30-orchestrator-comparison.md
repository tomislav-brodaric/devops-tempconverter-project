# Docker Swarm and Kubernetes comparison

## Decision summary

TempConverter uses Docker Swarm as the simpler orchestration approach and
Kubernetes through k3s/k3d as the more complex approach.

Both deployments implement the same assignment baseline:

- one MySQL database instance;
- two application replicas on different nodes;
- external access through TCP port 80;
- a real `100 °C -> 212 °F` conversion;
- scale from two to three application replicas and return to two.

## Implementation comparison

| Area | Docker Swarm | Kubernetes |
| --- | --- | --- |
| Main source | One stack file and one Nginx config | Namespace file and one six-resource manifest |
| Application | Replicated service with 2 tasks | Deployment with 2 pods |
| Replica separation | `max_replicas_per_node: 1` | Required hostname pod anti-affinity |
| Database | Replicated service with 1 task and named volume | Deployment with 1 pod and a 2 GiB PVC |
| External traffic | Global Nginx service publishes port 80 | Traefik Ingress routes to a Service on port 80 |
| Internal network | Swarm overlay network | Kubernetes Services and cluster networking |
| Secrets | Three external Swarm Secrets | One runtime Kubernetes Secret |
| Scaling | `docker service scale` | `kubectl scale deployment` |
| Baseline evidence | app `2/2`, DB `1/1`, proxy `3/3` | 2 Ready app pods on different nodes and 1 DB pod |

The global Nginx proxy is required by this particular nested Swarm lab. The
three Docker nodes run inside one Podman Machine, where the ordinary routing
mesh did not provide a reliable host-port path. Nginx publishes port 80 on
each node and load-balances the DNSRR application tasks.

Kubernetes needs more object types and commands. In return, it makes the
application Service, Ingress, persistent claim and scheduling rule explicit.

## Local resource observation

The following point-in-time outer-container measurements were collected on
2026-07-30 after both labs had returned to the two-app/one-database baseline.

| Local lab | Measured outer scope | CPU snapshot | RAM snapshot |
| --- | --- | ---: | ---: |
| Swarm | manager + two worker DIND containers | 11.67% | about 1.70 GB |
| Kubernetes | one DIND host containing the k3d cluster | 32.97% | 2.877 GB |

These values compare two different local lab topologies on one workstation.
They are useful as a bounded observation, not as a general product benchmark:

- both labs shared one WSL virtual machine;
- the Swarm total covers three nested Docker Engine containers;
- Kubernetes also includes its API server, scheduler, controllers, CoreDNS,
  Traefik, ServiceLB and local-path provisioner;
- CPU values are short snapshots, not a controlled time series;
- neither lab represents physical multi-host high availability.

The observation supports only a modest conclusion: this local Kubernetes lab
used more resources than the smaller Swarm lab for the same application.

## Troubleshooting lessons

Three issues from the local labs directly shaped the final templates:

1. **The application could start before MySQL was ready.** Early connections
   failed even though both containers were running. The local Compose file now
   waits for the MySQL health check before starting the app. The orchestrated
   deployments use restart behavior so the app converges after MySQL accepts
   connections.
2. **Swarm routing-mesh forwarding was unreliable in the nested lab.** The
   three Docker nodes run inside one Podman Machine, so a small global Nginx
   service publishes port 80 on each node and forwards to the DNSRR app tasks.
   Health checks on all three mapped node ports verify the workaround.
3. **The existing Kubernetes Secret format did not match direct environment
   injection.** Earlier file-backed values contained trailing line endings.
   The Secret helper can normalize those values without printing them, while
   the PVC and logical database passwords remain unchanged. A live transition
   still requires backup and rollback checks.

## Simpler-environment recommendation

Choose Swarm when the environment is small, Docker Engine is already in use,
and the main needs are service replication, placement, a shared network,
secrets and simple scaling. Its stack is shorter and easier to explain.

For TempConverter, Swarm is the clearer fit for the assignment's simple
orchestration target.

## Complex-environment recommendation

Choose Kubernetes when the environment needs explicit workload, networking,
Ingress, storage and scheduling objects or expects to grow into the broader
Kubernetes ecosystem. This flexibility introduces more concepts and a larger
operational surface.

For TempConverter, Kubernetes is the appropriate complex target because it
expresses Ingress, Services, a persistent claim and hard pod separation as
separate resources.

## Conclusion

Both orchestrators satisfy the functional assignment baseline. Swarm reaches
it with fewer concepts, while Kubernetes reaches it through a more structured
set of APIs. Neither nested local lab is production infrastructure; a real
production decision would additionally require multi-host failure tests,
backup and restore tests, TLS, observability, upgrade planning and a security
review.

## References

1. Docker, “Swarm mode key concepts.”
   <https://docs.docker.com/engine/swarm/key-concepts/>
2. Docker, “Deploy services to a swarm.”
   <https://docs.docker.com/engine/swarm/services/>
3. Kubernetes, “Deployments.”
   <https://kubernetes.io/docs/concepts/workloads/controllers/deployment/>
4. Kubernetes, “Service.”
   <https://kubernetes.io/docs/concepts/services-networking/service/>
5. Kubernetes, “Ingress.”
   <https://kubernetes.io/docs/concepts/services-networking/ingress/>
6. Kubernetes, “Persistent Volumes.”
   <https://kubernetes.io/docs/concepts/storage/persistent-volumes/>
