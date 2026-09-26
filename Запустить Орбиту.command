#!/bin/bash
cd -- "$(dirname -- "$0")"
./run.sh "$@"
status=$?
if [ "$status" -ne 0 ]; then
  echo "Не удалось запустить приложение. Подробности выше."
  read -r -p "Нажмите Enter, чтобы закрыть окно…"
fi
exit "$status"
