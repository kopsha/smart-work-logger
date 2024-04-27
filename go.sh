#!/usr/bin/env bash
set -o allexport
source .env
set +o allexport

if [[ -n "$VIRTUAL_ENV" ]]; then
    module=${1:-}; shift
    python3 -m ${module} $*
else
    echo "ERROR: Please activate the virtual environment first."
fi

