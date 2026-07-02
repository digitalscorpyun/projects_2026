# Get-DefenderThreatReceipt.ps1
# Beginner-safe script.
# Purpose: Read recent Microsoft Defender detections and write a receipt to Desktop.
# This script does NOT remove, quarantine, allow, or exclude anything.

$DaysBack = 14
$Now = Get-Date
$Since = $Now.AddDays(-$DaysBack)
$Stamp = $Now.ToString("yyyyMMdd-HHmmss")
$ReportPath = Join-Path $env:USERPROFILE "Desktop\defender-threat-receipt-$Stamp.md"

Write-Host "Checking Microsoft Defender detections from the last $DaysBack days..." -ForegroundColor Cyan

try {
    $Detections = Get-MpThreatDetection |
        Where-Object {
            $_.InitialDetectionTime -ge $Since -or
            $_.LastThreatStatusChangeTime -ge $Since
        } |
        Sort-Object InitialDetectionTime -Descending
}
catch {
    Write-Host "Could not read Defender detections." -ForegroundColor Red
    Write-Host "Try running PowerShell as Administrator." -ForegroundColor Yellow
    Write-Host $_.Exception.Message
    exit
}

$Lines = @()
$Lines += "# Microsoft Defender Threat Receipt"
$Lines += ""
$Lines += "**Generated:** $Now"
$Lines += "**Computer:** $env:COMPUTERNAME"
$Lines += "**User:** $env:USERNAME"
$Lines += "**Lookback window:** Last $DaysBack days"
$Lines += ""

if (-not $Detections) {
    $Lines += "## Result"
    $Lines += ""
    $Lines += "No Defender threat detections found in the selected time window."
}
else {
    $Lines += "## Recent Defender Detections"
    $Lines += ""
    $Lines += "| Initial Detection | Threat Name | Action Success | Resources |"
    $Lines += "|---|---|---|---|"

    foreach ($Detection in $Detections) {
        $Initial = $Detection.InitialDetectionTime
        $ThreatName = $Detection.ThreatName
        $ActionSuccess = $Detection.ActionSuccess
        $Resources = ($Detection.Resources -join "<br>")

        $Lines += "| $Initial | $ThreatName | $ActionSuccess | $Resources |"
    }

    $Lines += ""
    $Lines += "## Raw Details"
    $Lines += ""
    $Lines += '```text'
    $Lines += ($Detections | Format-List * | Out-String)
    $Lines += '```'
}

$Lines | Set-Content -Path $ReportPath -Encoding UTF8

Write-Host "Receipt written to:" -ForegroundColor Green
Write-Host $ReportPath -ForegroundColor Green
