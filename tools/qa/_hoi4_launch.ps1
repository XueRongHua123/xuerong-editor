<#
启动 HOI4 并定时截图，用来做「能不能进游戏」的真机验证。

用法：
  powershell -File qa/_hoi4_launch.ps1 -Tag baseline -WaitSec 75

行为：
  1. 若已有 hoi4.exe 在跑，直接报错退出（避免连开两个）
  2. 用游戏目录下的 hoi4.exe 直启（绕过 Paradox Launcher）
  3. 每 20 秒截一张图到 work/tmp/shots/<Tag>_<秒>.png
  4. 进程消失就立刻停下并打印 崩溃目录 / game.log 尾部

不做点击：点「开始」交给调用方（agent 看图后用 click.ps1 点）。
#>
param([string]$Tag = "run", [int]$WaitSec = 90, [int]$Every = 20,
      [string]$GameDir = "E:\SteamLibrary\steamapps\common\Hearts of Iron IV",
      [string]$OutDir = "D:\大肥鱼工作区\HOI4 MUVLUVsub mod 制作\work\tmp\shots")

Add-Type -AssemblyName System.Windows.Forms, System.Drawing

$exe = Join-Path $GameDir "hoi4.exe"
if (-not (Test-Path $exe)) { "ERR: 找不到 $exe"; exit 2 }
if (Get-Process hoi4 -ErrorAction SilentlyContinue) { "ERR: hoi4 已在运行"; exit 3 }

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

$docs = "C:\Users\33206\Documents\Paradox Interactive\Hearts of Iron IV"
$logs = Join-Path $docs "logs"
# 崩溃目录基线
$before = @(Get-ChildItem (Join-Path $docs "crashes") -Directory -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Name)

Start-Process -FilePath $exe -WorkingDirectory $GameDir
"launched $Tag"

function Shot([string]$path) {
  $b = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
  $bmp = New-Object System.Drawing.Bitmap $b.Width, $b.Height
  $g = [System.Drawing.Graphics]::FromImage($bmp)
  $g.CopyFromScreen($b.Location, [System.Drawing.Point]::Empty, $b.Size)
  $bmp.Save($path)
  $g.Dispose(); $bmp.Dispose()
}

$t = 0
$alive = $true
while ($t -lt $WaitSec) {
  Start-Sleep -Seconds $Every
  $t += $Every
  $p = Get-Process hoi4 -ErrorAction SilentlyContinue
  if (-not $p) {
    "PROCESS_GONE at ${t}s"
    $alive = $false
    break
  }
  $mem = [math]::Round($p.WorkingSet64 / 1MB)
  $shot = Join-Path $OutDir ("{0}_{1:D3}.png" -f $Tag, $t)
  Shot $shot
  "t=${t}s mem=${mem}MB shot=$shot"
}

if ($alive) { "STILL_RUNNING at ${t}s" } else { "DIED at ${t}s" }

"--- game.log ---"
if (Test-Path (Join-Path $logs "game.log")) { Get-Content (Join-Path $logs "game.log") -Tail 8 }
"--- 新崩溃目录 ---"
$after = @(Get-ChildItem (Join-Path $docs "crashes") -Directory -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Name)
$new = $after | Where-Object { $before -notcontains $_ }
if ($new) { $new | ForEach-Object { "CRASH_DIR: $_" } } else { "no new crash dir" }
