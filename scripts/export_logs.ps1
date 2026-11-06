# -*- coding: utf-8 -*-
<#
  课程学习助手 —— 日志一键导出
  用途：在只放了 start.exe 的电脑上，把运行日志 / 报错 / 诊断截图打成一个 zip，
        方便发给开发者分析。

  用法：
    1) 双击同目录的 export_logs.bat（推荐）
    2) 或在 PowerShell 里执行：
       powershell -NoProfile -ExecutionPolicy Bypass -File .\export_logs.ps1

  可选参数：
    -OutDir <目录>        zip 输出目录（默认：桌面）
    -WithQuestionShots    连「图片题」截图一起打包（体积大，默认不含）
    -NoPause              结束时不等待

  设计说明：
    · zip 内的文件名一律用 ASCII（main.log / account.log / shots/...），
      避免中文名在不同解压工具里乱码；中文原名与包内名的对应关系写在 00_README.txt 里。
    · accounts.json / account_info.json 里的手机号、密码、API Key 会先打码再打包。
#>
param(
    [string]$OutDir = '',
    [switch]$WithQuestionShots,
    [switch]$NoPause
)

$ErrorActionPreference = 'Continue'
try { [Console]::OutputEncoding = [Text.Encoding]::UTF8 } catch { }

function Say($m, $c = 'Gray') { Write-Host $m -ForegroundColor $c }
function Ok($m)  { Write-Host "  [OK] $m" -ForegroundColor Green }
function Warn($m){ Write-Host "  [!!] $m" -ForegroundColor Yellow }
function Fail($m){ Write-Host "  [XX] $m" -ForegroundColor Red }

Say ''
Say '==============================================' Cyan
Say '   课程学习助手 - 日志导出' Cyan
Say '==============================================' Cyan
Say ''

# ---------------------------------------------------------------- 1. 找数据目录
$candidates = New-Object System.Collections.Generic.List[string]
if ($env:XXT_DATA) { $candidates.Add($env:XXT_DATA) }
if ($env:LOCALAPPDATA) { $candidates.Add((Join-Path $env:LOCALAPPDATA 'XuexitongShuake')) }
if ($env:APPDATA)      { $candidates.Add((Join-Path $env:APPDATA 'XuexitongShuake')) }
if ($env:USERPROFILE)  { $candidates.Add((Join-Path $env:USERPROFILE 'XuexitongShuake')) }

$dataDir = $null
foreach ($c in $candidates) {
    if ($c -and (Test-Path (Join-Path $c 'logs'))) { $dataDir = $c; break }
}
if (-not $dataDir) {
    foreach ($c in $candidates) { if ($c -and (Test-Path $c)) { $dataDir = $c; break } }
}
if (-not $dataDir) {
    Fail '没找到程序的数据目录，无法导出。'
    Say ''
    Say '已尝试这些位置：' Yellow
    $candidates | ForEach-Object { if ($_) { Say "    $_" } }
    Say ''
    Say '请确认：'
    Say '  1) 这台电脑上运行过程序（至少启动过一次）；'
    Say '  2) 用的是打包版 start.exe（数据在 %LOCALAPPDATA%\XuexitongShuake）；'
    Say '  3) 如果设置过 XXT_DATA 环境变量，请把它的值告诉开发者。'
    if (-not $NoPause) { Read-Host '按回车退出' | Out-Null }
    exit 1
}
Ok "数据目录：$dataDir"
Say ''

# ---------------------------------------------------------------- 2. 暂存目录（ASCII 文件名）
$stamp  = Get-Date -Format 'yyyyMMdd_HHmmss'
$stage  = Join-Path $env:TEMP ("xtlog_" + $stamp)
if (Test-Path $stage) { Remove-Item $stage -Recurse -Force -ErrorAction SilentlyContinue }
foreach ($sub in @('logs', 'logs\accounts', 'shots', 'records', 'config_sanitized')) {
    New-Item -ItemType Directory -Force -Path (Join-Path $stage $sub) | Out-Null
}

