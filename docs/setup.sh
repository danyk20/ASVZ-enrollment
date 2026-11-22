#!/bin/sh
# Sets up asvz-enroll on macOS or Linux. The setup page runs it like this:
#
#   curl -fsSL https://danyk20.github.io/ASVZ-enrollment/setup.sh | sh -s -- \
#       --lesson-id 777113 --weekday 2 --time 19:13
#
# It installs uv if needed, downloads the app into ~/ASVZ-enrollment, asks for the SWITCH
# edu-ID login and the optional email settings, writes the .env file, tests the login and
# schedules scripts/enrol-weekly.sh with cron every week.
#
# Testing only (visitors never set these):
#   ASVZ_ZIP_URL             download the app from this URL instead of GitHub
#                            (the repository is private until it is made public)
#   ASVZ_SETUP_ANSWERS_FILE  read the answers from this file, one per line, instead of the
#                            terminal; the typing is then not hidden

set -eu

ZIP_URL="${ASVZ_ZIP_URL:-https://github.com/danyk20/ASVZ-enrollment/archive/refs/heads/main.zip}"
GUIDE_URL="https://github.com/danyk20/ASVZ-enrollment/blob/main/SETUP-GUIDE.md"

die() {
    printf '\nError: %s\n' "$1" >&2
    exit 1
}

warn() {
    printf '\nWarning: %s\n' "$1"
}

step() {
    printf '\n[%s/6] %s\n' "$1" "$2"
}

cleanup() {
    if [ "${ECHO_OFF:-0}" = 1 ]; then
        stty echo <&3 2>/dev/null || true
    fi
    if [ -n "${TMP_DIR:-}" ]; then
        rm -rf "$TMP_DIR"
    fi
}

# Reads one line of input for a question into ANSWER.
ask() {
    printf '%s' "$1"
    ANSWER=""
    if ! IFS= read -r ANSWER <&3; then
        printf '\n'
        die "No answer was given, so setup stopped. Run the command again in Terminal."
    fi
}

# Asks a yes/no question. $2 is the default, "y" or "n". Sets YES to 1 or 0.
ask_yes_no() {
    while :; do
        ask "$1 "
        if [ -z "$ANSWER" ]; then
            ANSWER="$2"
        fi
        case "$ANSWER" in
            y|Y|yes|Yes|YES)
                YES=1
                return 0
                ;;
            n|N|no|No|NO)
                YES=0
                return 0
                ;;
        esac
        printf 'Please answer y or n.\n'
    done
}

# Reads a line without showing it on screen. Sets ANSWER.
ask_secret() {
    if [ -n "${ASVZ_SETUP_ANSWERS_FILE:-}" ]; then
        ask "$1"
        return 0
    fi
    stty -echo <&3
    ECHO_OFF=1
    ask "$1"
    stty echo <&3
    ECHO_OFF=0
    printf '\n'
}

# Escapes a value for a double-quoted line in .env: backslash and double quote.
escape_value() {
    printf '%s' "$1" | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g'
}

# The whole line of the app's .env file that sets KEY, or nothing.
saved_line() {
    if [ -f "$APP_DIR/.env" ]; then
        grep "^$1=" "$APP_DIR/.env" | head -n 1 || true
    fi
}

# The value of KEY in the app's .env file, without the quotes. Empty if missing.
saved_value() {
    SAVED_RAW="$(saved_line "$1")"
    SAVED_RAW="${SAVED_RAW#*=}"
    SAVED_RAW="${SAVED_RAW#\"}"
    SAVED_RAW="${SAVED_RAW%\"}"
    printf '%s' "$SAVED_RAW"
}

open_answers() {
    if [ -n "${ASVZ_SETUP_ANSWERS_FILE:-}" ]; then
        # TESTING ONLY: answers come from a file instead of the terminal.
        [ -r "$ASVZ_SETUP_ANSWERS_FILE" ] || die "Cannot read $ASVZ_SETUP_ANSWERS_FILE."
        exec 3<"$ASVZ_SETUP_ANSWERS_FILE"
    else
        # The script itself arrives on standard input, so every question reads the terminal.
        if ! (exec 3</dev/tty) 2>/dev/null; then
            die "This setup asks questions, so it must run in Terminal. Paste the command into Terminal and press Enter."
        fi
        exec 3</dev/tty
    fi
}

