param([string]$BackupName = 'CatMate-v1.0-backup')
$ErrorActionPreference = 'Stop'
if ($BackupName -notmatch '^CatMate-[A-Za-z0-9.\-]+$') { throw 'Invalid backup folder name' }
$catWorkspace = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$catRelease = [IO.Path]::GetFullPath((Join-Path $catWorkspace 'dist\CatMate'))
$catStage = [IO.Path]::GetFullPath((Join-Path $catWorkspace 'release-staging\CatMate'))
$catBackup = [IO.Path]::GetFullPath((Join-Path (Join-Path $catWorkspace 'dist') $BackupName))
foreach ($catPath in @($catRelease, $catStage, $catBackup)) {
    if (-not $catPath.StartsWith($catWorkspace + '\', [StringComparison]::OrdinalIgnoreCase)) {
        throw "Update path is outside the workspace: $catPath"
    }
}
if (-not (Test-Path -LiteralPath (Join-Path $catStage 'CatMate.exe'))) { throw 'Verified staging build is missing' }
if (Test-Path -LiteralPath $catBackup) { throw 'Backup exists; choose a different backup name before updating' }
$catOldExe = Join-Path $catRelease 'CatMate.exe'
$catRunning = @(Get-Process -Name CatMate -ErrorAction SilentlyContinue | Where-Object { $_.Path -eq $catOldExe })
if ($catRunning.Count) {
    Start-Process -FilePath $catOldExe -ArgumentList '--quit' -WorkingDirectory $catRelease -WindowStyle Hidden -Wait
    foreach ($catInstance in $catRunning) {
        if (-not $catInstance.WaitForExit(8000)) { throw 'Desktop pet has not exited; update cancelled without replacing files' }
    }
}
$catSave = Join-Path $env:LOCALAPPDATA 'CatMate\save.json'
if (Test-Path -LiteralPath $catSave) {
    $catSaveBackup = Join-Path (Join-Path $catWorkspace 'build') ($BackupName + '-save.json')
    Copy-Item -LiteralPath $catSave -Destination $catSaveBackup
}
Rename-Item -LiteralPath $catRelease -NewName $BackupName
try {
    Move-Item -LiteralPath $catStage -Destination $catRelease
} catch {
    Rename-Item -LiteralPath $catBackup -NewName 'CatMate'
    throw
}
$catProcess = Start-Process -FilePath (Join-Path $catRelease 'CatMate.exe') -ArgumentList '--quiet' -WorkingDirectory $catRelease -WindowStyle Normal -PassThru
Start-Sleep -Seconds 2
if ($catProcess.HasExited) { throw 'Updated pet exited early; inspect the saved startup log' }
[PSCustomObject]@{Version='1.2.0'; ProcessId=$catProcess.Id; Release=$catRelease; PreviousVersion=$catBackup; Save=$catSave}
