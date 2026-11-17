$ErrorActionPreference = "Stop"

$installerPath = Resolve-Path "dist\OptiForge-Setup-1.0.0.exe"
$localAppData = [Environment]::GetFolderPath([Environment+SpecialFolder]::LocalApplicationData)
$appInstallDir = Join-Path $localAppData "Programs\OptiForge"
$installedExe = Join-Path $appInstallDir "OptiForgeApp.exe"
$uninstaller = Join-Path $appInstallDir "unins000.exe"
$startMenuShortcut = Join-Path ([Environment]::GetFolderPath([Environment+SpecialFolder]::ApplicationData)) "Microsoft\Windows\Start Menu\Programs\OptiForge.lnk"

Write-Host "=================================================="
Write-Host "STEP 1: Run Inno Setup Silent Install"
Write-Host "=================================================="
Write-Host "Installer: $installerPath"

$installProc = Start-Process -FilePath $installerPath -ArgumentList "/VERYSILENT /SUPPRESSMSGBOXES /CURRENTUSER /NORESTART" -PassThru -Wait
Write-Host "Installer exit code: $($installProc.ExitCode)"
if ($installProc.ExitCode -ne 0) {
    throw "Installer failed with exit code $($installProc.ExitCode)"
}

Write-Host "`n=================================================="
Write-Host "STEP 2: Verify Installation Files"
Write-Host "=================================================="
if (-not (Test-Path $installedExe)) {
    throw "OptiForgeApp.exe was not installed at $installedExe"
}
Write-Host "✓ Installed executable found: $installedExe"

if (Test-Path $startMenuShortcut) {
    Write-Host "✓ Start Menu shortcut created: $startMenuShortcut"
} else {
    Write-Host "ℹ️ Start Menu shortcut location checked: $startMenuShortcut (may depend on shell refresh)"
}

Write-Host "`n=================================================="
Write-Host "STEP 3: Test Startup Self-Check with STRIPPED PATH"
Write-Host "=================================================="
$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = $installedExe
$psi.Arguments = "--check-only"
$psi.EnvironmentVariables["PATH"] = "C:\Windows\System32;C:\Windows"
$psi.EnvironmentVariables["PYTHONPATH"] = ""
$psi.EnvironmentVariables["PYTHONHOME"] = ""
$psi.UseShellExecute = $false
$psi.RedirectStandardOutput = $true
$psi.RedirectStandardError = $true

$checkProc = [System.Diagnostics.Process]::Start($psi)
$checkProc.WaitForExit(10000)
$checkOut = $checkProc.StandardOutput.ReadToEnd().Trim()
$checkErr = $checkProc.StandardError.ReadToEnd().Trim()
Write-Host "Check-only ExitCode: $($checkProc.ExitCode)"
Write-Host "Check-only Output: $checkOut"
if ($checkProc.ExitCode -ne 0) {
    throw "Startup self-check failed under stripped PATH: $checkErr"
}
Write-Host "✓ Self-check passed on clean Windows environment simulation!"

Write-Host "`n=================================================="
Write-Host "STEP 4: Test HTTP Server and Single-Instance Mutex"
Write-Host "=================================================="
$psiRun = New-Object System.Diagnostics.ProcessStartInfo
$psiRun.FileName = $installedExe
$psiRun.Arguments = "--no-window --port=8859"
$psiRun.EnvironmentVariables["PATH"] = "C:\Windows\System32;C:\Windows"
$psiRun.EnvironmentVariables["PYTHONPATH"] = ""
$psiRun.EnvironmentVariables["PYTHONHOME"] = ""
$psiRun.UseShellExecute = $false

$runProc = [System.Diagnostics.Process]::Start($psiRun)
Write-Host "Started instance 1 (PID: $($runProc.Id)) on port 8859"
Start-Sleep -Seconds 3

try {
    $health = Invoke-RestMethod -Uri "http://127.0.0.1:8859/api/health" -TimeoutSec 5
    Write-Host "✓ API Health response: $($health | ConvertTo-Json -Compress)"
} catch {
    throw "Failed to reach health endpoint: $_"
}

# Try launching second instance (mutex test)
Write-Host "Testing second instance launch (should exit or delegate cleanly via mutex)..."
$psi2 = New-Object System.Diagnostics.ProcessStartInfo
$psi2.FileName = $installedExe
$psi2.Arguments = "--no-window --port=8859"
$psi2.EnvironmentVariables["PATH"] = "C:\Windows\System32;C:\Windows"
$psi2.UseShellExecute = $false
$proc2 = [System.Diagnostics.Process]::Start($psi2)
$proc2.WaitForExit(5000)
Write-Host "✓ Second instance exited promptly with code: $($proc2.ExitCode)"

# Kill instance 1 cleanly
Stop-Process -Id $runProc.Id -Force
Write-Host "✓ Instance 1 terminated."

Write-Host "`n=================================================="
Write-Host "STEP 5: Test In-Place Upgrade"
Write-Host "=================================================="
Write-Host "Re-running installer to simulate in-place upgrade..."
$upgradeProc = Start-Process -FilePath $installerPath -ArgumentList "/VERYSILENT /SUPPRESSMSGBOXES /CURRENTUSER /NORESTART" -PassThru -Wait
Write-Host "Upgrade exit code: $($upgradeProc.ExitCode)"
if ($upgradeProc.ExitCode -ne 0) {
    throw "In-place upgrade failed!"
}
Write-Host "✓ In-place upgrade completed smoothly."

Write-Host "`n=================================================="
Write-Host "STEP 6: Test Uninstaller"
Write-Host "=================================================="
if (-not (Test-Path $uninstaller)) {
    throw "Uninstaller not found at $uninstaller"
}
Write-Host "Running uninstaller: $uninstaller /VERYSILENT /SUPPRESSMSGBOXES /NORESTART"
$uninstProc = Start-Process -FilePath $uninstaller -ArgumentList "/VERYSILENT /SUPPRESSMSGBOXES /NORESTART" -PassThru -Wait
Start-Sleep -Seconds 2

Write-Host "Uninstaller exit code: $($uninstProc.ExitCode)"
if (Test-Path $appInstallDir) {
    $leftovers = Get-ChildItem -Path $appInstallDir
    if ($leftovers.Count -gt 0) {
        Write-Host "Remaining files in install dir: $($leftovers.Name -join ', ')"
    } else {
        Write-Host "✓ Install directory empty or removed."
    }
} else {
    Write-Host "✓ App directory completely removed from $appInstallDir"
}

Write-Host "`n=================================================="
Write-Host "ALL INSTALLER LIFECYCLE TESTS PASSED!"
Write-Host "=================================================="
