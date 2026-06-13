# ParkingLotDS 启动脚本
# 启动后端 :8000 + 前端 :5173

Set-Location $PSScriptRoot

Write-Host "正在启动 ParkingLotDS..." -ForegroundColor Green

# ── 0. 确保模拟数据已生成 ─────────────────────────────────
$dataDir = "data"
if (-not (Test-Path $dataDir)) {
    New-Item -ItemType Directory -Path $dataDir | Out-Null
}

$dbPath = "data\parking_lot.db"
$needGenerate = $false

if (-not (Test-Path $dbPath)) {
    $needGenerate = $true
}
else {
    $choice = Read-Host "是否更新数据库到最新状态？(Y/n)"
    if ($choice -eq 'n' -or $choice -eq 'N') {
        Write-Host "跳过数据生成（使用现有数据库）。" -ForegroundColor Gray
    }
    else {
        $needGenerate = $true
    }
}

if ($needGenerate) {
    Write-Host "正在生成模拟数据（120 天，日均约 1500 辆车）..." -ForegroundColor Yellow
    $pythonExe = ".\backend\venv\Scripts\python.exe"
    $genResult = & $pythonExe ".\backend\data_generator.py" 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "错误：数据生成失败（退出码 $LASTEXITCODE）" -ForegroundColor Red
        Write-Host $genResult -ForegroundColor Red
        Write-Host "启动中止。请检查 venv 是否存在以及依赖是否安装完整。" -ForegroundColor Red
        exit 1
    }
    Write-Host "数据生成完成。" -ForegroundColor Green
}

# ── 1. 后端 :8000 ─────────────────────────────────────────
$backendDir = Join-Path $PSScriptRoot "backend"
$pythonExe = Join-Path $backendDir "venv\Scripts\python.exe"
$backendJob = Start-Process -NoNewWindow -PassThru $pythonExe `
    -ArgumentList "-m", "uvicorn", "main:app", "--reload", "--port", "8000" `
    -WorkingDirectory $backendDir
Write-Host "后端 :8000（PID $($backendJob.Id)）" -ForegroundColor Yellow
Start-Sleep -Seconds 2

# 验证后端是否成功启动
if ($backendJob.HasExited -and $backendJob.ExitCode -ne 0) {
    Write-Host "错误：后端启动失败（退出码 $($backendJob.ExitCode)）" -ForegroundColor Red
    Write-Host "请检查 backend\venv 是否存在以及依赖是否安装完整。" -ForegroundColor Red
    exit 1
}

# ── 2. 前端 :5173 ─────────────────────────────────────────
# npm 在 Windows 上是 .cmd 脚本，需通过 cmd /c 调用
$frontendDir = Join-Path $PSScriptRoot "frontend"
$frontendJob = Start-Process -NoNewWindow -PassThru cmd `
    -ArgumentList "/c", "npm run dev" `
    -WorkingDirectory $frontendDir
Write-Host "前端 :5173（PID $($frontendJob.Id)）" -ForegroundColor Cyan

Write-Host "`n全部服务已启动。按 Ctrl+C 停止所有服务。" -ForegroundColor Green

# ── 等待 Ctrl+C，然后清理子进程 ──────────────────────────
try {
    while ($true) {
        Start-Sleep -Seconds 1
    }
}
finally {
    Write-Host "`n正在关闭..." -ForegroundColor Yellow

    foreach ($proc in @($backendJob, $frontendJob)) {
        if ($proc -and -not $proc.HasExited) {
            # 终止进程树（uvicorn workers、node 子进程一并清理）
            Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
            Write-Host "已停止 PID $($proc.Id)" -ForegroundColor Gray
        }
    }

    Write-Host "全部服务已停止。" -ForegroundColor Green
}
