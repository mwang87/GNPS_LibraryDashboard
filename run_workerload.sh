#!/bin/bash

source activate omnisci
export C_FORCE_ROOT="true"
celery -A tasks worker -l info -c 1 -Q workerload --max-tasks-per-child 1 --loglevel INFO --beat

