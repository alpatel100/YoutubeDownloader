# ============================================================
#  YouTube Clip Downloader
#  Reads download_config.txt and processes all listed jobs
# ============================================================

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $ScriptDir

$ConfigFile = Join-Path $ScriptDir "download_config.txt"
$ConfFile   = Join-Path $ScriptDir "yt-dlp.conf"

# Use pip-installed yt-dlp (python -m yt_dlp) for full EJS challenge solver support.
# Falls back to yt-dlp.exe if python is not available.
$YtDlpExe = Join-Path $ScriptDir "yt-dlp.exe"
$UsePython = $false
try {
    $null = & python -c "import yt_dlp" 2>&1
    if ($LASTEXITCODE -eq 0) { $UsePython = $true }
} catch {}

if ($UsePython) {
    Write-Host "  Using: python -m yt_dlp (pip install, full EJS support)" -ForegroundColor DarkGray
} else {
    Write-Host "  Using: yt-dlp.exe (run: pip install yt-dlp[default] for EJS support)" -ForegroundColor Yellow
}

# -- read config file ----------------------------------------
if (-not (Test-Path $ConfigFile)) {
    Write-Host "`n  ERROR: download_config.txt not found." -ForegroundColor Red
    Read-Host "`nPress Enter to exit"
    exit 1
}

$rawLines = Get-Content $ConfigFile

# -- split into job blocks separated by "---" ----------------
$allJobs      = @()
$currentBlock = New-Object System.Collections.Generic.List[string]

foreach ($line in $rawLines) {
    if ($line.Trim() -eq "---") {
        if ($currentBlock.Count -gt 0) {
            $allJobs += , $currentBlock.ToArray()
            $currentBlock = New-Object System.Collections.Generic.List[string]
        }
    } else {
        $currentBlock.Add($line)
    }
}
if ($currentBlock.Count -gt 0) {
    $allJobs += , $currentBlock.ToArray()
}

# -- parse each block into a hashtable -----------------------
$parsedJobs = @()
foreach ($block in $allJobs) {
    $job = @{}
    foreach ($line in $block) {
        $trimmed = $line.Trim()
        if ($trimmed -and -not $trimmed.StartsWith("#")) {
            $parts = $trimmed -split "=", 2
            if ($parts.Count -eq 2) {
                $job[$parts[0].Trim()] = $parts[1].Trim()
            }
        }
    }
    # Only include blocks that have a real URL
    if ($job["URL"] -and $job["URL"] -notlike "*REPLACE_WITH*") {
        $parsedJobs += $job
    }
}

if ($parsedJobs.Count -eq 0) {
    Write-Host "`n  ERROR: No valid jobs found in download_config.txt" -ForegroundColor Red
    Write-Host "  Make sure at least one URL= line is filled in." -ForegroundColor Red
    Read-Host "`nPress Enter to exit"
    exit 1
}

# -- header --------------------------------------------------
Write-Host ""
Write-Host "  ======================================" -ForegroundColor Green
Write-Host "    YouTube Clip Downloader" -ForegroundColor Green
Write-Host "  ======================================" -ForegroundColor Green
Write-Host "  Jobs found: $($parsedJobs.Count)" -ForegroundColor Cyan
Write-Host ""

$successCount = 0
$failCount    = 0

