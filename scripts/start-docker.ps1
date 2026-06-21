[CmdletBinding()]
param(
    [ValidateRange(1, 65535)]
    [int]$StartPort = 8000,

    [ValidateRange(1, 1000)]
    [int]$MaxAttempts = 20,

    [switch]$Detached,
    [switch]$NoBuild,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

function Test-LocalPortAvailable {
    param(
        [Parameter(Mandatory)]
        [int]$Port
    )

    $listener = [System.Net.Sockets.TcpListener]::new(
        [System.Net.IPAddress]::Loopback,
        $Port
    )
    try {
        $listener.Start()
        return $true
    }
    catch [System.Net.Sockets.SocketException] {
        return $false
    }
    finally {
        $listener.Stop()
    }
}

$lastPort = [Math]::Min(65535, $StartPort + $MaxAttempts - 1)
$selectedPort = $null

foreach ($port in $StartPort..$lastPort) {
    if (Test-LocalPortAvailable -Port $port) {
        $selectedPort = $port
        break
    }
}

if ($null -eq $selectedPort) {
    throw "No available local port was found from $StartPort to $lastPort."
}

$env:APP_PORT = [string]$selectedPort

if ($selectedPort -eq $StartPort) {
    Write-Host "Using available port $selectedPort."
}
else {
    Write-Host "Port $StartPort is unavailable. Using port $selectedPort instead."
}

Write-Host "Chatbot URL: http://localhost:$selectedPort"

if ($DryRun) {
    return
}

$composeArguments = @("compose", "up")
if (-not $NoBuild) {
    $composeArguments += "--build"
}
if ($Detached) {
    $composeArguments += "-d"
}

& docker @composeArguments
if ($LASTEXITCODE -ne 0) {
    throw "Docker Compose failed with exit code $LASTEXITCODE."
}
