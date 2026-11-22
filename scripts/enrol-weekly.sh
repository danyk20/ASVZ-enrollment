#!/bin/sh
# Starts asvz-enroll and writes everything it prints to ~/asvz.log.
# Meant to be run by cron on macOS and Linux, see SETUP-GUIDE.md.
#
# Usage:  sh ~/ASVZ-enrollment/scripts/enrol-weekly.sh --lesson-id 777113
# Any options are passed on to asvz-enroll unchanged.

project_folder="$(cd "$(dirname "$0")/.." && pwd)"
log_file="$HOME/asvz.log"

# cron starts programs with an almost empty PATH, so look for uv where its installers put it.
uv=""
for candidate in "$HOME/.local/bin/uv" "$HOME/.cargo/bin/uv" /opt/homebrew/bin/uv /usr/local/bin/uv; do
    if [ -x "$candidate" ]; then
        uv="$candidate"
        break
    fi
done

{
    echo "===== $(date) ====="
    if [ -z "$uv" ]; then
        echo "Error: uv was not found. Install it as described in SETUP-GUIDE.md."
        exit 1
    fi
    cd "$project_folder" || exit 1
    "$uv" run asvz-enroll "$@"
} >> "$log_file" 2>&1
