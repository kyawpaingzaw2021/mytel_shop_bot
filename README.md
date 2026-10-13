# Mytel Data Shop Bot

Telegram bot for selling Mytel data packages with wallet system.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
alembic upgrade head
python seed.py
python main.py
