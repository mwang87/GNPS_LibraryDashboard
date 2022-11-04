#!/bin/bash

source activate omnisci
export C_FORCE_ROOT="true"
# pip install reload

apt-get update
apt install -y nodejs npm
npm install nodemon -g

echo "Running Docker with reload with complex message"
# celery -A tasks worker -l info -c 1 -Q workerload --max-tasks-per-child 1 --loglevel INFO --beat
nodemon --watch ./tasks.py --exec "celery -A tasks worker -l info -c 1 -Q workerload --max-tasks-per-child 1 --loglevel INFO --beat"


# watchmedo  auto-restart -d . -p 'test.py' -- python test.py

# watchmedo auto-restart \
# --pattern="tasks.py" \
# --recursive -- \
# celery -A tasks worker -l info -c 1 -Q workerload --max-tasks-per-child 1 --loglevel INFO --beat

# set -o monitor

# sigint_handler()
# {
#   echo 'got the signal'
#   kill $PID
#   exit
# }

# trap sigint_handler SIGINT
# # trap sigint_handler SIGCHLD

# while true; do
#     python -t test.py &
#     PID=$!
#     echo 'here'
#     # inotifywait -e create,delete,modify app.py
#     change=$(inotifywait -mq test.py)
#     # while true; do
#     #   echo 'here2'
#     #   #sleep for 1 second
#     #   sleep 1
#     # done
#     kill $PID
# done