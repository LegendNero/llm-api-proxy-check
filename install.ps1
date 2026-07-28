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

function Persist-UserPath([string]$Directory) {
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    if (-not $userPath) { $userPath = "" }
    $parts = $userPath -split ";" | Where-Object { $_ -and $_.Trim() -ne "" }
    if ($parts -contains $Directory) {
        Write-Log "用户 PATH 已包含: $Directory"
        return
    }
    $newPath = if ($userPath.Trim()) { "$Directory;$userPath" } else { $Directory }
    [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
    Write-Log "已将 $Directory 写入用户 PATH（新开终端后生效）"
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
    Write-Log "已将 $BinDir 加入当前会话 PATH"
}
Persist-UserPath $BinDir

if (-not (Test-Path $VenvCli)) {
    Die "虚拟环境中未找到 llm-api-proxy-check 入口"
}

Write-Log ""
Write-Log "安装成功: $Wrapper"
Write-Log ""
Write-Log "若提示找不到命令，当前窗口可立刻用："
Write-Log "  1) 完整路径:  `"$Wrapper`" setup"
Write-Log "  2) 临时生效:  `$env:Path = `"$BinDir;`$env:Path`"; llm-api-proxy-check setup"
Write-Log "  3) 新开终端后再运行: llm-api-proxy-check setup"
Write-Log ""
Write-Log "小白三步走："
Write-Log "  1) 本地演示: `"$Wrapper`" check --demo"
Write-Log "  2) 中文设置: `"$Wrapper`" setup"
Write-Log "  3) 一键检测: `"$Wrapper`" check"
Write-Log ""
Write-Log "查看配置: `"$Wrapper`" show-config"

& $VenvPython -m llm_api_proxy_check check --format json | Out-Null
Write-Log "验证完成（本地 demo 已通过模块入口）。"
