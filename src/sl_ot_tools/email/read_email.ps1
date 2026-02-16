# read_email.ps1 — Read emails from Outlook via MAPI COM
#
# Called by read_email.sh (bash wrapper). Not intended to be run directly.
#
# Parameters:
#   -Days          Number of days to look back (default: 7)
#   -OutputDir     Windows path to write results
#   -Folders       Comma-separated folder names (default: "Inbox,Archive")
#   -SkipInline    Skip inline image attachments
#   -Account       Specific account name (default: first account)

param(
    [int]$Days = 7,
    [string]$OutputDir = "",
    [string]$Folders = "Inbox,Archive",
    [switch]$SkipInline,
    [string]$Account = ""
)

$ErrorActionPreference = "Continue"

# --- Validate output directory ---
if (-not $OutputDir) {
    Write-Error "OutputDir is required"
    exit 1
}

if (-not (Test-Path $OutputDir)) {
    New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
}

$errorsLog = Join-Path $OutputDir "_errors.log"

function Write-Log {
    param([string]$Message)
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -Path $errorsLog -Value "[$ts] $Message"
}

# --- Connect to Outlook ---
try {
    $outlook = New-Object -ComObject Outlook.Application
    $ns = $outlook.GetNamespace("MAPI")
}
catch {
    Write-Error "Failed to connect to Outlook. Is Outlook running?"
    Write-Error $_.Exception.Message
    exit 1
}

# --- Determine account ---
$targetAccount = $null
if ($Account) {
    foreach ($store in $ns.Stores) {
        if ($store.DisplayName -like "*$Account*") {
            $targetAccount = $store
            break
        }
    }
    if (-not $targetAccount) {
        Write-Error "Account matching '$Account' not found"
        exit 1
    }
}
else {
    # Use the default store (primary account)
    $targetAccount = $ns.DefaultStore
}

$accountName = $targetAccount.DisplayName

# --- Build folder list ---
$folderNames = $Folders -split "," | ForEach-Object { $_.Trim() }
$foldersToScan = @()

foreach ($fname in $folderNames) {
    try {
        if ($fname -eq "Inbox") {
            # GetDefaultFolder(6) = Inbox
            $folder = $ns.GetDefaultFolder(6)
            $foldersToScan += @{ Name = "Inbox"; Folder = $folder }
        }
        else {
            # Navigate from the account root
            $root = $targetAccount.GetRootFolder()
            $folder = $root.Folders.Item($fname)
            $foldersToScan += @{ Name = $fname; Folder = $folder }
        }
    }
    catch {
        Write-Log "WARNING: Folder '$fname' not found under '$accountName'. Skipping."
        Write-Host "WARNING: Folder '$fname' not found. Skipping." -ForegroundColor Yellow
    }
}

if ($foldersToScan.Count -eq 0) {
    Write-Error "No valid folders found to scan"
    exit 1
}

# --- Date filter ---
$cutoff = (Get-Date).AddDays(-$Days).ToString("MM/dd/yyyy HH:mm")
$filter = "[ReceivedTime] >= '$cutoff'"

# --- Process emails ---
$allEmails = @()
$totalAttachments = 0
$skippedInline = 0

