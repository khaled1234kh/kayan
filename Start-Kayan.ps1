param([ValidateSet('All','Review','Gate','Lab','Backend','Office')][string]$Component='Review', [switch]$RestoreDemo)
$ErrorActionPreference='Stop'
$projectRoot=$PSScriptRoot
if($RestoreDemo -and $Component -notin @('All','Review','Backend')) { throw '-RestoreDemo requires All, Review or Backend.' }
$python=if($Component -in @('All','Review','Lab','Backend')) { (Get-Command python -ErrorAction Stop).Source }
$node=if($Component -in @('All','Review','Office')) { (Get-Command node -ErrorAction Stop).Source }
function Start-Component([string]$Name,[int]$Port,[string]$Executable,[string[]]$Arguments,[string]$WorkingDirectory) {
    function Confirm-Service {
        try {
            if($Port -eq 5173) {
                $page=Invoke-WebRequest "http://127.0.0.1:$Port/" -TimeoutSec 2
                return $page.Content -match '<title>KAYAN.*Operations Floor</title>'
            }
            if($Port -eq 8000) {
                $health=Invoke-RestMethod "http://127.0.0.1:$Port/health" -TimeoutSec 2
                return ($health.status -eq 'ok' -and $health.engine -like 'cedar-policy*' -and $health.roe_authentication -eq 'HMAC-SHA256')
            }
            $schema=Invoke-RestMethod "http://127.0.0.1:$Port/openapi.json" -TimeoutSec 2
            $expected=if($Port -eq 8001) { 'KAYAN TrustGate Console' } else { 'KAYAN Lab*Vulnerable App' }
            return $schema.info.title -like $expected
        } catch { return $false }
    }
    if(Test-NetConnection -ComputerName 127.0.0.1 -Port $Port -InformationLevel Quiet -WarningAction SilentlyContinue) {
        if(-not (Confirm-Service)) { throw "$Name port $Port belongs to a different service or an unhealthy instance. Inspect its owner; no process was stopped." }
        Write-Host "$Name ready on port $Port; reusing expected service."
        return
    }
    $launch=@{FilePath=$Executable;WorkingDirectory=$WorkingDirectory;WindowStyle='Hidden';ErrorAction='Stop'}
    if($Arguments.Count -gt 0) { $launch.ArgumentList=$Arguments }
    Start-Process @launch | Out-Null
    for($attempt=0;$attempt -lt 20;$attempt++) {
        if(Confirm-Service) { Write-Host "$Name ready on port $Port."; return }
        Start-Sleep -Milliseconds 500
    }
    throw "$Name did not become healthy on port $Port. Check startup output and host execution controls; readiness is not established."
}
if($Component -in @('All','Gate')) {
    if(-not (Test-NetConnection 127.0.0.1 -Port 8000 -InformationLevel Quiet -WarningAction SilentlyContinue)) {
        Push-Location $projectRoot
        try { cargo build --manifest-path trustgate/service/Cargo.toml --target-dir .build/rust; if($LASTEXITCODE -ne 0) { throw 'Gate build failed' } }
        finally { Pop-Location }
    }
    Start-Component 'TrustGate' 8000 (Join-Path $projectRoot '.build/rust/debug/trustgate-service.exe') @() $projectRoot
}
if($Component -in @('All','Lab')) { Start-Component 'Owned lab' 8888 $python @('-m','uvicorn','lab.vulnerable_app:app','--host','127.0.0.1','--port','8888') $projectRoot }
if($Component -in @('All','Review','Backend')) { Start-Component 'Console backend' 8001 $python @('-m','uvicorn','console.backend.main:app','--host','127.0.0.1','--port','8001') $projectRoot }
if($Component -in @('All','Review','Office')) {
    $office=Join-Path $projectRoot 'console/office'
    if(-not (Test-Path -LiteralPath (Join-Path $office 'node_modules/vite/bin/vite.js'))) { throw 'Run npm ci inside console/office first.' }
    Start-Component '3D office' 5173 $node @('node_modules/vite/bin/vite.js','--host','127.0.0.1','--port','5173','--strictPort') $office
}
if($RestoreDemo) {
    $sessionPath=Join-Path $projectRoot 'eval/reports/checkpoints/ta_meeting_20261101_preflight/before-state.json'
    $saved=Get-Content -Raw -LiteralPath $sessionPath | ConvertFrom-Json
    if($saved.engagement_id -ne '7da73508-01e6-48e9-9093-be09c5fd734d' -or $saved.status -ne 'completed') { throw 'Unexpected saved demo' }
    $current=$null
    for($attempt=0;$attempt -lt 15;$attempt++) {
        try { $current=Invoke-RestMethod 'http://127.0.0.1:8001/engagement'; break } catch { Start-Sleep -Seconds 1 }
    }
    if(-not $current) { throw 'Console backend is unavailable' }
    if($current.status -eq 'waiting') {
        Invoke-RestMethod 'http://127.0.0.1:8001/engagement/update' -Method Post -ContentType 'application/json' -Body (Get-Content -Raw -LiteralPath $sessionPath) | Out-Null
        Write-Host 'Restored the original completed demo; no assessment started.'
    } elseif($current.engagement_id -eq $saved.engagement_id -and $current.status -eq 'completed') {
        Write-Host 'Original completed demo is already loaded.'
    } else { throw 'Refusing to replace an active or different session.' }
}
Write-Host 'Open http://127.0.0.1:5173/. Start Ollama separately for real-model assessments.'
if($Component -eq 'Review') { Write-Host 'Recorded-evidence presentation: http://127.0.0.1:5173/review.html' }
