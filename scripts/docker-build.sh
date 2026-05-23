#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/_lib.sh"

MODULE=${1:?Usage: docker-build.sh <module> [tag]}
TAG=${2:-latest}

if [ "$MODULE" = "all" ]; then
    for m in $AVAILABLE_MODULES; do
        [ "$m" = "all" ] && continue
        script="./docker/build_$m.sh"
        if [ -f "$script" ]; then
            echo "Running $script -t $TAG"
            bash "$script" -t "$TAG"
        else
            echo "Warning: Build script $script not found."
        fi
    done
else
    target=$(resolve_module "$MODULE")
    script="./docker/build_$target.sh"
    if [ -f "$script" ]; then
        bash "$script" -t "$TAG"
    else
        echo "Error: Build script $script not found."
        echo "Available modules are: $AVAILABLE_MODULES"
        exit 1
    fi
fi
