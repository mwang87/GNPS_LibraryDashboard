#!/bin/bash

source activate omnisci
export C_FORCE_ROOT="true"
echo "Running Docker with reload"

apt-get update
apt install -y nodejs npm
npm install nodemon -g

nodemon --watch ./tasks.py --exec "celery -A tasks worker -l info --autoscale=4,1 -Q worker --max-tasks-per-child 2 --loglevel INFO"