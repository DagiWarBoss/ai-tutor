$projectPath = "C:\Users\daksh\OneDrive\Dokumen\ai-tutor"
$logPath = "$projectPath\sync.log"

"Starting sync at $(Get-Date)" | Out-File $logPath -Force

while ($true) {
    try {
        cd $projectPath
        $changes = git status --porcelain
        if ($changes) {
            git add . 2>&1 | Out-File $logPath -Append
            git commit -m "Auto-sync $(Get-Date -Format 'HH:mm:ss')" 2>&1 | Out-File $logPath -Append
            git push origin main 2>&1 | Out-File $logPath -Append
            "Synced at $(Get-Date)" | Out-File $logPath -Append
        }
    }
    catch {
        "ERROR: $_" | Out-File $logPath -Append
    }
    Start-Sleep -Seconds 5
}