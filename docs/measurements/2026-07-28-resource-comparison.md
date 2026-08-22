# Container Workload and Podman Machine Resource Comparison

> **Historical measurement baseline.** These values were collected with the
> earlier multi-process application image. They preserve the assignment's
> measurement method and raw evidence, but they must not be presented as
> performance results for the current `python app.py` image until that image is
> measured with the same procedure.

- Measurement date: 2026-07-28
- Application endpoint: `http://127.0.0.1:5000/health`
- Scenarios: idle and sustained read-only health-check load

## Technical summary

During a 40.04-second load run, the deployed application completed all 9,135
requests successfully (228.145 requests/second, 0 failures). The application
and database containers together used a mean 139.195% CPU, where 100% equals
one fully utilized logical CPU core, and 564.414 MiB of cgroup-accounted memory.
The enclosing `vmmemWSL` process used a mean 188.2% CPU and 1,391.363 MiB of
working-set memory during the same load scenario.

The VM working set was approximately 2.47 times the summed container memory in
both scenarios. This is an observed footprint difference, not a causal estimate
of virtualization overhead: `vmmemWSL` includes the Linux kernel, Podman
Machine, container runtime, networking, both containers, and any other active
WSL/Podman work. The experiment therefore compares the deployed container
workload with its enclosing VM footprint. It is not a matched benchmark against
the same application installed directly in a separate clean VM.

## The load increased CPU sharply while memory remained stable

| Scenario | Container CPU mean | Container CPU median | Container CPU p95* | VM CPU mean | VM CPU median | VM CPU p95* | Container memory mean | VM working set mean | VM private memory mean |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Idle | 2.295% | 1.837% | 3.527% | 7.1% | 5.0% | 18.0% | 559.920 MiB | 1,383.300 MiB | 1,917.225 MiB |
| Load | 139.195% | 139.213% | 141.162% | 188.2% | 182.5% | 222.0% | 564.414 MiB | 1,391.363 MiB | 1,970.949 MiB |

\* With only 10 observations per scenario, nearest-rank p95 is the maximum
observed value and should not be interpreted as a stable tail estimate.

Mean container CPU was 60.651 times its idle value under load. Mean VM CPU was
26.507 times its idle value. Container memory increased by only 4.494 MiB, and
VM working-set memory increased by 8.063 MiB. This indicates that the selected
read-only workload was CPU-bound over the measured interval and did not produce
meaningful memory growth.

The difference between VM working-set memory and summed container memory was
823.380 MiB at idle and 826.949 MiB under load. The observed mean CPU values
differed by 49.005 percentage points under load. These differences must not be
labelled as pure VM overhead because the two measurement surfaces include
different processes and accounting boundaries.

## The application generated most load CPU; MySQL dominated container memory

| Component | Idle CPU mean | Load CPU mean | Idle memory mean | Load memory mean | Idle PIDs | Load PIDs |
|---|---:|---:|---:|---:|---:|---:|
| Flask application (previous image) | 0.055% | 124.615% | 88.620 MiB | 92.614 MiB | 8 | 8 |
| MySQL database | 2.240% | 14.579% | 471.300 MiB | 471.800 MiB | 46 | 48 |
| Combined | 2.295% | 139.195% | 559.920 MiB | 564.414 MiB | 54 | 56 |

The application accounted for 89.5% of mean container CPU during load. MySQL
accounted for 83.6% of combined container memory during load. The health
endpoint executes `SELECT 1`, so the database participated in every request,
but the test performed no application data writes.

## The service remained healthy throughout the run

| HTTP measure | Result |
|---|---:|
| Requested duration | 40 seconds |
| Measured duration | 40.04 seconds |
| Concurrency | 10 |
| Total requests | 9,135 |
| HTTP 200 responses | 9,135 |
| Failed requests | 0 |
| Throughput | 228.145 requests/second |
| Mean latency | 43.697 ms |
| p50 latency | 41.809 ms |
| p95 latency | 61.824 ms |
| p99 latency | 76.490 ms |
| Maximum latency | 129.926 ms |

The post-load `/health` check also returned HTTP 200 with
`{"status":"healthy"}`. This supports a descriptive claim that the deployed
service remained available during and immediately after this specific run. It
does not establish a long-duration capacity limit or production service-level
objective.

## Scope, environment, and metric definitions

### Environment

| Item | Observed value |
|---|---|
| Host | Windows 11 Pro, version 10.0.26200 (build 26200) |
| Host CPU | Intel Core i7-12700H, 20 logical processors |
| Host memory | Approximately 31.7 GiB |
| Podman client/server | 6.0.1 / 6.0.2 |
| Podman Machine mode | Rootless |
| Podman Machine configuration | 10 CPUs, 2,048 MiB memory, 100 GiB disk |
| Linux kernel | `6.6.87.2-microsoft-standard-WSL2` |
| Container cgroups | v2 |
| Network backend | Netavark |
| Application image | `localhost/tempconverter:dev` |
| Database image | `docker.io/library/mysql:8.4` |
| Application image size | 191,911,147 bytes (approximately 183.0 MiB) |
| Database image size | 832,172,179 bytes (approximately 793.6 MiB) |

The Linux guest reported 20 CPUs and approximately 15.47 GiB of visible memory,
which does not match the 10 CPU / 2 GiB values returned by
`podman machine inspect`. The WSL-based runtime can dynamically expose host
resources, so both observations are retained rather than silently choosing one
as authoritative.

The two image sizes sum to approximately 976.6 MiB, but this is not a disk
footprint total because container images can share layers. At measurement time,
`podman system df` reported 1.161 GB across 43 images, 218.4 MB in the active
local volume, and only 50.02 kB in writable container layers. The WSL filesystem
reported a logical size inconsistent with the configured Podman Machine disk,
so it is not used as evidence of physical VM disk consumption.

