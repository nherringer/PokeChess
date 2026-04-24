#!/usr/bin/env bash
# Local dev launcher: stops local postgres, starts Docker postgres, then opens
# iTerm2 tabs for the app server and frontend dev server.

set -e

REPO="$(cd "$(dirname "$0")/.." && pwd)"

# ── 1. Open Docker Desktop and wait for the daemon ───────────────────────────
echo "Starting Docker Desktop..."
open -a Docker
echo -n "Waiting for Docker daemon"
until docker info &>/dev/null 2>&1; do
    echo -n "."
    sleep 2
done
echo " ready."

# ── 2. Stop local Homebrew postgres to free port 5432 ────────────────────────
echo "Stopping local postgres (freeing port 5432)..."
brew services stop postgresql@18 2>/dev/null || true

# ── 3. Start Docker postgres and apply schema ─────────────────────────────────
echo "Running make partial..."
make -C "$REPO" partial 2>&1 | grep -v "already exists"

# ── 4 & 5. Open iTerm2 tabs for app and frontend ─────────────────────────────
echo "Opening iTerm2 tabs..."
osascript <<EOF
tell application "iTerm2"
    activate
    tell current window
        create tab with default profile
        tell current session of current tab
            write text "cd '$REPO' && make app"
        end tell
        create tab with default profile
        tell current session of current tab
            write text "cd '$REPO' && source ~/.nvm/nvm.sh && nvm use 20 && make frontend"
        end tell
    end tell
end tell
EOF

echo "Done! App and frontend tabs opened."
