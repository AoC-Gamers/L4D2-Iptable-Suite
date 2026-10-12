#!/bin/bash
# Configuration is declarative and resolved in core/config.py.
run_preload() {
    echo "ERROR: shell preload retired; use the suite entrypoints" >&2
    return 2
}
