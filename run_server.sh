#!/bin/bash

#python ./app.py
gunicorn -w 4 -b 0.0.0.0:5000 --timeout 3600 app:server --access-logfile /app/logs/access.log
