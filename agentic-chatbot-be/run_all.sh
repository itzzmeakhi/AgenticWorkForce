#!/usr/bin/env bash
# Starts both backend services in this one terminal. Stop both with Ctrl+C.
#   Usage: ./run_all.sh

cd "$(dirname "$0")"          # run from this folder
source venv/bin/activate      # use the project's virtual environment

# Stop both services when the script exits (Ctrl+C)
trap 'kill $(jobs -p)' EXIT

# 1) Fulfillment API (orders, products) on port 8010
python -m uvicorn fulfillment_api.server:app --port 8010 &

# 2) Agent API (chat) on port 8000
python -m uvicorn api.main:app --port 8000 &

wait                          # keep running until Ctrl+C
