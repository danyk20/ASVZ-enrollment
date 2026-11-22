# Sets up asvz-enroll on Windows. The setup page runs it in PowerShell like this:
#
#   [Net.ServicePointManager]::SecurityProtocol='Tls12'; & ([scriptblock]::Create((irm https://danyk20.github.io/ASVZ-enrollment/setup.ps1))) -LessonId 777113 -Weekday Tuesday -Time 19:13
#
# It runs in Windows PowerShell 5.1 and in PowerShell 7, without administrator rights. It
# installs uv if needed, downloads the app into $HOME\ASVZ-enrollment, asks for the SWITCH
# edu-ID login and the optional email settings, writes the .env file, tests the login and
# creates a weekly Windows scheduled task that runs scripts\enrol-weekly.bat.
#
# Testing only (visitors never set this): $env:ASVZ_ZIP_URL downloads the app from this URL
# instead of GitHub.

param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^\d+$')]
    [string]$LessonId,

    [Parameter(Mandatory = $true)]
    [ValidateSet('Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday')]
    [string]$Weekday,

    [Parameter(Mandatory = $true)]
    [ValidatePattern('^([01]\d|2[0-3]):[0-5]\d$')]
    [string]$Time
)

$ErrorActionPreference = 'Continue'
$GuideUrl = 'https://github.com/danyk20/ASVZ-enrollment/blob/main/SETUP-GUIDE.md'

function Stop-Setup([string]$Message) {
    Write-Host ''
    Write-Host "Error: $Message" -ForegroundColor Red
    throw $Message
}

function Write-Step([int]$Number, [string]$Text) {
    Write-Host ''
    Write-Host "[$Number/6] $Text"
}

function Read-Yes([string]$Question, [bool]$DefaultYes) {
    while ($true) {
        $answer = (Read-Host "$Question ").Trim()
        if ($answer -eq '') { return $DefaultYes }
        if ($answer -match '^(y|yes)$') { return $true }
        if ($answer -match '^(n|no)$') { return $false }
        Write-Host 'Please answer y or n.'
    }
}

function ConvertTo-PlainText([Security.SecureString]$Secure) {
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($Secure)
    try {
        return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    }
    finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    }
}

