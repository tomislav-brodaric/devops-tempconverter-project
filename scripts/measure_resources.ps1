param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('idle', 'load')]
    [string]$Scenario,

    [ValidateRange(1, 120)]
    [int]$Samples = 10,

    [ValidateRange(0, 60)]
    [int]$IntervalSeconds = 1,

    [Parameter(Mandatory = $true)]
    [string]$OutputPath,

    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$AppContainerName,

    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$DbContainerName,

    [string]$PodmanPath
)

$ErrorActionPreference = 'Stop'
$culture = [System.Globalization.CultureInfo]::InvariantCulture
if ($AppContainerName -eq $DbContainerName) {
    throw 'AppContainerName and DbContainerName must be different'
}
$containerNames = @($AppContainerName, $DbContainerName)

if (-not $PodmanPath) {
    $podmanCommand = Get-Command podman -CommandType Application `
        -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($podmanCommand) {
        $PodmanPath = $podmanCommand.Source
    }
    elseif ($env:LOCALAPPDATA) {
        $localPodmanPath = Join-Path $env:LOCALAPPDATA `
            'Programs\Podman\podman.exe'
        if (Test-Path -LiteralPath $localPodmanPath -PathType Leaf) {
            $PodmanPath = $localPodmanPath
        }
    }
}

if (-not $PodmanPath) {
    throw ('Podman was not found on PATH or in the standard per-user ' +
        'location. Pass -PodmanPath explicitly.')
}

if (-not (Test-Path -LiteralPath $PodmanPath -PathType Leaf)) {
    throw "Podman executable was not found: $PodmanPath"
}

function Convert-SizeToMiB {
    param([Parameter(Mandatory = $true)][string]$Value)

    if ($Value -notmatch '^([0-9.]+)\s*([KMGT]?i?B)$') {
        throw "Unsupported size value: $Value"
    }

    $number = [double]::Parse($Matches[1], $culture)
    $unit = $Matches[2]
    $bytes = switch ($unit) {
        'B' { $number }
        'kB' { $number * 1000 }
        'KB' { $number * 1000 }
        'KiB' { $number * 1KB }
        'MB' { $number * 1000 * 1000 }
        'MiB' { $number * 1MB }
        'GB' { $number * 1000 * 1000 * 1000 }
        'GiB' { $number * 1GB }
        'TB' { $number * 1000 * 1000 * 1000 * 1000 }
        'TiB' { $number * 1TB }
        default { throw "Unsupported size unit: $unit" }
    }

    return [math]::Round($bytes / 1MB, 3)
}

function Get-ContainerSnapshot {
    $format = '{{.Name}}|{{.CPUNano}}|{{.SystemNano}}|' +
        '{{.MemUsageBytes}}|{{.PIDs}}'
    $statsOutput = & $PodmanPath stats --no-stream --format $format `
        @containerNames
    if ($LASTEXITCODE -ne 0) {
        throw "podman stats failed with exit code $LASTEXITCODE"
    }

    $snapshot = @{}
    foreach ($line in $statsOutput) {
        $parts = $line -split '\|'
        if ($parts.Count -ne 5) {
            throw "Unexpected podman stats row: $line"
        }

        $snapshot[$parts[0]] = [pscustomobject]@{
            cpu_nano = [int64]$parts[1]
            system_nano = [int64]$parts[2]
            memory_mib = Convert-SizeToMiB (
                ($parts[3] -split '/')[0].Trim()
            )
            pids = [int]$parts[4]
        }
    }

    foreach ($containerName in $containerNames) {
        if (-not $snapshot.ContainsKey($containerName)) {
            throw "Statistics were not returned for $containerName"
        }
    }

    return $snapshot
}

$previous = Get-ContainerSnapshot
$rows = @(for ($sample = 1; $sample -le $Samples; $sample++) {
    if ($IntervalSeconds -gt 0) {
        Start-Sleep -Seconds $IntervalSeconds
    }

    $current = Get-ContainerSnapshot
    $app = $current[$AppContainerName]
    $db = $current[$DbContainerName]
    $previousApp = $previous[$AppContainerName]
    $previousDb = $previous[$DbContainerName]

    $vm = Get-CimInstance Win32_PerfFormattedData_PerfProc_Process `
        -Filter "Name='vmmemWSL'"
    if (-not $vm) {
        throw 'vmmemWSL performance data was not found'
    }

    $appSystemDelta = $app.system_nano - $previousApp.system_nano
    $dbSystemDelta = $db.system_nano - $previousDb.system_nano
    if ($appSystemDelta -le 0 -or $dbSystemDelta -le 0) {
        throw 'Podman system timestamp did not advance between samples'
    }

    $appCpu = [math]::Round(
        (($app.cpu_nano - $previousApp.cpu_nano) / $appSystemDelta) * 100,
        3
    )
    $dbCpu = [math]::Round(
        (($db.cpu_nano - $previousDb.cpu_nano) / $dbSystemDelta) * 100,
        3
    )

    [pscustomobject]@{
        scenario = $Scenario
        sample = $sample
        timestamp_utc = [DateTime]::UtcNow.ToString('o', $culture)
        app_cpu_percent = $appCpu
        app_memory_mib = $app.memory_mib
        app_pids = $app.pids
        db_cpu_percent = $dbCpu
        db_memory_mib = $db.memory_mib
        db_pids = $db.pids
        containers_cpu_percent_total = [math]::Round($appCpu + $dbCpu, 3)
        containers_memory_mib_total = [math]::Round(
            $app.memory_mib + $db.memory_mib,
            3
        )
        containers_pids_total = $app.pids + $db.pids
        vm_cpu_percent = [double]$vm.PercentProcessorTime
        vm_working_set_mib = [math]::Round(
            [double]$vm.WorkingSet / 1MB,
            3
        )
        vm_private_mib = [math]::Round(
            [double]$vm.PrivateBytes / 1MB,
            3
        )
    }

    $previous = $current
})

$resolvedOutput = $ExecutionContext.SessionState.Path.
    GetUnresolvedProviderPathFromPSPath($OutputPath)
$outputDirectory = Split-Path -Parent $resolvedOutput
if ($outputDirectory) {
    New-Item -ItemType Directory -Force -Path $outputDirectory | Out-Null
}

$originalCulture = [System.Threading.Thread]::CurrentThread.CurrentCulture
try {
    [System.Threading.Thread]::CurrentThread.CurrentCulture = $culture
    $rows | Export-Csv -NoTypeInformation -Encoding UTF8 -Path $resolvedOutput
}
finally {
    [System.Threading.Thread]::CurrentThread.CurrentCulture = $originalCulture
}
Write-Output "scenario=$Scenario|samples=$($rows.Count)|output=$resolvedOutput"
