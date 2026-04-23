#!/usr/bin/env bash
# Build LogGOPSim from the source shipped under tools/LogGOPSim/.
# Idempotent: skips compilation if the binary is already present.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
LGS_DIR="$ROOT/tools/LogGOPSim"

if [ ! -d "$LGS_DIR" ]; then
    echo "error: $LGS_DIR not found" >&2
    exit 1
fi

if [ -x "$LGS_DIR/LogGOPSim" ] && [ -x "$LGS_DIR/txt2bin" ]; then
    echo "[build_tools] LogGOPSim and txt2bin already built."
    exit 0
fi

# Check build prerequisites
for prog in g++ gengetopt re2c; do
    if ! command -v "$prog" >/dev/null 2>&1; then
        echo "error: '$prog' is required to build LogGOPSim. Install with apt-get install g++ gengetopt re2c" >&2
        exit 2
    fi
done

echo "[build_tools] Building LogGOPSim in $LGS_DIR"
(cd "$LGS_DIR" && make -j"$(nproc)")
echo "[build_tools] Built binaries:"
ls -la "$LGS_DIR/LogGOPSim" "$LGS_DIR/txt2bin"
