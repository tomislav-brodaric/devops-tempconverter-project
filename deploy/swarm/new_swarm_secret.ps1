[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet(
        'tempconverter_db_password',
        'tempconverter_db_root_password',
        'tempconverter_flask_secret_key'
    )]
    [string]$Name,

    [string]$DockerPath = 'docker'
)

$ErrorActionPreference = 'Stop'
$swarmState = (& $DockerPath info `
    --format '{{.Swarm.LocalNodeState}}|{{.Swarm.ControlAvailable}}' |
    Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or $swarmState -ne 'active|true') {
    throw 'The selected Docker CLI is not connected to an active Swarm manager. No secret was created.'
}

$secureValue = Read-Host "Enter the value for $Name" -AsSecureString
$nativeValue = [IntPtr]::Zero

try {
    $nativeValue = [Runtime.InteropServices.Marshal]::
        SecureStringToBSTR($secureValue)
    $plainValue = [Runtime.InteropServices.Marshal]::
        PtrToStringBSTR($nativeValue)

    if ([string]::IsNullOrWhiteSpace($plainValue)) {
        throw 'A Swarm secret must not be empty'
    }

    $plainValue | & $DockerPath secret create $Name -
    if ($LASTEXITCODE -ne 0) {
        throw "docker secret create failed with exit code $LASTEXITCODE"
    }

    Write-Output "secret=$Name|status=created"
}
finally {
    if ($nativeValue -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($nativeValue)
    }
    $plainValue = $null
    $secureValue.Dispose()
}
