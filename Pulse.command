#!/bin/zsh
PULSE_DIRECTORY="${0:A:h}"
for PULSE_INTERPRETER in "${PULSE_PYTHON:-}" "$PULSE_DIRECTORY/.venv/bin/python" /Library/Frameworks/Python.framework/Versions/3.10/bin/python3 python3; do
  [[ -n "$PULSE_INTERPRETER" ]] || continue
  if "$PULSE_INTERPRETER" -c 'import numpy' >/dev/null 2>&1; then
    "$PULSE_INTERPRETER" "$PULSE_DIRECTORY/scripts/build_native.py" --quiet >/dev/null 2>&1
    export PYTHONPATH="$PULSE_DIRECTORY/src${PYTHONPATH:+:$PYTHONPATH}"
    exec "$PULSE_INTERPRETER" -m pulse_tui "$@"
  fi
done
print -u2 'Pulse needs Python 3.10+ and NumPy. Install with: python3 -m pip install numpy'
exit 1