foreach ($folderInfo in $foldersToScan) {
    $folderName = $folderInfo.Name
    $folder = $folderInfo.Folder

    Write-Host "Scanning: $folderName..."

    try {
        $items = $folder.Items
        $items.Sort("[ReceivedTime]", $true)  # newest first
        $filtered = $items.Restrict($filter)
    }
    catch {
        Write-Log "ERROR: Failed to filter folder '$folderName': $($_.Exception.Message)"
        continue
    }

    $count = $filtered.Count
    Write-Host "  Found $count emails in last $Days days"

    for ($i = 1; $i -le $count; $i++) {
        try {
            $item = $filtered.Item($i)

            # Skip non-mail items (meeting requests, etc.)
            if ($item.Class -ne 43) {
                continue
            }

            # Generate a short ID from EntryID
            $hasher = [System.Security.Cryptography.SHA256]::Create()
            $bytes = [System.Text.Encoding]::UTF8.GetBytes($item.EntryID)
            $hash = $hasher.ComputeHash($bytes)
            $id = ($hash[0..5] | ForEach-Object { $_.ToString("x2") }) -join ""

            # Extract fields
            $subject = $item.Subject
            $fromName = $item.SenderName
            $fromEmail = ""
            try {
                $fromEmail = $item.SenderEmailAddress
                # Resolve Exchange addresses
                if ($item.SenderEmailType -eq "EX") {
                    try {
                        $fromEmail = $item.Sender.GetExchangeUser().PrimarySmtpAddress
                    }
                    catch {
                        $fromEmail = $item.SenderEmailAddress
                    }
                }
            }
            catch { }

            $to = $item.To
            $cc = $item.CC

            # Extract recipient email addresses (To and CC)
            $toRecipients = @()
            $ccRecipients = @()
            try {
                foreach ($recip in $item.Recipients) {
                    $recipEmail = ""
                    try {
                        if ($recip.AddressEntry.Type -eq "EX") {
                            $recipEmail = $recip.AddressEntry.GetExchangeUser().PrimarySmtpAddress
                        }
                        else {
                            $recipEmail = $recip.Address
                        }
                    }
                    catch {
                        $recipEmail = $recip.Address
                    }
                    $recipObj = @{
                        name  = $recip.Name
                        email = $recipEmail
                    }
                    # Type 1 = To, Type 2 = CC, Type 3 = BCC
                    if ($recip.Type -eq 1) {
                        $toRecipients += $recipObj
                    }
                    elseif ($recip.Type -eq 2) {
                        $ccRecipients += $recipObj
                    }
                }
            }
            catch {
                Write-Log "WARNING: Failed to extract recipients for '$subject': $($_.Exception.Message)"
            }
            $date = $item.ReceivedTime.ToString("yyyy-MM-ddTHH:mm:ss")
            $bodyText = $item.Body
            $bodyFormat = "Plain"
            if ($item.BodyFormat -eq 2) { $bodyFormat = "HTML" }
            elseif ($item.BodyFormat -eq 3) { $bodyFormat = "RTF" }

            # Body preview (first 200 chars, cleaned)
            $preview = ($bodyText -replace '\r?\n', ' ' -replace '\s+', ' ').Trim()
            if ($preview.Length -gt 200) {
                $preview = $preview.Substring(0, 200) + "..."
            }

            # Save body text
            $bodyFile = "${id}_body.txt"
            $bodyPath = Join-Path $OutputDir $bodyFile
            Set-Content -Path $bodyPath -Value $bodyText -Encoding UTF8

            # Save HTML body if available
            $htmlFile = $null
            if ($item.BodyFormat -eq 2) {
                $htmlFile = "${id}_body.html"
                $htmlPath = Join-Path $OutputDir $htmlFile
                Set-Content -Path $htmlPath -Value $item.HTMLBody -Encoding UTF8
            }

            # Process attachments
            $attachmentsList = @()
            if ($item.Attachments.Count -gt 0) {
                for ($j = 1; $j -le $item.Attachments.Count; $j++) {
                    try {
                        $att = $item.Attachments.Item($j)

                        # Check if inline
                        $isInline = $false
                        try {
                            $cid = $att.PropertyAccessor.GetProperty("http://schemas.microsoft.com/mapi/proptag/0x3712001F")
                            if ($cid) { $isInline = $true }
                        }
                        catch { }

                        if ($SkipInline -and $isInline) {
                            $skippedInline++
                            continue
                        }

                        # Skip embedded OLE objects (type 5/6)
                        if ($att.Type -eq 5 -or $att.Type -eq 6) {
                            continue
                        }

                        $originalName = $att.FileName
                        $safeFilename = "${id}_att_${j}_${originalName}"
                        $attPath = Join-Path $OutputDir $safeFilename

                        $att.SaveAsFile($attPath)
                        $attSize = (Get-Item $attPath).Length
                        $totalAttachments++

                        $attachmentsList += @{
                            filename      = $safeFilename
                            original_name = $originalName
                            size          = $attSize
                            is_inline     = $isInline
                        }
                    }
                    catch {
                        Write-Log "WARNING: Failed to save attachment $j from '$subject': $($_.Exception.Message)"
                    }
                }
            }

            $emailObj = @{
                id             = $id
                subject        = $subject
                from_name      = $fromName
                from_email     = $fromEmail
                to             = $to
                cc             = $cc
                to_recipients  = $toRecipients
                cc_recipients  = $ccRecipients
                date           = $date
                folder         = $folderName
                body_format    = $bodyFormat
                body_file      = $bodyFile
                html_file      = $htmlFile
                body_preview   = $preview
                attachments    = $attachmentsList
            }

            $allEmails += $emailObj
        }
        catch {
            Write-Log "ERROR: Failed to process email $i in '$folderName': $($_.Exception.Message)"
        }
    }
}

# --- Write index.json ---
$index = @{
    generated  = (Get-Date).ToString("yyyy-MM-ddTHH:mm:ss")
    parameters = @{
        days    = $Days
        folders = $folderNames
        account = $accountName
    }
    emails     = $allEmails
    stats      = @{
        total_emails      = $allEmails.Count
        total_attachments = $totalAttachments
        skipped_inline    = $skippedInline
        folders_scanned   = $folderNames
    }
}

$indexPath = Join-Path $OutputDir "index.json"
# Write without BOM (PowerShell 5.1 UTF8 adds BOM, so use .NET directly)
$jsonText = $index | ConvertTo-Json -Depth 10
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($indexPath, $jsonText, $utf8NoBom)

# --- Summary ---
Write-Host ""
Write-Host "=== Email Export Complete ==="
Write-Host "  Emails:      $($allEmails.Count)"
Write-Host "  Attachments: $totalAttachments"
Write-Host "  Skipped:     $skippedInline inline"
Write-Host "  Output:      $OutputDir"
Write-Host "  Index:       $indexPath"
