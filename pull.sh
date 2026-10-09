#!/usr/bin/env bash
# Pull the latest changes from GitHub (the upstream branch tracked by the current local branch).
set -euo pipefail
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
git pull --ff-only "$@"
