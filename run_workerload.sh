#!/bin/bash

source activate omnisci
celery -A tasks worker -l info -c 1 -Q workerload --max-tasks-per-child 1 --loglevel INFO

