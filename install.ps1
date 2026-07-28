#Requires -Version 5.1
$ErrorActionPreference = "Stop"

$RepoUrl = if ($env:LLM_API_PROXY_CHECK_REPO) { $env:LLM_API_PROXY_CHECK_REPO } else { "https://github.com/LegendNero/llm-api-proxy-check.git" }
$PackageSpec = if ($env:LLM_API_PROXY_CHECK_PACKAGE) { $env:LLM_API_PROXY_CHECK_PACKAGE } else { "git+$RepoUrl" }
$InstallHome = if ($env:LLM_API_PROXY_CHECK_HOME) { $env:LLM_API_PROXY_CHECK_HOME } else { Join-Path $env:LOCALAPPDATA "llm-api-proxy-check" }
$VenvDir = Join-Path $InstallHome "venv"
$BinDir = if ($env:LLM_API_PROXY_CHECK_BIN) { $env:LLM_API_PROXY_CHECK_BIN } else { Join-Path $env:LOCALAPPDATA "llm-api-proxy-check\bin" }
$Wrapper = Join-Path $BinDir "llm-api-proxy-check.cmd"

function Write-Log([string]$Message) {
    Write-Host $Message
}

function Die([string]$Message) {
    Write-Error "llm-api-proxy-check install: $Message"
    exit 1
}

function Test-PythonVersion([string]$PythonExe) {
    & $PythonExe -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)" 2>$null
    return ($LASTEXITCODE -eq 0)
}

function Find-Python {
    if ($env:PYTHON) {
        if (Get-Command $env:PYTHON -ErrorAction SilentlyContinue) {
            $resolved = (Get-Command $env:PYTHON).Source
            if (Test-PythonVersion $resolved) { return $resolved }
        }
        Die "PYTHON=$($env:PYTHON) 不可用或版本低于 3.9"
    }
    $candidates = @("python3.13", "python3.12", "python3.11", "python3.10", "python3.9", "python3", "python", "py")
    foreach ($name in $candidates) {
        $cmd = Get-Command $name -ErrorAction SilentlyContinue
        if (-not $cmd) { continue }
        $exe = $cmd.Source
        if ($name -eq "py") {
            try {
                $exe = & py -3 -c "import sys; print(sys.executable)"
                if (-not $exe) { continue }
            } catch {
                continue
            }
        }
        if (Test-PythonVersion $exe) { return $exe }
    }
    return $null
}

$PythonBin = Find-Python
if (-not $PythonBin) {
    Die "需要 Python 3.9+，请先安装后重试"
}

$VersionText = & $PythonBin -c "import sys; print('.'.join(map(str, sys.version_info[:3])))"
Write-Log "使用 Python: $PythonBin ($VersionText)"

New-Item -ItemType Directory -Force -Path $InstallHome | Out-Null
New-Item -ItemType Directory -Force -Path $BinDir | Out-Null

$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    Write-Log "创建虚拟环境: $VenvDir"
    & $PythonBin -m venv $VenvDir
    if ($LASTEXITCODE -ne 0) { Die "创建 venv 失败" }
}

Write-Log "正在安装 llm-api-proxy-check 到虚拟环境 ..."
& $VenvPython -m pip install --upgrade pip setuptools wheel | Out-Null
& $VenvPython -m pip install --upgrade $PackageSpec
if ($LASTEXITCODE -ne 0) { Die "pip 安装失败" }

$VenvCli = Join-Path $VenvDir "Scripts\llm-api-proxy-check.exe"
@"
@echo off
"$VenvCli" %*
"@ | Set-Content -Path $Wrapper -Encoding ASCII

if (-not ($env:Path -split ";" | Where-Object { $_ -eq $BinDir })) {
    $env:Path = "$BinDir;$env:Path"
    Write-Log "已临时将 $BinDir 加入 PATH"
    Write-Log "永久生效可将该目录加入用户 PATH 环境变量"
}

if (-not (Test-Path $VenvCli)) {
    Die "虚拟环境中未找到 llm-api-proxy-check 入口"
}

Write-Log "安装成功: $Wrapper"
Write-Log ""
Write-Log "小白三步走："
Write-Log "  1) 本地演示（无需 Key）: llm-api-proxy-check check --demo"
Write-Log "  2) 中文设置向导:         llm-api-proxy-check setup"
Write-Log "  3) 一键完整检测:         llm-api-proxy-check check"
Write-Log ""
Write-Log "查看配置: llm-api-proxy-check show-config"

& $VenvPython -m llm_api_proxy_check check --format json | Out-Null
Write-Log "验证完成（本地 demo 已通过模块入口）。"
