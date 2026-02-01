#!/usr/bin/env bash
set -e

COWS_LIST=(10 25 50 75 100)


WARMUP=60
MEASURE=120

for N in "${COWS_LIST[@]}"; do
  echo "=============================="
  echo " Benchmark: $N krów"
  echo "=============================="

  docker compose down -v

  docker compose up -d --scale cow=$N

  echo "Warm-up (${WARMUP}s)..."
  sleep $WARMUP

  echo "Pomiar (${MEASURE}s)..."
  DURATION=$MEASURE ./measure.sh $N

  docker compose down -v
done

echo "Benchmark zakończony"
