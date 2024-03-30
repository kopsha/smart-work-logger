#!/usr/bin/env bash
set -o allexport
source .env
set +o allexport

if [[ -n "$VIRTUAL_ENV" ]]; then
    python3 -m user_reports $*
else
    echo "ERROR: Please activate the virtual environment first."
fi