# Escapes a value for a double-quoted line in .env: backslash and double quote.
function Escape-Value([string]$Value) {
    return $Value.Replace('\', '\\').Replace('"', '\"')
}

# The whole line of the app's .env file that sets KEY, or $null.
function Get-SavedLine([string]$Key) {
    if (-not (Test-Path $script:EnvPath)) { return $null }
    foreach ($line in [IO.File]::ReadAllLines($script:EnvPath, [Text.Encoding]::UTF8)) {
        if ($line.StartsWith("$Key=")) { return $line }
    }
    return $null
}

# The value of KEY in the app's .env file, without the quotes. Empty if missing.
function Get-SavedValue([string]$Key) {
    $line = Get-SavedLine $Key
    if ($null -eq $line) { return '' }
    $value = $line.Substring($Key.Length + 1)
    if ($value.Length -ge 2 -and $value.StartsWith('"') -and $value.EndsWith('"')) {
        $value = $value.Substring(1, $value.Length - 2)
    }
    return $value
}

# Asks for the login and the password (twice). Returns @{ User = ...; Password = ... }.
function Read-Login {
    $user = ''
    while ($user -eq '') {
        $user = (Read-Host 'SWITCH edu-ID login (your email address)').Trim()
        if ($user -eq '') { Write-Host 'The login cannot be empty.' }
    }
    while ($true) {
        $first = ConvertTo-PlainText (Read-Host 'Password (typed hidden)' -AsSecureString)
        $second = ConvertTo-PlainText (Read-Host 'Type the password again' -AsSecureString)
        if ($first -ne '' -and $first -ceq $second) { break }
        Write-Host 'The two passwords do not match, or the password is empty. Try again.'
    }
    return @{ User = $user; Password = $first }
}

function Write-EnvFile {
    if ($script:KeepLogin) {
        $userLine = $script:KeptUserLine
        $passwordLine = $script:KeptPasswordLine
    }
    else {
        $userLine = 'ASVZ_USERNAME="' + (Escape-Value $script:LoginUser) + '"'
        $passwordLine = 'ASVZ_PASSWORD="' + (Escape-Value $script:LoginPassword) + '"'
    }
    $early = Escape-Value (Get-SavedValue 'ASVZ_EARLY_START_MINUTES')

    $lines = @(
        '# Settings for asvz-enroll. Anything given on the command line wins over this file.',
        '',
        '# Your SWITCH edu-ID login (an email address)',
        $userLine,
        $passwordLine,
        '',
        '# The number at the end of https://schalter.asvz.ch/tn/lessons/<number>',
        ('ASVZ_LESSON_ID="' + $LessonId + '"'),
        '',
        '# Optional: how many minutes before enrolment opens the app may be started.',
        '# It logs in and waits. Started earlier than this, it stops with an error. Default: 10',
        ('ASVZ_EARLY_START_MINUTES="' + $early + '"'),
        '',
        '# Optional: email the result of every enrolment attempt (success or failure).',
        '# Leave ASVZ_EMAIL_RECIPIENT empty to send no email.',
        ('ASVZ_EMAIL_RECIPIENT="' + (Escape-Value $script:EmailRecipient) + '"'),
        '# From Brevo: "SMTP & API" -> "API keys" (starts with xkeysib-)',
        ('BREVO_API_KEY="' + (Escape-Value $script:BrevoKey) + '"'),
        '# An address listed under Brevo "Senders, Domains & Dedicated IPs" -> "Senders"',
        ('BREVO_SENDER_EMAIL="' + (Escape-Value $script:BrevoSender) + '"')
    )
    $content = ($lines -join "`n") + "`n"
    # UTF-8 without a byte order mark: a BOM would break the first key.
    [IO.File]::WriteAllText($script:EnvPath, $content, (New-Object System.Text.UTF8Encoding($false)))
}

# ---- Step 1: check the system and the arguments ------------------------------------------

Write-Step 1 'Checking the lesson and your system...'
if ([Environment]::OSVersion.Platform -ne 'Win32NT') {
    Stop-Setup 'This command is for Windows. On macOS and Linux, use the Terminal command.'
}
try {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
}
catch {
    # PowerShell 7 does not need this.
}
Write-Host "Lesson $LessonId, every $Weekday at $Time."

$appDir = Join-Path $HOME 'ASVZ-enrollment'
$envPath = Join-Path $appDir '.env'
$script:EnvPath = $envPath
$tmpDir = Join-Path ([IO.Path]::GetTempPath()) ('asvz-setup-' + [Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $tmpDir -ErrorAction Stop | Out-Null

try {
    # ---- Step 2: uv ----------------------------------------------------------------------

    Write-Step 2 'Installing uv (the tool that runs the app) if needed...'
    $uvPath = Join-Path $HOME '.local\bin\uv.exe'
    if (-not (Test-Path $uvPath)) {
        $onPath = Get-Command uv -ErrorAction SilentlyContinue
        if ($null -ne $onPath) {
            $uvPath = $onPath.Source
        }
        else {
            try {
                Invoke-Expression (Invoke-RestMethod -Uri 'https://astral.sh/uv/install.ps1' -ErrorAction Stop)
            }
            catch {
                Stop-Setup ('Could not install uv: ' + $_.Exception.Message)
            }
            if (-not (Test-Path $uvPath)) {
                Stop-Setup "uv was installed, but not to $uvPath."
            }
        }
    }
    Write-Host "Using $uvPath"

    # ---- Step 3: the app -----------------------------------------------------------------

    Write-Step 3 "Downloading the app to $appDir..."
    $zipUrl = 'https://github.com/danyk20/ASVZ-enrollment/archive/refs/heads/main.zip'
    if ($env:ASVZ_ZIP_URL) { $zipUrl = $env:ASVZ_ZIP_URL }
    $zipFile = Join-Path $tmpDir 'app.zip'
    $unpackDir = Join-Path $tmpDir 'unpacked'
    try {
        Invoke-WebRequest -Uri $zipUrl -OutFile $zipFile -UseBasicParsing -ErrorAction Stop
    }
    catch {
        Stop-Setup ('Could not download the app. Check your internet connection and try again. ' + $_.Exception.Message)
    }
    try {
        Expand-Archive -Path $zipFile -DestinationPath $unpackDir -Force -ErrorAction Stop
    }
    catch {
        Stop-Setup 'The download is not a valid ZIP file.'
    }
    $newApp = Join-Path $unpackDir 'ASVZ-enrollment-main'
    if (-not (Test-Path (Join-Path $newApp 'pyproject.toml'))) {
        Stop-Setup 'The download does not contain the app.'
    }

    $savedEnv = $null
    if (Test-Path $appDir) {
        # Only ever replace a folder that this script installed: never a git checkout, and
        # never an unrelated folder that happens to have the same name.
        if (Test-Path (Join-Path $appDir '.git')) {
            Stop-Setup "$appDir is a git checkout. Update it with 'git pull' instead, or move it away and run this again."
        }
        $existingProject = Join-Path $appDir 'pyproject.toml'
        if (-not ((Test-Path $existingProject) -and (Select-String -Path $existingProject -Pattern '^name = "asvz-enroll"' -Quiet))) {
            Stop-Setup "$appDir already exists but is not this app. Rename or move it, then run this again."
        }
        Write-Host 'The app folder already exists: updating it and keeping your .env file.'
        if (Test-Path $envPath) {
            $savedEnv = Join-Path $tmpDir 'saved.env'
            Copy-Item $envPath $savedEnv -ErrorAction Stop
        }
        Remove-Item -Recurse -Force $appDir -ErrorAction Stop
    }
    Move-Item $newApp $appDir -ErrorAction Stop
    if ($null -ne $savedEnv) {
        Move-Item $savedEnv $envPath -ErrorAction Stop
    }
    Write-Host "App installed in $appDir"

    # ---- Step 4: login and optional email ------------------------------------------------

    Write-Step 4 'Login and optional email...'
    $script:KeepLogin = $false
    $script:KeptUserLine = ''
    $script:KeptPasswordLine = ''
    $script:LoginUser = ''
    $script:LoginPassword = ''
    $hasLogin = $false

    $savedUser = Get-SavedValue 'ASVZ_USERNAME'
    if ($savedUser -ne '' -and (Read-Yes "Keep the saved login for $savedUser? [Y/n]" $true)) {
        $script:KeepLogin = $true
        $hasLogin = $true
        $script:LoginUser = $savedUser
        $script:KeptUserLine = Get-SavedLine 'ASVZ_USERNAME'
        $script:KeptPasswordLine = Get-SavedLine 'ASVZ_PASSWORD'
        if ($null -eq $script:KeptPasswordLine) { $script:KeptPasswordLine = 'ASVZ_PASSWORD=""' }
    }
    if (-not $script:KeepLogin) {
        if (Read-Yes 'Enter your SWITCH edu-ID login now? [Y/n]' $true) {
            $login = Read-Login
            $script:LoginUser = $login.User
            $script:LoginPassword = $login.Password
            $hasLogin = $true
        }
        else {
            Write-Host "You can add it later in $envPath"
        }
    }

    $script:EmailRecipient = ''
    $script:BrevoKey = ''
    $script:BrevoSender = ''
    if (Read-Yes 'Get an email after every attempt? [y/N]' $false) {
        Write-Host "Brevo steps: $GuideUrl#email-after-every-attempt-optional"
        while ($true) {
            if ($script:LoginUser -ne '') {
                $typed = (Read-Host "Send the emails to [$($script:LoginUser)]").Trim()
            }
            else {
                $typed = (Read-Host 'Send the emails to').Trim()
            }
            if ($typed -ne '') { $script:EmailRecipient = $typed } else { $script:EmailRecipient = $script:LoginUser }
            if ($script:EmailRecipient -ne '') { break }
            Write-Host 'Please type an email address.'
        }
        while ($true) {
            $script:BrevoKey = ConvertTo-PlainText (Read-Host 'Brevo API key (starts with xkeysib-) (typed hidden)' -AsSecureString)
            if ($script:BrevoKey -ne '') { break }
            Write-Host 'The API key cannot be empty.'
        }
        while ($true) {
            $script:BrevoSender = (Read-Host 'Sender address (verified in Brevo)').Trim()
            if ($script:BrevoSender -ne '') { break }
            Write-Host 'The sender address cannot be empty.'
        }
    }

    Write-EnvFile
    Write-Host "Settings written to $envPath (readable only by your Windows account)."

    # ---- Step 5: test the login ----------------------------------------------------------

    Write-Step 5 'Testing the login...'
    if (-not $hasLogin) {
        Write-Host 'No login was entered, so there is nothing to test yet.'
    }
    else {
        while ($true) {
            Push-Location $appDir
            try {
                & $uvPath run asvz-enroll --check-login
                $loginCode = $LASTEXITCODE
            }
            finally {
                Pop-Location
            }
            if ($loginCode -eq 0) {
                Write-Host 'The login works.'
                break
            }
            Write-Host ''
            Write-Host 'The login test failed. The message above says why.'
            if (-not (Read-Yes 'Enter the login again? [Y/n]' $true)) {
                Write-Host "Continuing without a working login. Fix it later in $envPath"
                break
            }
            $login = Read-Login
            $script:LoginUser = $login.User
            $script:LoginPassword = $login.Password
            $script:KeepLogin = $false
            Write-EnvFile
            Write-Host "Settings written to $envPath"
        }
    }

    # ---- Step 6: the weekly schedule -----------------------------------------------------

    Write-Step 6 'Scheduling the weekly run...'
    $runner = Join-Path $appDir 'scripts\enrol-weekly.bat'
    $taskName = "ASVZ enrolment $LessonId"
    try {
        $action = New-ScheduledTaskAction -Execute $runner -Argument "--lesson-id $LessonId" -WorkingDirectory $appDir -ErrorAction Stop
        $trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek $Weekday -At $Time -ErrorAction Stop
        $settings = New-ScheduledTaskSettingsSet -WakeToRun -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ErrorAction Stop
        Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Force -ErrorAction Stop | Out-Null
    }
    catch {
        Stop-Setup ('Could not create the scheduled task: ' + $_.Exception.Message)
    }
    Write-Host "Scheduled task '$taskName' created: every $Weekday at $Time."

    # ---- Summary -------------------------------------------------------------------------

    $lessonName = ''
    Push-Location $appDir
    try {
        $nameOutput = & $uvPath run python -c "from asvz_enroll.lesson_api import get_lesson; l = get_lesson($LessonId); print(l.sport_name + ': ' + l.title)" 2>$null
        if ($LASTEXITCODE -eq 0) {
            $lessonName = ($nameOutput | Out-String).Trim()
        }
    }
    catch {
        $lessonName = ''
    }
    finally {
        Pop-Location
    }

    Write-Host ''
    if ($lessonName -ne '') {
        Write-Host "Done. Every $Weekday at $Time your computer will enrol you in $lessonName."
    }
    else {
        Write-Host "Done. Every $Weekday at $Time your computer will try to enrol you in lesson $LessonId."
    }
    Write-Host ''
    Write-Host 'Three things to remember:'
    Write-Host '1. Keep the computer plugged in and awake at that time: Settings > System > Power & battery > Sleep: Never.'
    Write-Host "2. Each run is logged to $(Join-Path $HOME 'asvz.log')"
    Write-Host "3. To remove the schedule, run: Unregister-ScheduledTask -TaskName `"$taskName`" -Confirm:`$false"

    $timeZone = (Get-TimeZone).Id
    if ($timeZone -ne 'W. Europe Standard Time') {
        Write-Host ''
        Write-Host "Warning: this computer's time zone is '$timeZone', not 'W. Europe Standard Time' (Zurich). The start time above is in Zurich time, so check the clock settings."
    }
}
finally {
    if (Test-Path $tmpDir) {
        Remove-Item -Recurse -Force $tmpDir -ErrorAction SilentlyContinue
    }
}
