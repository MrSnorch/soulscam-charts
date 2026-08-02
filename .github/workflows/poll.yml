name: Soulscam Tracker Poll

on:
  workflow_dispatch:   # triggered manually, or by this workflow re-triggering itself
  schedule:
    - cron: '*/30 * * * *'   # safety net in case the self-retrigger chain ever breaks

concurrency:
  group: poll-steam-players
  cancel-in-progress: false

jobs:
  poll:
    runs-on: ubuntu-latest
    timeout-minutes: 350   # stay under GitHub's 360-minute (6h) job limit
    permissions:
      contents: write

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.x'

      - name: Poll Steam API for ~5.5 hours, committing each hourly flush
        run: |
          python3 -u scripts/poll.py &
          POLL_PID=$!

          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"

          # Commit new hourly files every few minutes while poll.py runs in the background.
          while kill -0 $POLL_PID 2>/dev/null; do
            sleep 300
            python3 scripts/build-index.py
            git add docs/hourly/ docs/recent.json docs/points.json
            git diff --cached --quiet || git commit -m "chore: player count $(date -u +'%Y-%m-%dT%H:%M')"
            git pull --rebase --quiet || true
            git push --quiet || true
          done

          wait $POLL_PID

          # Rebuild the dashboard's aggregate and commit anything flushed at the end.
          python3 scripts/build-index.py
          git add docs/hourly/ docs/recent.json docs/points.json
          git diff --cached --quiet || git commit -m "chore: player count $(date -u +'%Y-%m-%dT%H:%M') (final)"
          git pull --rebase --quiet || true
          git push --quiet || true

      - name: Re-trigger this workflow to keep polling
        if: always()
        run: |
          curl -f -X POST \
            -H "Authorization: Bearer ${{ secrets.GH_PAT }}" \
            -H "Accept: application/vnd.github+json" \
            https://api.github.com/repos/${{ github.repository }}/actions/workflows/poll.yml/dispatches \
            -d '{"ref":"${{ github.ref_name }}"}'
