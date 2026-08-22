# Container and Podman Machine Resource Comparison

## Result

The current `python app.py` image was measured on 2026-08-21 in the isolated
Compose project `tempconverter-measure-20260821`. The application image was
`localhost/tempconverter:dev` with image ID
`b50d01b7b2022bb3e6bdf3618ad3680b3047d0b7238eb1dd541902eb7ccbfadc`.

The experiment collected 10 idle and 10 load samples. During the 40.028-second
load run, all 10,756 health requests returned HTTP 200 and none failed.

| Scenario | App + DB CPU mean | Podman Machine CPU mean | App + DB memory mean | Podman Machine working set mean |
| --- | ---: | ---: | ---: | ---: |
| Idle | 1.504% | 90.5% | 547.5 MiB | 6,626.482 MiB |
| Load | 203.733% | 467.3% | 554.1 MiB | 6,650.485 MiB |

Container CPU uses the convention that 100% equals one fully used logical CPU
core. The Windows `vmmemWSL` CPU counter can also exceed 100% because it covers
multiple logical processors.

The measured container workload used about 547.5 MiB at idle and 554.1 MiB
under load. The enclosing WSL/Podman Machine working set was about 6.47 GiB in
both scenarios. Its working set was approximately 12 times the memory reported
for the two measured containers.

This difference is not pure virtualization overhead. `vmmemWSL` included the
Linux kernel, Podman, networking, the measured containers, and other active
course labs that were intentionally left running. The valid conclusion is
limited: the complete local VM environment had a much larger memory footprint
than the isolated app and database containers measured inside it.

## Load response

| HTTP measure | Result |
| --- | ---: |
| Duration | 40.028 s |
| Concurrency | 10 |
| Successful requests | 10,756 |
| Failed requests | 0 |
| Throughput | 268.713 requests/s |
| Mean latency | 37.178 ms |
| p50 latency | 33.788 ms |
| p95 latency | 54.820 ms |
| p99 latency | 122.128 ms |
| Maximum latency | 177.148 ms |

The post-load `/health` request also returned `{"status":"healthy"}`.

## Component observations

| Component | Idle CPU mean | Load CPU mean | Idle memory mean | Load memory mean |
| --- | ---: | ---: | ---: | ---: |
| Flask application | 0.028% | 185.748% | 95.2 MiB | 100.690 MiB |
| MySQL 8.4 | 1.476% | 17.985% | 452.3 MiB | 453.410 MiB |

The application produced 91.2% of the measured container CPU during load,
while MySQL accounted for most container memory. Combined container memory
increased by 6.6 MiB and the VM working set increased by 24.003 MiB between the
two short scenarios.

## Environment

| Item | Measured value |
| --- | --- |
| Host | Windows 11 Pro, version 10.0.26200, build 26200 |
| CPU | Intel Core i7-12700H, 20 logical processors |
| Host memory | Approximately 31.7 GiB |
| Podman client/server | 6.1.0 / 6.1.0 |
| Podman Machine configuration | 10 CPUs, 2,048 MiB memory, 100 GiB disk, rootless |
| Application image | 178,621,356 bytes, Linux amd64, `appuser`, `python app.py` |
| Database image | MySQL 8.4, 832,221,844 bytes, Linux amd64 |
| Local endpoint | `http://127.0.0.1:5600/health` |

The configured 2 GiB Podman Machine value and the larger observed `vmmemWSL`
working set are both retained. WSL resource accounting is inclusive and does
not behave like a fixed-size traditional VM measurement.

## Method

- The PowerShell sampler read `CPUNano`, `SystemNano`, memory and PID values
  from `podman stats` for only the isolated app and DB container names.
- Container CPU was calculated from counter deltas between samples.
- Windows `Win32_PerfFormattedData_PerfProc_Process` supplied the inclusive
  `vmmemWSL` CPU, working-set and private-memory counters.
- Ten ordered samples were collected for each scenario with a requested
  one-second delay. Command execution made the sample spans longer than ten
  seconds.
- The load generator sent concurrent read-only requests to `/health`, which
  also executes a database `SELECT 1`.
- The summarizer rejected missing columns, invalid scenario labels, unordered
  samples, non-increasing timestamps, non-finite numbers and HTTP failures.

The sampler requires explicit container names so it cannot silently measure
the unrelated live Compose deployment:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\measure_resources.ps1 `
  -Scenario idle -Samples 10 -IntervalSeconds 1 `
  -OutputPath .\docs\measurements\2026-08-21-idle.csv `
  -AppContainerName tempconverter-measure-20260821-app-1 `
  -DbContainerName tempconverter-measure-20260821-db-1
```

For load, run the generator in one terminal and repeat the sampler with
`-Scenario load` in another:

```powershell
node .\scripts\load_health.js http://127.0.0.1:5600/health 40 10 `
  .\docs\measurements\2026-08-21-load-http.json

powershell -ExecutionPolicy Bypass -File .\scripts\measure_resources.ps1 `
  -Scenario load -Samples 10 -IntervalSeconds 1 `
  -OutputPath .\docs\measurements\2026-08-21-load.csv `
  -AppContainerName tempconverter-measure-20260821-app-1 `
  -DbContainerName tempconverter-measure-20260821-db-1
```

Validate the evidence:

```powershell
python .\scripts\summarize_resources.py `
  --idle .\docs\measurements\2026-08-21-idle.csv `
  --load .\docs\measurements\2026-08-21-load.csv `
  --http .\docs\measurements\2026-08-21-load-http.json `
  --output .\docs\measurements\2026-08-21-summary.json
```

## Limitations

1. Ten samples per scenario and one load run demonstrate the procedure but do
   not establish long-term capacity or stable tail latency.
2. The VM boundary contains other active WSL and course workloads, so its
   absolute CPU and memory values cannot be attributed only to TempConverter.
3. Container and VM CPU counters use different accounting boundaries.
4. The load exercised the health path, not conversion writes.
5. With only 10 resource samples, nearest-rank p95 equals the maximum sample.

## Evidence files

- [`2026-08-21-idle.csv`](2026-08-21-idle.csv)
- [`2026-08-21-load.csv`](2026-08-21-load.csv)
- [`2026-08-21-load-http.json`](2026-08-21-load-http.json)
- [`2026-08-21-summary.json`](2026-08-21-summary.json)
- [`scripts/measure_resources.ps1`](../../scripts/measure_resources.ps1)
- [`scripts/load_health.js`](../../scripts/load_health.js)
- [`scripts/summarize_resources.py`](../../scripts/summarize_resources.py)

This 2026-08-21 set is the single assignment-facing measurement result.
