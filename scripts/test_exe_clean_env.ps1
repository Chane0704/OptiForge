$ErrorActionPreference = "Stop"

$exePath = Resolve-Path "dist\OptiForgeApp\OptiForgeApp.exe"
Write-Host "Testing EXE at: $exePath"

$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = $exePath
$psi.EnvironmentVariables["PATH"] = "C:\Windows\System32;C:\Windows"
$psi.EnvironmentVariables["PYTHONPATH"] = ""
$psi.EnvironmentVariables["PYTHONHOME"] = ""
$psi.UseShellExecute = $false
$psi.RedirectStandardOutput = $true
$psi.RedirectStandardError = $true

$proc = [System.Diagnostics.Process]::Start($psi)
Write-Host "Started process with PID: $($proc.Id)"

# Wait 4 seconds for initialization
Start-Sleep -Seconds 4

$hasExited = $proc.HasExited
Write-Host "Has process exited? $hasExited"

if ($hasExited) {
    Write-Host "Process Exit Code: $($proc.ExitCode)"
    $stdout = $proc.StandardOutput.ReadToEnd()
    $stderr = $proc.StandardError.ReadToEnd()
    Write-Host "Stdout: $stdout"
    Write-Host "Stderr: $stderr"
} else {
    Write-Host "SUCCESS: Process is running smoothly without crashing!"
    
    # Test HTTP endpoint
    try {
        $res = Invoke-RestMethod -Uri "http://127.0.0.1:8849/api/health" -TimeoutSec 3 -ErrorAction Stop
        Write-Host "HTTP /api/health responded: $($res | ConvertTo-Json -Compress)"
    } catch {
        Write-Host "HTTP health check attempt: $_"
    }

    # Terminate process cleanly
    Stop-Process -Id $proc.Id -Force
    Write-Host "Stopped test process."
}

# Print log file output
$localAppData = [Environment]::GetFolderPath([Environment+SpecialFolder]::LocalApplicationData)
$logFile = Join-Path $localAppData "OptiForge\logs\optiforge.log"
if (Test-Path $logFile) {
    Write-Host "`n--- Log contents from %LOCALAPPDATA%\OptiForge\logs\optiforge.log ---"
    Get-Content $logFile -Tail 20
}