# -- process each job ----------------------------------------
for ($i = 0; $i -lt $parsedJobs.Count; $i++) {
    $job         = $parsedJobs[$i]
    $URL         = $job["URL"]
    $START       = $job["START"]
    $END         = $job["END"]
    $OUTDIR      = $job["OUTPUT_DIR"]
    $FILENAME    = $job["FILENAME"]
    $QUALITY     = $job["QUALITY"]
    $UPLOAD      = $job["UPLOAD"]
    $YT_TITLE    = $job["YT_TITLE"]
    $YT_DESC     = $job["YT_DESCRIPTION"]
    $YT_PLAYLIST = $job["YT_PLAYLIST"]

    # Map QUALITY to a yt-dlp format string (default: 1080p)
    switch ($QUALITY.ToLower()) {
        "720p"  { $FormatStr = "bv[height=720]+ba[ext=m4a]";  $QLabel = "720p" }
        "1440p" { $FormatStr = "bv[height=1440]+ba[ext=m4a]"; $QLabel = "1440p" }
        "2160p" { $FormatStr = "bv[height=2160]+ba[ext=m4a]"; $QLabel = "2160p (4K)" }
        "best"  { $FormatStr = "bv+ba[ext=m4a]";              $QLabel = "Best available" }
        default { $FormatStr = "bv[height=1080]+ba[ext=m4a]"; $QLabel = "1080p" }
    }

    Write-Host "  Job $($i + 1) of $($parsedJobs.Count)" -ForegroundColor Cyan
    Write-Host "  URL     : $URL" -ForegroundColor White
    Write-Host "  Quality : $QLabel" -ForegroundColor White

    # Validate required fields
    $jobErrors = @()
    if (-not $URL)    { $jobErrors += "URL is missing" }
    if (-not $OUTDIR) { $jobErrors += "OUTPUT_DIR is missing or blank" }

    if ($jobErrors.Count -gt 0) {
        foreach ($err in $jobErrors) {
            Write-Host "  ERROR: $err" -ForegroundColor Red
        }
        $failCount++
        Write-Host ""
        continue
    }

    # Clip range (optional)
    $hasSection = ($START -ne $null -and $START -ne "") -and ($END -ne $null -and $END -ne "")
    if ($hasSection) {
        Write-Host "  Clip    : $START -> $END" -ForegroundColor White
    } else {
        Write-Host "  Clip    : Full video" -ForegroundColor White
    }

    # Output path
    if ($FILENAME) {
        $BaseName  = [System.IO.Path]::GetFileNameWithoutExtension($FILENAME)
        $OutputArg = "$OUTDIR\$BaseName.mp4"
    } else {
        $OutputArg = "$OUTDIR\%(title)s.mp4"
    }
    Write-Host "  Output  : $OutputArg" -ForegroundColor White
    Write-Host ""
    Write-Host "  Starting download..." -ForegroundColor Yellow

    # Build yt-dlp argument list
    $ytArgs = @(
        "--config-locations", $ConfFile,
        "-f", $FormatStr,
        "-o", $OutputArg
    )
    if ($hasSection) {
        $ytArgs += "--download-sections"
        $ytArgs += "*$START-$END"
    }
    $ytArgs += $URL

    if ($UsePython) {
        & python -m yt_dlp @ytArgs
    } else {
        & $YtDlpExe @ytArgs
    }
    $ExitCode = $LASTEXITCODE

    Write-Host ""
    if ($ExitCode -eq 0) {
        Write-Host "  OK - Saved to: $OutputArg" -ForegroundColor Green
        $successCount++

        # -- upload to YouTube if requested ------------------
        if ($UPLOAD -eq "yes") {
            Write-Host ""
            Write-Host "  Upload requested -- finding downloaded file..." -ForegroundColor Yellow

            # Resolve actual file path
            if ($FILENAME) {
                # Filename was fixed -- we know the exact path
                $UploadFile = $OutputArg
            } else {
                # yt-dlp used the video title -- find the newest .mp4 in OUTDIR
                $UploadFile = Get-ChildItem -Path $OUTDIR -Filter "*.mp4" `
                    | Sort-Object LastWriteTime -Descending `
                    | Select-Object -First 1 -ExpandProperty FullName
            }

            if ($UploadFile -and (Test-Path $UploadFile)) {
                Write-Host "  Uploading: $UploadFile" -ForegroundColor Yellow

                $UploadScript = Join-Path $ScriptDir "upload_to_youtube.py"
                $pyArgs = @($UploadScript, "--file", $UploadFile)
                if ($YT_TITLE)    { $pyArgs += "--title";       $pyArgs += $YT_TITLE    }
                if ($YT_DESC)     { $pyArgs += "--description"; $pyArgs += $YT_DESC     }
                if ($YT_PLAYLIST) { $pyArgs += "--playlist";    $pyArgs += $YT_PLAYLIST }

                python @pyArgs
                if ($LASTEXITCODE -eq 0) {
                    Write-Host "  Upload OK" -ForegroundColor Green
                } else {
                    Write-Host "  Upload FAILED -- check output above" -ForegroundColor Red
                }
            } else {
                Write-Host "  ERROR: Could not find the downloaded file in $OUTDIR" -ForegroundColor Red
            }
        }
    } else {
        Write-Host "  FAILED - yt-dlp exited with code $ExitCode" -ForegroundColor Red
        $failCount++
    }
    Write-Host ""
}

# -- summary -------------------------------------------------
Write-Host "  ======================================" -ForegroundColor Cyan
Write-Host "  Done: $successCount succeeded, $failCount failed." -ForegroundColor Cyan
Write-Host "  ======================================" -ForegroundColor Cyan
Write-Host ""
Read-Host "Press Enter to close"
