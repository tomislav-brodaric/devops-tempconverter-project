# Security policy

TempConverter is an academic staging project, not a hosted production service.
Only the latest commit on the default branch is intended to receive security
fixes.

## Reporting a vulnerability

Do not include credentials, tokens, private keys, kubeconfig content, personal
data, vulnerability details, or an exploit payload in a public issue. Private
Vulnerability Reporting is not currently configured. Until it is enabled, open
a minimal public issue containing no technical details or secrets and ask the
repository owner to establish a private reporting channel. Continue only in
that private channel and share the minimum information needed to reproduce the
problem.

If a secret may have been exposed, revoke or rotate it first. Removing a value
from the current working tree does not remove it from Git history.

## Deployment boundary

The Compose, Swarm, and Kubernetes configurations demonstrate course
requirements in local staging environments. Before any Internet-facing use,
add TLS, authentication/authorization, backups, monitoring, a migration
process, a privacy/retention policy, and environment-specific secret rotation.
