param([ValidateSet('setup','start','test','scan','billion','tune','check')][string]$Action='start')
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $root
$venv=Join-Path $root '.venv\Scripts\python.exe'
function Probe-Python([string]$Executable, [string[]]$Prefix=@()) {
    try {
        $result=& $Executable @Prefix -c 'import sys,struct; assert (3,11)<=sys.version_info[:2]<=(3,14) and struct.calcsize(chr(80))==8; print(sys.executable)' 2>$null
        if ($LASTEXITCODE -eq 0 -and $result) { return ([string]($result | Select-Object -Last 1)).Trim() }
    } catch {}
    return $null
}
function Find-Python {
    if ($env:PI_EXPLORER_PYTHON) {
        $found=Probe-Python $env:PI_EXPLORER_PYTHON
        if ($found) { return $found }
        throw 'PI_EXPLORER_PYTHON must point to a working 64-bit Python 3.11-3.14 executable.'
    }
    foreach ($name in @('py','python','python3')) {
        if (Get-Command $name -ErrorAction SilentlyContinue) {
            if ($name -eq 'py') { $found=Probe-Python $name @('-3') }
            else { $found=Probe-Python $name }
            if ($found) { return $found }
        }
    }
    foreach ($key in @('HKCU:\Software\Python\PythonCore','HKLM:\Software\Python\PythonCore')) {
        if (Test-Path $key) {
            foreach ($entry in (Get-ChildItem $key | Sort-Object PSChildName -Descending)) {
                $install=Join-Path $entry.PSPath 'InstallPath'
                if (Test-Path $install) {
                    $properties=Get-ItemProperty $install
                    $candidate=$properties.ExecutablePath
                    if (-not $candidate) { $candidate=Join-Path $properties.'(default)' 'python.exe' }
                    $found=Probe-Python $candidate
                    if ($found) { return $found }
                }
            }
        }
    }
    throw 'No supported Python found. Install 64-bit Python 3.11-3.14 (3.14 is supported), enable Python on PATH, then reopen this launcher. Or set PI_EXPLORER_PYTHON to its python.exe path.'
}
function Run-Python([string[]]$Arguments) {
    & $venv @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Python command failed (exit $LASTEXITCODE). See the error above." }
}
try {
    if (-not (Test-Path -LiteralPath (Join-Path $root 'server.py'))) { throw 'Extract the complete ZIP first. server.py must be next to the CMD launchers.' }
    $working=$null
    if (Test-Path -LiteralPath $venv) { $working=Probe-Python $venv }
    if ($Action -eq 'setup' -or -not $working) {
        $base=Find-Python
        Write-Host "Using $base"
        & $base --version
        if (-not $working) {
            $folder=Join-Path $root '.venv'
            if (Test-Path -LiteralPath $folder) {
                $backup='.venv-backup-'+[guid]::NewGuid().ToString('N')
                Rename-Item -LiteralPath $folder -NewName $backup
                Write-Host "Preserved the broken/moved environment as $backup"
            }
            & $base -m venv (Join-Path $root '.venv')
            if ($LASTEXITCODE -ne 0) { throw 'Could not create .venv. Check the Python installation and folder write permissions.' }
        }
        Run-Python @('-m','pip','install','--upgrade','pip')
        Run-Python @('-m','pip','install','--only-binary=:all:','-r',(Join-Path $root 'requirements.txt'))
    }
    Run-Python @('-c',"import numpy,gmpy2; print('Dependencies ready: NumPy',numpy.__version__,'gmpy2',gmpy2.version())")
    switch ($Action) {
        'setup' { Write-Host 'Setup complete. Open Start Pi Explorer.cmd.' }
        'check' { Run-Python @('-c',"import engine,constants,fast_search; print('Application imports OK')") }
        'start' { Run-Python @((Join-Path $root 'server.py')) }
        'test' { Run-Python @('-m','unittest','discover','-s','tests','-v') }
        'scan' { Run-Python @('benchmarks/scan_speed.py','--quick') }
        'billion' { Run-Python @('benchmarks/billion.py') }
        'tune' { Run-Python @('benchmarks/tune_native.py') }
    }
    exit 0
} catch {
    Write-Host "`nPi Explorer: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host 'No computation was started by setup. If dependencies are missing, rerun Setup Pi Explorer.cmd.'
    exit 1
}
