#!/bin/bash
# Loads the project's .env into the environment exactly like thoughtlab.app.load_env (nothing is printed), then runs the runner.
exec python3 - "$@" <<'PY'
import os, sys
path = "/path/to/project/AIScientist-scholareval/.env"
for line in open(path).read().splitlines():
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.split(" #")[0].strip().strip("'\""))
script = "/path/to/scripts/run_lane.sh"
os.execv("/bin/bash", ["bash", script, *sys.argv[1:]])
PY
