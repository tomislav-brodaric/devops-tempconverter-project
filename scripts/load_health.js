const fs = require("node:fs");
const http = require("node:http");
const { performance } = require("node:perf_hooks");
const path = require("node:path");

const target = process.argv[2] || "http://127.0.0.1:5000/health";
const durationSeconds = Number(process.argv[3] || 30);
const concurrency = Number(process.argv[4] || 10);
const outputPath = process.argv[5];

if (!Number.isFinite(durationSeconds) || durationSeconds <= 0) {
  throw new Error("durationSeconds must be a positive number");
}

if (!Number.isInteger(concurrency) || concurrency <= 0) {
  throw new Error("concurrency must be a positive integer");
}

const url = new URL(target);
const agent = new http.Agent({
  keepAlive: true,
  maxSockets: concurrency,
  maxFreeSockets: concurrency,
});
const latencies = [];
const statusCodes = {};
let successfulRequests = 0;
let failedRequests = 0;

function percentile(sortedValues, percentileValue) {
  if (sortedValues.length === 0) {
    return null;
  }

  const index = Math.min(
    sortedValues.length - 1,
    Math.ceil((percentileValue / 100) * sortedValues.length) - 1,
  );
  return sortedValues[Math.max(0, index)];
}

function rounded(value) {
  return value === null ? null : Number(value.toFixed(3));
}

function requestHealth() {
  return new Promise((resolve) => {
    const startedAt = performance.now();
    const request = http.get(
      url,
      {
        agent,
        timeout: 5000,
        headers: { Accept: "application/json" },
      },
      (response) => {
        response.resume();
        response.on("end", () => {
          const elapsed = performance.now() - startedAt;
          latencies.push(elapsed);
          const status = String(response.statusCode);
          statusCodes[status] = (statusCodes[status] || 0) + 1;
          if (response.statusCode === 200) {
            successfulRequests += 1;
          } else {
            failedRequests += 1;
          }
          resolve();
        });
      },
    );

    request.on("timeout", () => {
      request.destroy(new Error("request timeout"));
    });
    request.on("error", () => {
      failedRequests += 1;
      resolve();
    });
  });
}

async function worker(deadline) {
  while (performance.now() < deadline) {
    await requestHealth();
  }
}

async function main() {
  const startedAt = performance.now();
  const deadline = startedAt + durationSeconds * 1000;
  await Promise.all(
    Array.from({ length: concurrency }, () => worker(deadline)),
  );
  agent.destroy();

  const elapsedSeconds = (performance.now() - startedAt) / 1000;
  const totalRequests = successfulRequests + failedRequests;
  const sortedLatencies = [...latencies].sort((a, b) => a - b);
  const latencySum = latencies.reduce((sum, value) => sum + value, 0);
  const result = {
    target,
    requested_duration_seconds: durationSeconds,
    elapsed_seconds: Number(elapsedSeconds.toFixed(3)),
    concurrency,
    total_requests: totalRequests,
    successful_requests: successfulRequests,
    failed_requests: failedRequests,
    requests_per_second: Number(
      (totalRequests / elapsedSeconds).toFixed(3),
    ),
    status_codes: statusCodes,
    latency_ms: {
      mean:
        latencies.length > 0
          ? Number((latencySum / latencies.length).toFixed(3))
          : null,
      p50: rounded(percentile(sortedLatencies, 50)),
      p95: rounded(percentile(sortedLatencies, 95)),
      p99: rounded(percentile(sortedLatencies, 99)),
      max:
        sortedLatencies.length > 0
          ? rounded(sortedLatencies[sortedLatencies.length - 1])
          : null,
    },
  };

  const serialized = `${JSON.stringify(result, null, 2)}\n`;
  if (outputPath) {
    const resolvedOutput = path.resolve(outputPath);
    fs.mkdirSync(path.dirname(resolvedOutput), { recursive: true });
    fs.writeFileSync(resolvedOutput, serialized, "utf8");
  }
  process.stdout.write(serialized);

  if (failedRequests > 0) {
    process.exitCode = 1;
  }
}

main().catch((error) => {
  process.stderr.write(`${error.stack || error.message}\n`);
  process.exitCode = 1;
});
