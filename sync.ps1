$projectPath = "C:\Users\daksh\OneDrive\Dokumen\ai-tutor"
cd $projectPath
while ($true) {
    if (git status --porcelain) {
        git add .
        git commit -m "Auto-sync $(Get-Date -Format 'HH:mm:ss')"
        git push origin main
        Write-Host "Synced at $(Get-Date -Format 'HH:mm:ss')"
    }
    Start-Sleep -Seconds 5
}