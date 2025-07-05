#!/bin/bash

set -u

export PYTHONPATH="$(dirname ${0})"

trap "kill -- -${BASHPID}" EXIT  # forces watchmedo to stop when this script ends

watchmedo shell-command --patterns='**/*.py' --recursive --command='killall -s KILL pyknic' &

while true; do
  pyknic -vv $@
  sleep 1
done
