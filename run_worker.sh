#!/bin/bash

source activate omnisci
export C_FORCE_ROOT="true"
celery -A tasks worker -l info --autoscale=2,1 -Q worker --max-tasks-per-child 2 --loglevel INFO