$plan = New-Object System.Collections.Generic.List[object]   # Source / Packed / Note

function Stage-File($src, $packedRel, $note) {
    if (-not (Test-Path -LiteralPath $src)) { return }
    try {
        $dest = Join-Path $stage ($packedRel -replace '/', '\')
        New-Item -ItemType Directory -Force -Path (Split-Path $dest -Parent) | Out-Null
        Copy-Item -LiteralPath $src -Destination $dest -Force -ErrorAction Stop
        $script:plan.Add([pscustomobject]@{ Source = $dest; Packed = $packedRel; Note = $note })
    } catch {
        Warn ("跳过（可能正被占用）：" + $note)
    }
}

# 截图标签 -> ASCII
$tagMap = @{
    '未识别页面'     = 'unknown_page'
    '页面卡住'       = 'stuck_page'
    '视频出错'       = 'video_error'
    '测验出错'       = 'quiz_error'
    '找不到元素'     = 'no_element'
    '浏览器会话异常' = 'browser_session_error'
    '程序异常'       = 'program_error'
}

# ---------------------------------------------------------------- 3. 主日志 / 报错 / 自检 / 签到
Stage-File (Join-Path $dataDir 'logs\程序日志.log')     'logs/main.log'      'logs\程序日志.log'
Stage-File (Join-Path $dataDir 'logs\程序日志.log.1')   'logs/main.log.1'    'logs\程序日志.log.1（轮转备份）'
Stage-File (Join-Path $dataDir 'error.log')             'logs/error.log'     'error.log（异常堆栈）'
Stage-File (Join-Path $dataDir '输出记录.log')           'logs/gui.log'       '输出记录.log（logging 记录）'
Stage-File (Join-Path $dataDir 'selftest.log')          'logs/selftest.log'  'selftest.log（自检结果）'
Stage-File (Join-Path $dataDir 'data\sign.log')         'logs/sign.log'      'data\sign.log（签到）'

# ---------------------------------------------------------------- 4. 各账号：明细日志 / 截图 / 学习记录
$runRoot = Join-Path $dataDir 'run'
if (Test-Path -LiteralPath $runRoot) {
    foreach ($acc in Get-ChildItem -LiteralPath $runRoot -Directory -ErrorAction SilentlyContinue) {
        $id  = $acc.Name
        $safeId = ($id -replace '[^0-9A-Za-z_\-]', '_')

        Stage-File (Join-Path $acc.FullName '运行日志.log')     ("logs/accounts/$safeId/account.log")     ("run\$id\运行日志.log")
        Stage-File (Join-Path $acc.FullName '运行日志.log.old') ("logs/accounts/$safeId/account.log.old") ("run\$id\运行日志.log.old（轮转备份）")

        # 诊断截图
        $shotDir = Join-Path $acc.FullName 'record\诊断截图'
        if (Test-Path -LiteralPath $shotDir) {
            $n = 0
            foreach ($png in Get-ChildItem -LiteralPath $shotDir -Filter *.png -File -ErrorAction SilentlyContinue) {
                $n++
                $base = [IO.Path]::GetFileNameWithoutExtension($png.Name)
                $m = [regex]::Match($base, '^(?<tag>.+?)_(?<d>\d{8})_(?<t>\d{6})$')
                if ($m.Success) {
                    $tag = $m.Groups['tag'].Value
                    $ascii = $tagMap[$tag]
                    if (-not $ascii) { $ascii = 'shot' }
                    $name = ('{0}_{1}_{2}.png' -f $ascii, $m.Groups['d'].Value, $m.Groups['t'].Value)
                } else {
                    $name = ('shot_{0:000}.png' -f $n)
                }
                Stage-File $png.FullName ("shots/$safeId/$name") ("run\$id\record\诊断截图\" + $png.Name)
            }
        }

        # 图片题截图（可选）
        if ($WithQuestionShots) {
            $qDir = Join-Path $acc.FullName 'record\图片题'
            if (Test-Path -LiteralPath $qDir) {
                foreach ($png in Get-ChildItem -LiteralPath $qDir -Filter *.png -File -ErrorAction SilentlyContinue) {
                    Stage-File $png.FullName ("shots/$safeId/questions/" + $png.Name) ("run\$id\record\图片题\" + $png.Name)
                }
            }
        }

        # 学习/成绩记录
        $recDir = Join-Path $acc.FullName 'record'
        if (Test-Path -LiteralPath $recDir) {
            $iStudy = 0; $iScore = 0
            foreach ($txt in (Get-ChildItem -LiteralPath $recDir -Filter *.txt -File -ErrorAction SilentlyContinue | Sort-Object Name)) {
                if ($txt.Name -like '*成绩*') { $iScore++; $name = ('score_{0:00}.txt' -f $iScore) }
                else                          { $iStudy++; $name = ('study_{0:00}.txt' -f $iStudy) }
                Stage-File $txt.FullName ("records/$safeId/$name") ("run\$id\record\" + $txt.Name)
            }
        }
    }
}

# ---------------------------------------------------------------- 5. 配置脱敏
function Save-Sanitized($srcPath, $packedRel, $note) {
    if (-not (Test-Path -LiteralPath $srcPath)) { return }
    try {
        $text = Get-Content -LiteralPath $srcPath -Raw -Encoding UTF8
        # 敏感字段整体打码
        $text = [regex]::Replace($text,
            '"(?<k>password|pwd|API|api_key|apikey|cookies|token|secret)"\s*:\s*"(?:[^"\\]|\\.)*"',
            '"${k}": "***"')
        # 手机号只留后 4 位
        $text = [regex]::Replace($text, '"(?<k>phone_number|phone)"\s*:\s*"(?<v>[^"]*)"', {
            param($m)
            $v = $m.Groups['v'].Value
            $k = $m.Groups['k'].Value
            if ($v.Length -le 4) { return '"' + $k + '": "***"' }
            return '"' + $k + '": "' + ('*' * ($v.Length - 4)) + $v.Substring($v.Length - 4) + '"'
        })
        $dest = Join-Path $stage ($packedRel -replace '/', '\')
        New-Item -ItemType Directory -Force -Path (Split-Path $dest -Parent) | Out-Null
        $text | Out-File -LiteralPath $dest -Encoding UTF8 -Force
        $script:plan.Add([pscustomobject]@{ Source = $dest; Packed = $packedRel; Note = ($note + '（已脱敏）') })
    } catch {
        Warn ("配置脱敏失败：" + $note)
    }
}
Save-Sanitized (Join-Path $dataDir 'tool\accounts.json') 'config_sanitized/accounts.json' 'tool\accounts.json'
if (Test-Path -LiteralPath $runRoot) {
    foreach ($acc in Get-ChildItem -LiteralPath $runRoot -Directory -ErrorAction SilentlyContinue) {
        $safeId = ($acc.Name -replace '[^0-9A-Za-z_\-]', '_')
        Save-Sanitized (Join-Path $acc.FullName 'tool\account_info.json') ("config_sanitized/account_info_$safeId.json") ("run\" + $acc.Name + "\tool\account_info.json")
    }
}

# ---------------------------------------------------------------- 6. 系统信息
function Get-BrowserVersion($browser) {
    if ($browser -eq 'edge') {
        $keys = @('HKCU:\Software\Microsoft\Edge\BLBeacon',
                  'HKLM:\SOFTWARE\WOW6432Node\Microsoft\Edge\BLBeacon',
                  'HKLM:\SOFTWARE\Microsoft\Edge\BLBeacon')
    } else {
        $keys = @('HKCU:\Software\Google\Chrome\BLBeacon',
                  'HKLM:\SOFTWARE\WOW6432Node\Google\Chrome\BLBeacon',
                  'HKLM:\SOFTWARE\Google\Chrome\BLBeacon')
    }
    foreach ($k in $keys) {
        try { $v = (Get-ItemProperty -Path $k -ErrorAction Stop).version; if ($v) { return $v } } catch { }
    }
    return '未检测到'
}

$appVersion = '未知'
$mainLog = Join-Path $dataDir 'logs\程序日志.log'
if (Test-Path -LiteralPath $mainLog) {
    $hit = Select-String -LiteralPath $mainLog -Pattern '启动 .*?版本\s+(\S+)' -Encoding UTF8 -ErrorAction SilentlyContinue |
           Select-Object -Last 1
    if ($hit) { $appVersion = $hit.Matches[0].Groups[1].Value }
}
if ($appVersion -eq '未知') {
    $st = Join-Path $dataDir 'selftest.log'
    if (Test-Path -LiteralPath $st) {
        $hit = Select-String -LiteralPath $st -Pattern '版本\s+(\S+)' -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($hit) { $appVersion = $hit.Matches[0].Groups[1].Value }
    }
}

$allFiles = @(Get-ChildItem -LiteralPath $dataDir -Recurse -File -ErrorAction SilentlyContinue | Where-Object { $_.Length -gt 0 })
$totalMB = 0
if ($allFiles.Count -gt 0) { $totalMB = [math]::Round((($allFiles | Measure-Object Length -Sum).Sum) / 1MB, 1) }

# README（含对照表）
$readme = New-Object System.Collections.Generic.List[string]
$readme.Add('课程学习助手 - 日志包说明')
$readme.Add('')
$readme.Add('导出时间：' + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'))
$readme.Add('计算机名：' + $env:COMPUTERNAME + '    用户：' + $env:USERNAME)
$readme.Add('系统：' + [System.Environment]::OSVersion.VersionString)
$readme.Add('数据目录：' + $dataDir)
$readme.Add('程序版本（取自日志）：' + $appVersion)
$readme.Add('Edge 版本：' + (Get-BrowserVersion 'edge') + '    Chrome 版本：' + (Get-BrowserVersion 'chrome'))
$readme.Add('数据目录总大小：' + $totalMB + ' MB，文件数：' + $allFiles.Count)
$readme.Add('打包范围：' + ($(if ($WithQuestionShots) { '日志 + 诊断截图 + 图片题截图 + 学习记录' } else { '日志 + 诊断截图 + 学习记录（不含图片题截图）' })))
$readme.Add('')
$readme.Add('【包里有什么】')
$readme.Add('  logs/main.log                      主日志：启动信息、界面操作、每个账号子进程的启动/退出和全部输出')
$readme.Add('  logs/main.log.1                    主日志轮转备份（8MB 轮转）')
$readme.Add('  logs/accounts/<账号>/account.log   单账号明细（3MB 轮转，超了叫 account.log.old）')
$readme.Add('  logs/error.log                     异常堆栈')
$readme.Add('  logs/gui.log                       界面 logging 记录（启动/开始学习/账号结束）')
$readme.Add('  logs/selftest.log                  自检结果（跑过 --selftest 才有）')
$readme.Add('  logs/sign.log                      自动签到日志')
$readme.Add('  shots/<账号>/*.png                 出错时的诊断截图（unknown_page/stuck_page/video_error/quiz_error/...）')
$readme.Add('  records/<账号>/*.txt               学习记录、成绩记录')
$readme.Add('  config_sanitized/*.json            配置（手机号只留后 4 位，密码/API Key 已抹掉）')
$readme.Add('')
$readme.Add('【原文件名 -> 包内文件名 对照表】')
$readme.Add(('{0,-56} {1}' -f '包内文件', '原始位置'))
foreach ($p in ($plan | Sort-Object Packed)) {
    $readme.Add(('{0,-56} {1}' -f $p.Packed, $p.Note))
}
$readme.Add('')
$readme.Add('【数据目录完整清单（字节 / 修改时间 / 相对路径）】')
foreach ($f in ($allFiles | Sort-Object FullName)) {
    $rel = $f.FullName.Substring($dataDir.Length).TrimStart('\')
    $readme.Add(('{0,10}  {1}  {2}' -f $f.Length, $f.LastWriteTime.ToString('yyyy-MM-dd HH:mm:ss'), $rel))
}
$readmePath = Join-Path $stage '00_README.txt'
$readme | Out-File -LiteralPath $readmePath -Encoding UTF8 -Force

# ---------------------------------------------------------------- 7. 打包（手写 zip：包内一律 / 分隔的 ASCII 名）
if (-not $OutDir) {
    $OutDir = [Environment]::GetFolderPath('Desktop')
    if (-not $OutDir) { $OutDir = Join-Path $env:USERPROFILE 'Desktop' }
}
if (-not (Test-Path -LiteralPath $OutDir)) {
    try { New-Item -ItemType Directory -Force -Path $OutDir | Out-Null } catch { $OutDir = $env:TEMP }
}
$zipPath = Join-Path $OutDir ("课程学习助手_日志_" + $stamp + ".zip")

$zipped = $false
try {
    Add-Type -AssemblyName System.IO.Compression -ErrorAction Stop
    Add-Type -AssemblyName System.IO.Compression.FileSystem -ErrorAction Stop
    if (Test-Path -LiteralPath $zipPath) { Remove-Item -LiteralPath $zipPath -Force }
    $zip = [System.IO.Compression.ZipFile]::Open($zipPath, [System.IO.Compression.ZipArchiveMode]::Create)
    try {
        $entries = New-Object System.Collections.Generic.List[object]
        $entries.Add([pscustomobject]@{ Source = $readmePath; Packed = '00_README.txt' })
        foreach ($p in $plan) { $entries.Add($p) }
        foreach ($item in $entries) {
            if (-not (Test-Path -LiteralPath $item.Source)) { continue }
            $entry = $zip.CreateEntry($item.Packed, [System.IO.Compression.CompressionLevel]::Optimal)
            $es = $entry.Open()
            try {
                $fs = [System.IO.File]::OpenRead($item.Source)
                try { $fs.CopyTo($es) } finally { $fs.Dispose() }
            } finally { $es.Dispose() }
        }
        $zipped = $true
    } finally {
        $zip.Dispose()
    }
} catch {
    Warn ('打包失败：' + $_.Exception.Message)
}

Say ''
Say '---------------- 导出结果 ----------------' Cyan
if ($plan.Count -gt 0) {
    foreach ($p in ($plan | Sort-Object Packed)) {
        $sizeKB = [math]::Round((Get-Item -LiteralPath $p.Source).Length / 1KB, 1)
        Say ('  {0,9} KB  {1}' -f $sizeKB, $p.Packed)
    }
} else {
    Warn '没有收集到任何日志文件（程序可能还没运行过）。'
}

if ($zipped -and (Test-Path -LiteralPath $zipPath)) {
    $mb = [math]::Round((Get-Item -LiteralPath $zipPath).Length / 1MB, 2)
    Say ''
    Ok ("已生成：" + $zipPath)
    Ok ("大小：" + $mb + " MB")
    Say ''
    Say '请把这个 zip 发回给开发者；账号密码和 API Key 已自动打码。' Yellow
} else {
    Say ''
    Fail '打包失败，请把上面的错误信息截图发回。'
}

try { Remove-Item $stage -Recurse -Force -ErrorAction SilentlyContinue } catch { }

if (-not $NoPause) {
    Say ''
    Read-Host '按回车退出' | Out-Null
}
if ($zipped) { exit 0 } else { exit 1 }
