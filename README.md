# ROE Player Count Tracker

Отслеживает онлайн игроков Roots of Embervault (appid 4369490) через Steam API.

## Как это работает

- `docs/steamdb_snapshot.json` — снимок пиков со SteamDB
  (https://steamdb.info/app/4369490/charts/), обновляется автоматически
  скриптом `scripts/update_snapshot.py` в конце каждого запуска `poll.py`.
  `peak_players_24h` берётся из последнего запроса; `peak_players_all_time`
  накапливается как max(старое значение, новое из API), так как SteamDB
  отдаёт максимум только за последние ~8 дней, а не за всё время.
- `scripts/poll.py` — опрашивает
  `GetNumberOfCurrentPlayers` раз в минуту и раз в час пишет
  `docs/hourly/YYYY-MM-DDTHH.json.gz` с массивом точек `{ts, player_count}`.
  Один запуск длится ~5.5 часа (лимит GitHub Actions на job — 6 часов).
- `.github/workflows/poll.yml` — запускает `poll.py`, каждые 5 минут
  пересобирает `docs/recent.json` (через `build-index.py`) и коммитит новые
  файлы, а в конце запуска сам себя перезапускает через `workflow_dispatch`
  API. Плюс cron каждые 6 часов как страховка, если цепочка самозапуска
  когда-нибудь порвётся (сбой, ручная отмена и т.д.).
- `scripts/build-index.py` — сворачивает все `docs/hourly/*.json.gz` в один
  лёгкий `docs/recent.json` (avg/max/min по часам), который читает дашборд.
- `docs/index.html` — дашборд на GitHub Pages: текущий онлайн, пик за 24ч,
  пик all-time (из `steamdb_snapshot.json`), общий график по всей истории и
  сравнение любых двух дней по часам (0–23) для оценки тенденции.

## Включение GitHub Pages

Settings → Pages → Source: Deploy from a branch → `main` / `/docs`.
Дашборд появится на `https://<ваш-юзер>.github.io/<репозиторий>/`.

## Первый запуск

1. Запушьте репозиторий на GitHub.
2. Вручную запустите workflow "Poll Steam Player Count" (Actions → Run workflow)
   один раз — дальше он будет перезапускать себя сам. `docs/steamdb_snapshot.json`
   обновится сам после первого запуска.

## Локальный тест

```bash
RUN_DURATION_SEC=10 python3 scripts/poll.py
```
