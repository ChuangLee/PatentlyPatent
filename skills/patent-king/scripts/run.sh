#!/usr/bin/env bash
# 简单 wrapper：转发参数到 pk CLI
set -euo pipefail
exec pk "$@"
