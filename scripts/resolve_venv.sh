#!/usr/bin/env bash

set -e

if [[ -z $VIRTUAL_ENV && -f .venv/bin/activate ]]; then
    source .venv/bin/activate
fi

$@
