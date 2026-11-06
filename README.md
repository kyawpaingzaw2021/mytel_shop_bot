# Myanmar Operator Bot

Telegram bot for selling Data, SIM, MLBB, PUBG with wallet system.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# .env ကို ဖွင့်ပြီး ဖြည့်ပါ
alembic upgrade head
python seed.py
python main.py
