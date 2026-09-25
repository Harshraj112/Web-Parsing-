# Web Parsing Job Alerts

This project scrapes Indian jobs, stores the queue in `output/india_jobs.json`, and sends the next batch of jobs to WhatsApp or Telegram through a FastAPI notification service.

## Project structure

- `scrape_india_jobs.py` — scraper and queue generation
- `output/india_jobs.json` — job queue used by the notification API
- `output/india_jobs.csv` — CSV export of scraped jobs
- `notification-service/main.py` — FastAPI notification API
- `notification-service/services/` — Telegram and WhatsApp senders

## Local usage

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Start the notification API:
   ```bash
   cd notification-service
   uvicorn main:app --host 0.0.0.0 --port 8001
   ```
3. Trigger the next 5 jobs from the queue:
   ```bash
   curl -X POST "http://localhost:8001/api/notifications/send-jobs" \
     -H "Content-Type: application/json" \
     -d '{"channel":"whatsapp","recipient":"918090519139"}'
   ```

## Render deployment

Use a Python Web Service and set the start command:

```bash
cd notification-service && uvicorn main:app --host 0.0.0.0 --port $PORT
```

Add these environment variables in Render:

- `TELEGRAM_BOT_TOKEN`
- `WHATSAPP_ACCESS_TOKEN`
- `WHATSAPP_PHONE_NUMBER_ID`
- `WHATSAPP_GRAPH_API_VERSION`

The `output/` directory is intentionally kept in git so the API can read and consume the queued jobs.
