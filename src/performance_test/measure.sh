#!/usr/bin/env bash

COWS_COUNT=$1
DURATION=${DURATION:-180}
INTERVAL=1

# --------- krowy (STADO) ---------
COW_CPU_SUM=0
COW_CPU_MAX=0
COW_MEM_SUM=0
COW_MEM_MAX=0
COW_SECONDS=0

# --------- xmpp ---------
XMPP_CPU_SUM=0
XMPP_CPU_MAX=0
XMPP_MEM_SUM=0
XMPP_MEM_MAX=0
XMPP_SECONDS=0

END=$((SECONDS + DURATION))

while [ $SECONDS -lt $END ]; do

  # suma w TEJ sekundzie
  COW_CPU_SEC=0
  COW_MEM_SEC=0
  XMPP_CPU_SEC=0
  XMPP_MEM_SEC=0

  while IFS=',' read -r NAME CPU MEM; do

    CPU_VAL=${CPU%\%}
    MEM_RAW=$(echo "$MEM" | awk '{print $1}')

    if [[ "$MEM_RAW" == *KiB ]]; then
      MEM_MB=$(echo "scale=4; ${MEM_RAW%KiB} / 1024" | bc)
    elif [[ "$MEM_RAW" == *MiB ]]; then
      MEM_MB=$(echo "scale=4; ${MEM_RAW%MiB}" | bc)
    elif [[ "$MEM_RAW" == *GiB ]]; then
      MEM_MB=$(echo "scale=4; ${MEM_RAW%GiB} * 1024" | bc)
    else
      continue
    fi

    if [[ "$NAME" == *cow* ]] && [[ "$NAME" != *cow_analyzer* ]]; then
      COW_CPU_SEC=$(echo "$COW_CPU_SEC + $CPU_VAL" | bc)
      COW_MEM_SEC=$(echo "$COW_MEM_SEC + $MEM_MB" | bc)

    elif [[ "$NAME" == *xmpp_server* ]]; then
      XMPP_CPU_SEC=$(echo "$XMPP_CPU_SEC + $CPU_VAL" | bc)
      XMPP_MEM_SEC=$(echo "$XMPP_MEM_SEC + $MEM_MB" | bc)
    fi

  done < <(
    docker stats --no-stream \
      --format "{{.Name}},{{.CPUPerc}},{{.MemUsage}}"
  )

  # --- krowy ---
  COW_CPU_SUM=$(echo "$COW_CPU_SUM + $COW_CPU_SEC" | bc)
  COW_MEM_SUM=$(echo "$COW_MEM_SUM + $COW_MEM_SEC" | bc)
  ((COW_SECONDS++))

  (( $(echo "$COW_CPU_SEC > $COW_CPU_MAX" | bc -l) )) && COW_CPU_MAX=$COW_CPU_SEC
  (( $(echo "$COW_MEM_SEC > $COW_MEM_MAX" | bc -l) )) && COW_MEM_MAX=$COW_MEM_SEC

  # --- xmpp ---
  XMPP_CPU_SUM=$(echo "$XMPP_CPU_SUM + $XMPP_CPU_SEC" | bc)
  XMPP_MEM_SUM=$(echo "$XMPP_MEM_SUM + $XMPP_MEM_SEC" | bc)
  ((XMPP_SECONDS++))

  (( $(echo "$XMPP_CPU_SEC > $XMPP_CPU_MAX" | bc -l) )) && XMPP_CPU_MAX=$XMPP_CPU_SEC
  (( $(echo "$XMPP_MEM_SEC > $XMPP_MEM_MAX" | bc -l) )) && XMPP_MEM_MAX=$XMPP_MEM_SEC

  sleep $INTERVAL
done

# --------- średnie ---------
COW_CPU_AVG=$(echo "scale=2; $COW_CPU_SUM / $COW_SECONDS" | bc)
COW_MEM_AVG=$(echo "scale=2; $COW_MEM_SUM / $COW_SECONDS" | bc)

XMPP_CPU_AVG=$(echo "scale=2; $XMPP_CPU_SUM / $XMPP_SECONDS" | bc)
XMPP_MEM_AVG=$(echo "scale=2; $XMPP_MEM_SUM / $XMPP_SECONDS" | bc)

# --------- zapis ---------
OUT="data/summary.csv"
mkdir -p data

if [ ! -f "$OUT" ]; then
  echo "cows_count,group,cpu_avg,cpu_max,ram_avg,ram_max" > "$OUT"
fi

echo "$COWS_COUNT,cows,$COW_CPU_AVG,$COW_CPU_MAX,$COW_MEM_AVG,$COW_MEM_MAX" >> "$OUT"
echo "$COWS_COUNT,xmpp,$XMPP_CPU_AVG,$XMPP_CPU_MAX,$XMPP_MEM_AVG,$XMPP_MEM_MAX" >> "$OUT"
