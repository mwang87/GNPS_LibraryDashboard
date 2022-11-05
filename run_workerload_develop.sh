#!/bin/bash

source activate omnisci
export C_FORCE_ROOT="true"

# Installing node, npm, and nodmon for reload on save
# This installation increases the initialization time
# Remove this part and run the command directly if not convinient
apt-get update
apt install -y nodejs npm
npm install nodemon -g

nodemon --watch ./tasks.py --exec "celery -A tasks worker -l info -c 1 -Q workerload --max-tasks-per-child 1 --loglevel INFO --beat"
