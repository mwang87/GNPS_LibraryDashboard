#!/bin/bash

source activate rdkit
celery -A tasks worker -l info -c 1 -Q workerstructure --max-tasks-per-child 1000 --loglevel INFO