check_system() {
    step 1 "Checking the lesson and your system..."

    case "$LESSON_ID" in
        ""|*[!0-9]*) die "The lesson id must be a number, like 777113." ;;
    esac
    case "$WEEKDAY" in
        [0-6]) ;;
        *) die "The weekday must be a number from 0 (Sunday) to 6 (Saturday)." ;;
    esac
    case "$TIME" in
        [0-2][0-9]:[0-5][0-9]) ;;
        *) die "The time must look like 19:13." ;;
    esac
    if [ "${TIME%%:*}" -gt 23 ]; then
        die "The time must look like 19:13, with an hour from 00 to 23."
    fi

    case "$(uname -s)" in
        Darwin) OS=macos ;;
        Linux) OS=linux ;;
        *) die "This command is for macOS and Linux. On Windows, use the PowerShell command." ;;
    esac

    if [ "$OS" = linux ]; then
        if ! command -v unzip >/dev/null 2>&1; then
            die "unzip is missing. Install it with: sudo apt install -y unzip   (Fedora: sudo dnf install -y unzip)"
        fi
        if ! command -v crontab >/dev/null 2>&1; then
            die "crontab is missing. Install cron with: sudo apt install -y cron   (Fedora: sudo dnf install -y cronie)"
        fi
    fi

    case "$WEEKDAY" in
        0) DAY_NAME=Sunday ;;
        1) DAY_NAME=Monday ;;
        2) DAY_NAME=Tuesday ;;
        3) DAY_NAME=Wednesday ;;
        4) DAY_NAME=Thursday ;;
        5) DAY_NAME=Friday ;;
        6) DAY_NAME=Saturday ;;
    esac
    printf 'Lesson %s, every %s at %s, on %s.\n' "$LESSON_ID" "$DAY_NAME" "$TIME" "$OS"
}

install_uv() {
    step 2 "Installing uv (the tool that runs the app) if needed..."
    if [ -x "$HOME/.local/bin/uv" ]; then
        UV="$HOME/.local/bin/uv"
    elif command -v uv >/dev/null 2>&1; then
        UV="$(command -v uv)"
    else
        curl -LsSf https://astral.sh/uv/install.sh -o "$TMP_DIR/uv-install.sh" \
            || die "Could not download the uv installer. Check your internet connection and try again."
        sh "$TMP_DIR/uv-install.sh" </dev/null || die "The uv installer failed. See the messages above."
        UV="$HOME/.local/bin/uv"
        [ -x "$UV" ] || die "uv was installed, but not to $UV."
    fi
    printf 'Using %s\n' "$UV"
}

download_app() {
    step 3 "Downloading the app to $APP_DIR..."
    curl -fsSL "$ZIP_URL" -o "$TMP_DIR/app.zip" \
        || die "Could not download the app. Check your internet connection and try again."
    mkdir "$TMP_DIR/unpacked"
    unzip -q "$TMP_DIR/app.zip" -d "$TMP_DIR/unpacked" || die "The download is not a valid ZIP file."
    NEW_APP="$TMP_DIR/unpacked/ASVZ-enrollment-main"
    [ -f "$NEW_APP/pyproject.toml" ] || die "The download does not contain the app."

    KEPT_ENV=0
    if [ -e "$APP_DIR" ]; then
        # Only ever replace a folder that this script installed: never a git checkout, and
        # never an unrelated folder that happens to have the same name.
        if [ -d "$APP_DIR/.git" ]; then
            die "$APP_DIR is a git checkout. Update it with 'git pull' instead, or move it away and run this again."
        fi
        if ! grep -q '^name = "asvz-enroll"' "$APP_DIR/pyproject.toml" 2>/dev/null; then
            die "$APP_DIR already exists but is not this app. Rename or move it, then run this again."
        fi
        printf 'The app folder already exists: updating it and keeping your .env file.\n'
        if [ -f "$APP_DIR/.env" ]; then
            cp -p "$APP_DIR/.env" "$TMP_DIR/saved.env"
            KEPT_ENV=1
        fi
        rm -rf "$APP_DIR"
    fi
    mv "$NEW_APP" "$APP_DIR"
    if [ "$KEPT_ENV" = 1 ]; then
        mv "$TMP_DIR/saved.env" "$APP_DIR/.env"
    fi
    printf 'App installed in %s\n' "$APP_DIR"
}

