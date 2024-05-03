#!/bin/sh

python /app/init_db.py

flask run --host=0.0.0.0 --port=8080
