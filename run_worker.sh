#!/bin/bash

source activate omnisci
celery -A tasks worker -l info --autoscale=4,1 -Q worker --max-tasks-per-child 2 --loglevel INFO

