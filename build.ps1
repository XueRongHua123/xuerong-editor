param(
    [string]$Python = "python",
    [string]$Name = "雪绒的钢铁雄心编辑器"
)

$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

& $Python -m pip install -r requirements.txt pyinstaller

$root = (Get-Location).Path
$args = @(
    "--noconfirm", "--onefile", "--name", $Name,
    "--icon", "$root\mascot\xuerong_face.ico",
    "--add-data", "$root\focus_editor_index.html;.",
    "--add-data", "$root\web;web",
    "--add-data", "$root\xuerong;xuerong",
    "--add-data", "$root\qa;qa",
    "--add-data", "$root\mascot_face.png;.",
    "--add-data", "$root\mascot_card.png;.",
    "--add-data", "$root\_version.txt;.",
    "--add-data", "$root\mascot;mascot",
    "--exclude-module", "PIL._avif",
    "--exclude-module", "PIL._avif_cffi",
    "--exclude-module", "scipy",
    "--exclude-module", "pandas",
    "--exclude-module", "matplotlib",
    "$root\focus_editor.py"
)
& $Python -m PyInstaller @args

Write-Host "构建完成：dist\$Name.exe"
