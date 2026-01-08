#!/bin/bash
set -e

REPO="AgentMatthy/AI-Shell"
echo "🔍 Looking for the latest release of $REPO..."

# fetching the latest release data from GitHub API
LATEST_RELEASE_JSON=$(curl -s "https://api.github.com/repos/$REPO/releases/latest")

# Check if we got a valid response
if echo "$LATEST_RELEASE_JSON" | grep -q "message.*Not Found"; then
    echo "❌ Error: Could not find any releases for $REPO."
    echo "   Ensure you have created a Release on GitHub and uploaded the .whl file."
    exit 1
fi

# Extract the download URL for the .whl file using Python (reliable standard tool)
DOWNLOAD_URL=$(echo "$LATEST_RELEASE_JSON" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    assets = data.get('assets', [])
    # Find the first asset ending in .whl
    whl_url = next((a['browser_download_url'] for a in assets if a['name'].endswith('.whl')), None)
    if whl_url:
        print(whl_url)
    else:
        sys.exit(1)
except Exception:
    sys.exit(1)
")

if [ -z "$DOWNLOAD_URL" ]; then
    echo "❌ Error: Could not find a .whl file in the latest release."
    echo "   Make sure you attached the binary (dist/ai_shell-*-py3-none-any.whl) to the GitHub Release."
    exit 1
fi

echo "⬇️  Found latest release asset: $DOWNLOAD_URL"

# Check if pipx is installed
if ! command -v pipx &> /dev/null; then
    echo "⚠️  pipx is not installed."
    echo "   Please install it first using your package manager (e.g., 'pacman -S python-pipx' on Manjaro)."
    exit 1
fi

echo "🚀 Installing with pipx..."
pipx install "$DOWNLOAD_URL" --force

echo ""
echo "✅ AI-Shell has been successfully installed/updated!"
echo "   Run it with: ai-shell"
