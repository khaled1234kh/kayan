"""Exercise launcher functions in PowerShell with controlled process/HTTP results."""
import shutil,subprocess
from pathlib import Path
import pytest
PS=shutil.which('pwsh')
pytestmark=pytest.mark.skipif(not PS,reason='PowerShell required')
SOURCE=Path('Start-Kayan.ps1').read_text(encoding='utf-8')
FUNCTIONS=SOURCE[SOURCE.index('function Start-Component'):SOURCE.index("if($Component -in @('All','Gate'))")]

def invoke(script):
    return subprocess.run([PS,'-NoProfile','-Command',FUNCTIONS+'\n'+script],capture_output=True,text=True,timeout=15)

def test_collision_is_rejected_before_starting_or_reusing_foreign_listener():
    result=invoke("""
    function Test-NetConnection { return $true }
    function Invoke-RestMethod { return @{info=@{title='Unrelated app'}} }
    function Start-Process { throw 'MUST NOT LAUNCH' }
    try { Start-Component 'Console backend' 8001 'python' @() '.'; exit 9 }
    catch { Write-Output $_.Exception.Message; exit 0 }
    """)
    assert result.returncode==0 and 'different service' in result.stdout

def test_existing_expected_service_is_reused():
    result=invoke("""
    function Test-NetConnection { return $true }
    function Invoke-RestMethod { return @{info=@{title='KAYAN TrustGate Console'}} }
    function Start-Process { throw 'MUST NOT LAUNCH' }
    Start-Component 'Console backend' 8001 'python' @() '.'
    """)
    assert result.returncode==0 and 'reusing expected service' in result.stdout.lower()

def test_failed_new_service_does_not_print_success():
    result=invoke("""
    function Test-NetConnection { return $false }
    function Start-Process { throw 'blocked executable' }
    try { Start-Component 'Console backend' 8001 'python' @() '.'; exit 9 }
    catch { Write-Output $_.Exception.Message; exit 0 }
    """)
    assert result.returncode==0 and 'blocked executable' in result.stdout


def test_default_launch_is_safe_review_mode_not_a_gate_build():
    result=subprocess.run([PS,'-NoProfile','-Command',"$tokens=$null;$errors=$null;$ast=[System.Management.Automation.Language.Parser]::ParseFile((Join-Path (Get-Location) 'Start-Kayan.ps1'),[ref]$tokens,[ref]$errors); $ast.ParamBlock.Parameters | Where-Object {$_.Name.VariablePath.UserPath -eq 'Component'} | ForEach-Object {$_.DefaultValue.Value}"],capture_output=True,text=True,timeout=15)
    assert result.returncode==0 and result.stdout.strip()=='Review'
