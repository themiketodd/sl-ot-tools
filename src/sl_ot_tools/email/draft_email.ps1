# draft_email.ps1 — Create a draft email in Outlook via MAPI COM
#
# Called by draft_email.sh (bash wrapper). Not intended to be run directly.
#
# Parameters:
#   -To          Recipient email addresses (semicolon-separated)
#   -Cc          CC recipients (optional, semicolon-separated)
#   -Subject     Email subject line
#   -Body        Email body text (short bodies only; prefer -BodyFile)
#   -BodyFile    Path to file containing the email body
#   -BodyFormat  "Plain" or "HTML" (default: Plain)
#   -Account     Specific account name (default: first account)

param(
    [string]$To = "",
    [string]$Cc = "",
    [string]$Subject = "",
    [string]$Body = "",
    [string]$BodyFile = "",
    [string]$BodyFormat = "Plain",
    [string]$Account = "",
    [string]$Timezone = ""
)

$ErrorActionPreference = "Stop"

# --- Validate required fields ---
if (-not $To) {
    Write-Error "To is required"
    exit 1
}
if (-not $Subject) {
    Write-Error "Subject is required"
    exit 1
}

# --- Resolve body content ---
if ($BodyFile) {
    if (-not (Test-Path $BodyFile)) {
        Write-Error "Body file not found: $BodyFile"
        exit 1
    }
    $Body = Get-Content -Path $BodyFile -Raw -Encoding UTF8
}

if (-not $Body) {
    Write-Error "Body is required (via -Body or -BodyFile)"
    exit 1
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
if ($Account) {
    $targetAccount = $null
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
    Write-Host "Using account: $($targetAccount.DisplayName)"
}

# --- Create draft ---
try {
    $mail = $outlook.CreateItem(0)  # olMailItem = 0
    $mail.To = $To
    if ($Cc) {
        $mail.CC = $Cc
    }
    $mail.Subject = $Subject

    if ($BodyFormat -eq "HTML") {
        $mail.HTMLBody = $Body
    }
    else {
        $mail.Body = $Body
    }

    # If a specific account was requested, set the SendUsingAccount
    if ($Account -and $targetAccount) {
        foreach ($acct in $outlook.Session.Accounts) {
            if ($acct.DisplayName -like "*$Account*") {
                $mail.SendUsingAccount = $acct
                break
            }
        }
    }

    # Set the client submit time so the draft sorts by current date/time
    # PR_CLIENT_SUBMIT_TIME = 0x00390040
    if ($Timezone) {
        try {
            $tz = [System.TimeZoneInfo]::FindSystemTimeZoneById($Timezone)
            $now = [System.TimeZoneInfo]::ConvertTimeFromUtc([System.DateTime]::UtcNow, $tz)
        }
        catch {
            # IANA names (e.g. "America/Los_Angeles") aren't recognized on older Windows.
            # Try common IANA-to-Windows mappings before falling back to local time.
            $ianaMap = @{
                "America/New_York"      = "Eastern Standard Time"
                "America/Chicago"       = "Central Standard Time"
                "America/Denver"        = "Mountain Standard Time"
                "America/Los_Angeles"   = "Pacific Standard Time"
                "America/Phoenix"       = "US Mountain Standard Time"
                "America/Anchorage"     = "Alaskan Standard Time"
                "Pacific/Honolulu"      = "Hawaiian Standard Time"
                "Europe/London"         = "GMT Standard Time"
                "Europe/Berlin"         = "W. Europe Standard Time"
                "Asia/Tokyo"            = "Tokyo Standard Time"
                "Asia/Shanghai"         = "China Standard Time"
                "Australia/Sydney"      = "AUS Eastern Standard Time"
                "UTC"                   = "UTC"
            }
            $winId = $ianaMap[$Timezone]
            if ($winId) {
                try {
                    $tz = [System.TimeZoneInfo]::FindSystemTimeZoneById($winId)
                    $now = [System.TimeZoneInfo]::ConvertTimeFromUtc([System.DateTime]::UtcNow, $tz)
                }
                catch {
                    Write-Host "WARNING: Could not resolve timezone '$Timezone', using local time"
                    $now = Get-Date
                }
            }
            else {
                Write-Host "WARNING: Unknown timezone '$Timezone', using local time"
                $now = Get-Date
            }
        }
    }
    else {
        $now = Get-Date
    }
    $mail.PropertyAccessor.SetProperty("http://schemas.microsoft.com/mapi/proptag/0x00390040", $now)

    $mail.Save()  # Saves to Drafts folder

    Write-Host ""
    Write-Host "=== Draft Created ==="
    Write-Host "  To:      $To"
    if ($Cc) {
        Write-Host "  CC:      $Cc"
    }
    Write-Host "  Subject: $Subject"
    Write-Host "  Format:  $BodyFormat"
    Write-Host "  Status:  Saved to Drafts folder"
}
catch {
    Write-Error "Failed to create draft: $($_.Exception.Message)"
    exit 1
}
