<#
    STLIX GATEWAY — التشغيل للعرض
    ================================================================
    أمر واحد بيجهّز كل حاجة ويشغّل المنصّة علشان الزملاء يفتحوها من أجهزتهم.

        .\deploy.ps1                 # عرض على شبكة الشركة (الافتراضي)
        .\deploy.ps1 -LocalOnly      # على الجهاز ده بس
        .\deploy.ps1 -SkipTests      # من غير اختبارات (مش منصوح بيه قبل عرض)
        .\deploy.ps1 -Port 8000

    بيعمل بالترتيب: البيئة → المفتاح → الاختبارات → فحص ما قبل العرض → التشغيل.
    وبيقف لو أي خطوة وقعت، لأن سيرفر شغّال بصفحة بتقع أوحش من سيرفر مش شغّال.
#>
[CmdletBinding()]
param(
    # 3900 وليس 8000: على جهاز المالك فيه بروسيس تاني ماسك 127.0.0.1:8000
    # فأي فتح من نفس الجهاز بيروح له مش لنا (الأكثر تحديدًا بيكسب)، و8080 ضمن
    # نطاق محجوز في ويندوز (WinError 10013). البورت 3900 اتجرّب واشتغل.
    [int]$Port = 3900,
    [switch]$LocalOnly,
    [switch]$SkipTests,
    [switch]$NoBrowser
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

function Say($m)  { Write-Host "  $m" -ForegroundColor Cyan }
function Ok($m)   { Write-Host "  OK  $m" -ForegroundColor Green }
function Warn($m) { Write-Host "  !!  $m" -ForegroundColor Yellow }
function Die($m)  { Write-Host "`n  XX  $m`n" -ForegroundColor Red; exit 1 }

Write-Host ""
Write-Host "  ==========================================" -ForegroundColor DarkCyan
Write-Host "   STLIX GATEWAY  —  DEPLOY" -ForegroundColor White
Write-Host "  ==========================================" -ForegroundColor DarkCyan
Write-Host ""

# --- 1) البيئة -----------------------------------------------------------
$py = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path $py)) {
    Say "مافيش .venv — بعملها دلوقتي..."
    python -m venv .venv
    if (-not (Test-Path $py)) { Die "فشل إنشاء البيئة. اتأكد إن python في الـPATH." }
}
Ok "البيئة: .venv"

Say "بيثبّت المكتبات..."
& $py -m pip install --quiet --disable-pip-version-check -r requirements.txt
if ($LASTEXITCODE -ne 0) { Die "pip install وقع." }
if (-not $SkipTests) {
    & $py -m pip install --quiet --disable-pip-version-check pytest pytest-asyncio respx
}
Ok "المكتبات متثبّتة"

# --- 2) المفتاح ----------------------------------------------------------
# من غير مفتاح، أي جهاز على شبكة الشركة يقدر ينده /api/v1/* مباشرة ويقرا
# أرصدة العملاء والموردين. الصفحات نفسها المفروض تفتح لأي حد بيتفرّج — الكوكي
# بيتظبّط تلقائي — إنما الـAPI الخام لأ. فلو المفتاح فاضي، بنولّد واحد.
$envPath = Join-Path $root '.env'
if (-not (Test-Path $envPath)) { Die "مافيش ملف .env — انسخ .env.example وظبّطه الأول." }

$envText = Get-Content $envPath -Raw -Encoding UTF8
$keyLine = ($envText -split "`n") | Where-Object { $_ -match '^\s*GATEWAY_API_KEY\s*=' }
$keyVal  = if ($keyLine) { ($keyLine -split '=', 2)[1].Trim() } else { '' }

if ([string]::IsNullOrWhiteSpace($keyVal)) {
    $bytes = New-Object byte[] 24
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    $newKey = ([System.BitConverter]::ToString($bytes) -replace '-', '').ToLower()
    if ($keyLine) {
        $envText = $envText -replace '(?m)^\s*GATEWAY_API_KEY\s*=.*$', "GATEWAY_API_KEY=$newKey"
    } else {
        $envText = $envText.TrimEnd() + "`nGATEWAY_API_KEY=$newKey`n"
    }
    [System.IO.File]::WriteAllText($envPath, $envText, (New-Object System.Text.UTF8Encoding $false))
    Warn "GATEWAY_API_KEY كان فاضي — ولّدت واحد وحطيته في .env."
    Warn "الصفحات هتفضل تفتح عادي لأي زميل (الكوكي بيتظبّط لوحده)؛ اللي اتقفل هو"
    Warn "الـAPI الخام من غير مفتاح."
} else {
    Ok "مفتاح الجيتواي متظبّط"
}

# --- 3) الاختبارات -------------------------------------------------------
if ($SkipTests) {
    Warn "الاختبارات اتخطّت (-SkipTests)"
} else {
    Say "بيشغّل الاختبارات..."
    & $py -m pytest -q
    if ($LASTEXITCODE -ne 0) { Die "فيه اختبارات وقعت. متعرضش قبل ما تتصلّح." }
    Ok "كل الاختبارات عدّت"
}

# --- 4) فحص ما قبل العرض -------------------------------------------------
$bindHost = if ($LocalOnly) { '127.0.0.1' } else { '0.0.0.0' }
$env:SG_BIND_HOST = $bindHost
& $py scripts\preflight.py
if ($LASTEXITCODE -ne 0) { Die "فحص ما قبل العرض لقى مانع." }

# --- 5) العناوين ---------------------------------------------------------
$ips = @()
try {
    $ips = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction Stop |
           Where-Object { $_.IPAddress -notmatch '^(127\.|169\.254\.)' -and $_.PrefixOrigin -ne 'WellKnown' } |
           Select-Object -ExpandProperty IPAddress
} catch { }

Write-Host ""
Write-Host "  ------------------------------------------" -ForegroundColor DarkCyan
Write-Host "   افتح من الجهاز ده:" -ForegroundColor White
Write-Host "     http://localhost:$Port/tools/tour        <- ابدأ من هنا" -ForegroundColor Green
Write-Host "     http://localhost:$Port/tools/platform" -ForegroundColor Gray
if (-not $LocalOnly -and $ips.Count -gt 0) {
    Write-Host ""
    Write-Host "   الزملاء يفتحوا من أجهزتهم:" -ForegroundColor White
    foreach ($ip in $ips) {
        Write-Host "     http://${ip}:$Port/tools/tour" -ForegroundColor Green
    }
    Write-Host ""
    Write-Host "   لو مافتحش عندهم، الفايروول بيمنع البورت. من PowerShell كأدمن:" -ForegroundColor DarkGray
    Write-Host "     New-NetFirewallRule -DisplayName 'Stlix Gateway' -Direction Inbound -Protocol TCP -LocalPort $Port -Action Allow" -ForegroundColor DarkGray
}
Write-Host "  ------------------------------------------" -ForegroundColor DarkCyan
Write-Host ""
Warn "شبكة الشركة بس — متعرّضش البورت ده على الإنترنت."
Write-Host ""

if (-not $NoBrowser) {
    Start-Job -ScriptBlock {
        Start-Sleep -Seconds 4
        $u = "http://localhost:$using:Port/tools/tour"
        $chrome = @(
            "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
            "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
            "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe"
        ) | Where-Object { Test-Path $_ } | Select-Object -First 1
        if ($chrome) { Start-Process $chrome $u } else { Start-Process $u }
    } | Out-Null
}

# --- 6) التشغيل ----------------------------------------------------------
Say "بيشغّل... (Ctrl+C يوقف)"
Write-Host ""
& $py -m uvicorn app.main:app --host $bindHost --port $Port