# Asks for the SWITCH edu-ID login and the password (twice). Sets LOGIN_USER and LOGIN_PASSWORD.
enter_login() {
    KEEP_LOGIN=0
    while :; do
        ask "SWITCH edu-ID login (your email address): "
        LOGIN_USER="$(printf '%s' "$ANSWER" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"
        if [ -n "$LOGIN_USER" ]; then
            break
        fi
        printf 'The login cannot be empty.\n'
    done
    while :; do
        ask_secret "Password (typed hidden): "
        LOGIN_PASSWORD="$ANSWER"
        ask_secret "Type the password again: "
        if [ -n "$LOGIN_PASSWORD" ] && [ "$LOGIN_PASSWORD" = "$ANSWER" ]; then
            break
        fi
        printf 'The two passwords do not match, or the password is empty. Try again.\n'
    done
    HAS_LOGIN=1
}

setup_login() {
    step 4 "Login and optional email..."

    KEEP_LOGIN=0
    HAS_LOGIN=0
    LOGIN_USER=""
    LOGIN_PASSWORD=""
    SAVED_USER="$(saved_value ASVZ_USERNAME)"
    if [ -n "$SAVED_USER" ]; then
        ask_yes_no "Keep the saved login for $SAVED_USER? [Y/n]" y
        if [ "$YES" = 1 ]; then
            KEEP_LOGIN=1
            HAS_LOGIN=1
            LOGIN_USER="$SAVED_USER"
            KEPT_USER_LINE="$(saved_line ASVZ_USERNAME)"
            KEPT_PASSWORD_LINE="$(saved_line ASVZ_PASSWORD)"
            if [ -z "$KEPT_PASSWORD_LINE" ]; then
                KEPT_PASSWORD_LINE='ASVZ_PASSWORD=""'
            fi
        fi
    fi
    if [ "$KEEP_LOGIN" = 0 ]; then
        ask_yes_no "Enter your SWITCH edu-ID login now? [Y/n]" y
        if [ "$YES" = 1 ]; then
            enter_login
        else
            printf 'You can add it later in %s/.env\n' "$APP_DIR"
        fi
    fi

    EMAIL_RECIPIENT=""
    BREVO_KEY=""
    BREVO_SENDER=""
    EMAIL_KEEP=0
    SAVED_EMAIL="$(saved_value ASVZ_EMAIL_RECIPIENT)"
    if [ -n "$SAVED_EMAIL" ]; then
        # Already set up: pressing Enter keeps the saved email settings unchanged.
        ask_yes_no "Keep the email after every attempt to $SAVED_EMAIL? [Y/n]" y
        if [ "$YES" = 1 ]; then
            EMAIL_KEEP=1
        fi
    else
        ask_yes_no "Get an email after every attempt? [y/N]" n
    fi
    if [ "$EMAIL_KEEP" = 0 ] && [ "$YES" = 1 ]; then
        printf 'Brevo steps: %s#email-after-every-attempt-optional\n' "$GUIDE_URL"
        while :; do
            if [ -n "$LOGIN_USER" ]; then
                ask "Send the emails to [$LOGIN_USER]: "
            else
                ask "Send the emails to: "
            fi
            if [ -n "$ANSWER" ]; then
                EMAIL_RECIPIENT="$ANSWER"
            else
                EMAIL_RECIPIENT="$LOGIN_USER"
            fi
            if [ -n "$EMAIL_RECIPIENT" ]; then
                break
            fi
            printf 'Please type an email address.\n'
        done
        while :; do
            ask_secret "Brevo API key (starts with xkeysib-): "
            BREVO_KEY="$ANSWER"
            if [ -n "$BREVO_KEY" ]; then
                break
            fi
            printf 'The API key cannot be empty.\n'
        done
        while :; do
            ask "Sender address (verified in Brevo): "
            BREVO_SENDER="$ANSWER"
            if [ -n "$BREVO_SENDER" ]; then
                break
            fi
            printf 'The sender address cannot be empty.\n'
        done
    fi

    write_env
    printf 'Settings written to %s/.env (readable only by you).\n' "$APP_DIR"
}