### Metrics and boundaries

- **Container CPU:** interval delta of Podman's `CPUNano` divided by the
  interval delta of `SystemNano`, multiplied by 100. A value of 100% represents
  one fully utilized logical CPU core.
- **Container memory:** current cgroup memory usage from Podman for the
  application and database, summed in MiB.
- **VM CPU and memory:** Windows
  `Win32_PerfFormattedData_PerfProc_Process` counters for `vmmemWSL`.
  This is an inclusive WSL VM boundary.
- **Working set:** VM memory currently resident in physical RAM.
- **Private memory:** committed private bytes attributed to the VM process.
- **p95:** nearest-rank percentile calculated separately for each 10-row
  scenario.
- **Idle baseline:** no intentional requests during collection.
- **Load cohort:** only GET requests to `/health`, with concurrency 10.

## Methodology and reproducibility

The idle and load resource files each contain 10 ordered interval observations.
The requested delay between observations was one second; Podman and Windows
counter collection added execution time, so each recorded series spans
approximately 20 seconds. The resource collection interval during the load
scenario was fully contained inside the 40-second HTTP run.

The raw Podman counter fields were used rather than a locale-formatted
human-readable CPU percentage. The analysis script validates required columns,
scenario labels, contiguous sample numbers, strictly increasing timestamps,
finite nonnegative numeric values, and HTTP failure count before producing the
summary.

Reproduction requires the existing local stack to be healthy:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\measure_resources.ps1 `
  -Scenario idle -Samples 10 -IntervalSeconds 1 `
  -OutputPath .\docs\measurements\2026-07-28-idle.csv `
  -AppContainerName tempconverter-app-1 `
  -DbContainerName tempconverter-db-1
```

For the load scenario, start the following load generator in one terminal:

```powershell
node .\scripts\load_health.js http://127.0.0.1:5000/health 40 10 `
  .\docs\measurements\2026-07-28-load-http.json
```

While it is running, start the resource sampler in a second terminal:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\measure_resources.ps1 `
  -Scenario load -Samples 10 -IntervalSeconds 1 `
  -OutputPath .\docs\measurements\2026-07-28-load.csv `
  -AppContainerName tempconverter-app-1 `
  -DbContainerName tempconverter-db-1
```

Then validate and summarize the artifacts in an isolated container, without
requiring Python on the Windows host:

```powershell
podman run --rm `
  --network none `
  --volume "${PWD}:/workspace" `
  --workdir /workspace `
  --entrypoint python `
  localhost/tempconverter:dev `
  scripts/summarize_resources.py `
  --idle docs/measurements/2026-07-28-idle.csv `
  --load docs/measurements/2026-07-28-load.csv `
  --http docs/measurements/2026-07-28-load-http.json `
  --output docs/measurements/2026-07-28-summary.json
```

## Limitations and robustness

1. **The VM comparator is inclusive.** It contains the measured containers plus
   the guest kernel and runtime. A clean VM with the same application installed
   directly was not measured.
2. **The sample is short.** Ten resource observations per scenario are enough
   to demonstrate a repeatable procedure, but not to characterize long-term
   variance or stable tail percentiles.
3. **CPU counters have different boundaries.** Container CPU comes from cgroup
   deltas; VM CPU comes from a Windows process counter. The observed gap is
   descriptive, not a decomposed overhead calculation.
4. **The measured image predates the current academic version.** The deployed
   `/health` behavior used by this benchmark is unchanged, but the current
   image must be measured before these numbers are claimed as current results.
5. **The local network workaround disables the Podman firewall driver.** It is
   a temporary response to a Netavark/WSL kernel incompatibility and is not a
   production security configuration. The run used only the loopback endpoint.
6. **Network I/O was excluded.** Rootless Podman environments may not expose
   complete network statistics, and this experiment did not rely on those
   counters.
7. **No secrets are embedded.** The procedure uses the existing deployment
   environment but records no `.env` values.

The strongest internal robustness result is consistency during load: container
CPU ranged from 137.490% to 141.162%, and container memory from 564.140 MiB to
564.880 MiB, while every HTTP request succeeded. Idle VM CPU was burstier
(0–18%), which is why both mean and median are reported.

## Recommended next experiment

For a defensible container-versus-VM efficiency claim, provision a dedicated
clean VM with fixed CPU and memory limits, install the same application and
MySQL versions directly in that VM, replay the same request sequence, and
collect counters at the same cadence. Repeat both scenarios multiple times
after warm-up and report confidence intervals or at least between-run ranges.

Before repeating the current container benchmark, rebuild the application image
from the current source, verify its image digest, rerun unit and integration
tests, and record the new deployment identity.

## Evidence files and external reference

- `2026-07-28-idle.csv` — raw idle observations
- `2026-07-28-load.csv` — raw load observations
- `2026-07-28-load-http.json` — HTTP workload result
- `2026-07-28-summary.json` — validated aggregate statistics
- `scripts/measure_resources.ps1` — resource sampler
- `scripts/load_health.js` — dependency-free load generator
- `scripts/summarize_resources.py` — validation and aggregation
- Podman documentation: <https://docs.podman.io/en/latest/markdown/podman-stats.1.html>

## Further questions

- How does the result change with a conversion endpoint workload rather than
  the lightweight health endpoint?
- What is the steady-state behavior over 10–30 minutes and across repeated
  runs?
- How much of the inclusive VM footprint remains after the application and
  database containers are stopped?
- Does a freshly rebuilt application image change CPU, memory, or latency?
