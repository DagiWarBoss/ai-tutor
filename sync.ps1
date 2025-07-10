# Log all output
Start-Transcript -Path "$PSScriptRoot\sync.log" -Append

try {
    cd "C:\Users\daksh\OneDrive\Dokumen\ai-tutor"
    while ($true) {
        if (git status --porcelain) {
            git add .
            git commit -m "Auto-sync $(Get-Date -Format 'HH:mm:ss')"
            git push origin main
            Write-Output "Synced at $(Get-Date -Format 'HH:mm:ss')"
        }
        Start-Sleep -Seconds 5
    }
}
catch {
    Write-Output "ERROR: $_"
    Pause
}