write_env() {
    if [ "$KEEP_LOGIN" = 1 ]; then
        USER_LINE="$KEPT_USER_LINE"
        PASSWORD_LINE="$KEPT_PASSWORD_LINE"
    else
        USER_LINE="ASVZ_USERNAME=\"$(escape_value "$LOGIN_USER")\""
        PASSWORD_LINE="ASVZ_PASSWORD=\"$(escape_value "$LOGIN_PASSWORD")\""
    fi
    EARLY_START="$(saved_value ASVZ_EARLY_START_MINUTES)"
    if [ "$EMAIL_KEEP" = 1 ]; then
        # The saved lines are copied as they are, so nothing is escaped twice.
        RECIPIENT_LINE="$(saved_line ASVZ_EMAIL_RECIPIENT)"
        BREVO_LINE="$(saved_line BREVO_API_KEY)"
        SENDER_LINE="$(saved_line BREVO_SENDER_EMAIL)"
        [ -n "$BREVO_LINE" ] || BREVO_LINE='BREVO_API_KEY=""'
        [ -n "$SENDER_LINE" ] || SENDER_LINE='BREVO_SENDER_EMAIL=""'
    else
        RECIPIENT_LINE="ASVZ_EMAIL_RECIPIENT=\"$(escape_value "$EMAIL_RECIPIENT")\""
        BREVO_LINE="BREVO_API_KEY=\"$(escape_value "$BREVO_KEY")\""
        SENDER_LINE="BREVO_SENDER_EMAIL=\"$(escape_value "$BREVO_SENDER")\""
    fi
    ENV_TMP="$TMP_DIR/env.new"

    (
        umask 077
        {
            printf '%s\n' "# Settings for asvz-enroll. Anything given on the command line wins over this file."
            printf '\n'
            printf '%s\n' "# Your SWITCH edu-ID login (an email address)"
            printf '%s\n' "$USER_LINE"
            printf '%s\n' "$PASSWORD_LINE"
            printf '\n'
            printf '%s\n' "# The number at the end of https://schalter.asvz.ch/tn/lessons/<number>"
            printf 'ASVZ_LESSON_ID="%s"\n' "$LESSON_ID"
            printf '\n'
            printf '%s\n' "# Optional: how many minutes before enrolment opens the app may be started."
            printf '%s\n' "# It logs in and waits. Started earlier than this, it stops with an error. Default: 10"
            printf 'ASVZ_EARLY_START_MINUTES="%s"\n' "$(escape_value "$EARLY_START")"
            printf '\n'
            printf '%s\n' "# Optional: email the result of every enrolment attempt (success or failure)."
            printf '%s\n' "# Leave ASVZ_EMAIL_RECIPIENT empty to send no email."
            printf '%s\n' "$RECIPIENT_LINE"
            printf '%s\n' "# From Brevo: \"SMTP & API\" -> \"API keys\" (starts with xkeysib-)"
            printf '%s\n' "$BREVO_LINE"
            printf '%s\n' "# An address listed under Brevo \"Senders, Domains & Dedicated IPs\" -> \"Senders\""
            printf '%s\n' "$SENDER_LINE"
        } > "$ENV_TMP"
    )
    mv "$ENV_TMP" "$APP_DIR/.env"
    chmod 600 "$APP_DIR/.env"
}

test_login() {
    step 5 "Testing the login..."
    if [ "$HAS_LOGIN" != 1 ]; then
        printf 'No login was entered, so there is nothing to test yet.\n'
        return 0
    fi
    while :; do
        if (cd "$APP_DIR" && "$UV" run asvz-enroll --check-login) </dev/null; then
            printf 'The login works.\n'
            return 0
        fi
        printf '\nThe login test failed. The message above says why.\n'
        ask_yes_no "Enter the login again? [Y/n]" y
        if [ "$YES" = 0 ]; then
            printf 'Continuing without a working login. Fix it later in %s/.env\n' "$APP_DIR"
            return 0
        fi
        enter_login
        write_env
        printf 'Settings written to %s/.env\n' "$APP_DIR"
    done
}

