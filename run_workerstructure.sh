#!/bin/bash

source activate rdkit
export C_FORCE_ROOT="true"
celery -A tasks worker -l info --autoscale=4,1 -Q workerstructure --max-tasks-per-child 10 --loglevel INFO

