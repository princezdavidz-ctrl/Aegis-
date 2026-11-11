#requires -RunAsAdministrator
$ErrorActionPreference = "Stop"
$installDir = Join-Path $env:ProgramFiles "AEGIS"
$stateDir = Join-Path $env:ProgramData "AEGIS"

New-Item -ItemType Directory -Force -Path $installDir, $stateDir | Out-Null
py -3.13 -m venv (Join-Path $installDir "venv")
$venvPython = Join-Path $installDir "venv\Scripts\python.exe"
& $venvPython -m pip install --disable-pip-version-check -r (Join-Path $PSScriptRoot "requirements.txt")
Copy-Item -Force (Join-Path $PSScriptRoot "aegis_agent.py") (Join-Path $installDir "aegis_agent.py")

# DPAPI uses machine scope; filesystem ACL is the access-control boundary.
& icacls.exe $stateDir /inheritance:r /grant:r "NT AUTHORITY\LOCAL SERVICE:(OI)(CI)F" "NT AUTHORITY\SYSTEM:(OI)(CI)F" "BUILTIN\Administrators:(OI)(CI)F" | Out-Null
$taskName = "AEGIS Endpoint Agent"
$agentPath = Join-Path $installDir "aegis_agent.py"
$taskAction = '"' + $venvPython + '" "' + $agentPath + '" --state-dir "' + $stateDir + '" run-once'
& schtasks.exe /Create /TN $taskName /SC MINUTE /MO 5 /TR $taskAction /RU "NT AUTHORITY\LOCAL SERVICE" /RL LIMITED /F | Out-Null
Write-Host "AEGIS Windows agent installed. Enroll it using the documented interactive command."