schedule_weekly() {
    step 6 "Scheduling the weekly run..."
    MINUTE="${TIME#*:}"
    HOUR="${TIME%%:*}"
    CRON_LINE="$MINUTE $HOUR * * $WEEKDAY sh \"\$HOME/ASVZ-enrollment/scripts/enrol-weekly.sh\" --lesson-id $LESSON_ID # asvz-enroll:$LESSON_ID"

    if [ "$OS" = macos ]; then
        printf 'macOS may ask whether Terminal may administer this computer. Click OK.\n'
    fi

    EXISTING_CRON="$(crontab -l 2>/dev/null || true)"
    CRON_TMP="$TMP_DIR/crontab.new"
    {
        if [ -n "$EXISTING_CRON" ]; then
            printf '%s\n' "$EXISTING_CRON" | grep -v "# asvz-enroll:$LESSON_ID\$" || true
        fi
        printf '%s\n' "$CRON_LINE"
    } > "$CRON_TMP"
    crontab "$CRON_TMP" || die "Could not install the weekly schedule. See the messages above."

    if [ "$OS" = linux ]; then
        running=0
        if command -v systemctl >/dev/null 2>&1; then
            if systemctl is-active --quiet cron 2>/dev/null || systemctl is-active --quiet crond 2>/dev/null; then
                running=1
            fi
        fi
        if [ "$running" = 0 ] && pgrep -x cron >/dev/null 2>&1; then
            running=1
        fi
        if [ "$running" = 0 ] && pgrep -x crond >/dev/null 2>&1; then
            running=1
        fi
        if [ "$running" = 0 ]; then
            warn "The cron service does not seem to be running, so the schedule will not fire. Start it with: sudo systemctl enable --now cron   (Fedora: crond)"
        fi
    fi
    printf 'Scheduled: %s\n' "$CRON_LINE"
}

show_summary() {
    LESSON_NAME="$(cd "$APP_DIR" && "$UV" run python -c "from asvz_enroll.lesson_api import get_lesson; l = get_lesson($LESSON_ID); print(l.sport_name + ': ' + l.title)" 2>/dev/null </dev/null || true)"

    printf '\n'
    if [ -n "$LESSON_NAME" ]; then
        printf 'Done. Every %s at %s your computer will enrol you in %s.\n' "$DAY_NAME" "$TIME" "$LESSON_NAME"
    else
        printf 'Done. Every %s at %s your computer will try to enrol you in lesson %s.\n' "$DAY_NAME" "$TIME" "$LESSON_ID"
    fi

    printf '\nThree things to remember:\n'
    printf '1. Keep the computer plugged in and awake at that time. macOS: System Settings > Battery > Options.\n'
    printf '   Linux: Settings > Power. Nothing happens in a week when the computer is asleep.\n'
    printf '2. Each run is logged to %s/asvz.log\n' "$HOME"
    printf '3. To remove the schedule, run crontab -e and delete the line ending in # asvz-enroll:%s\n' "$LESSON_ID"
}

check_timezone() {
    if [ "$OS" = macos ]; then
        ZONE="$(readlink /etc/localtime 2>/dev/null | sed -e 's#.*/zoneinfo/##' || true)"
    else
        ZONE="$(timedatectl show -p Timezone --value 2>/dev/null || true)"
    fi
    if [ "$ZONE" != "Europe/Zurich" ]; then
        warn "This computer's time zone is '${ZONE:-unknown}', not Europe/Zurich. The start time above is in Zurich time, so check the clock settings."
    fi
}

main() {
    if [ -z "${HOME:-}" ]; then
        die "HOME is not set."
    fi
    APP_DIR="$HOME/ASVZ-enrollment"
    TMP_DIR=""
    ECHO_OFF=0
    YES=0
    KEPT_USER_LINE=""
    KEPT_PASSWORD_LINE=""

    trap cleanup EXIT
    trap 'exit 1' HUP INT TERM

    LESSON_ID=""
    WEEKDAY=""
    TIME=""
    while [ $# -gt 0 ]; do
        case "$1" in
            --lesson-id)
                [ $# -ge 2 ] || die "--lesson-id needs a value."
                LESSON_ID="$2"
                shift 2
                ;;
            --weekday)
                [ $# -ge 2 ] || die "--weekday needs a value."
                WEEKDAY="$2"
                shift 2
                ;;
            --time)
                [ $# -ge 2 ] || die "--time needs a value."
                TIME="$2"
                shift 2
                ;;
            *)
                die "Unknown option: $1"
                ;;
        esac
    done
    if [ -z "$LESSON_ID" ] || [ -z "$WEEKDAY" ] || [ -z "$TIME" ]; then
        die "The command must give --lesson-id, --weekday and --time. Copy it again from the setup page."
    fi

    check_system
    open_answers
    TMP_DIR="$(mktemp -d)"
    install_uv
    download_app
    setup_login
    test_login
    schedule_weekly
    show_summary
    check_timezone
}

main "$@"
