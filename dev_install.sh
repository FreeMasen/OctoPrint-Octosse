#! /bin/bash

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

rm -f "$HOME/.octoprint/plugins/octosse.py"
ln "$SCRIPT_DIR/octoprint_octosse/__init__.py" "$HOME/.octoprint/plugins/octosse.py"
