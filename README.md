# 🇺🇸 RCMaaS — Immigration Compliance Daily

**Automated US immigration compliance digest for HR teams.**  
Daily alerts from USCIS, DOL, ICE, State Dept, Federal Register.  
Plain English. Action items. Fully automated. $99/month per company.

---

## Architecture

```
sources.yaml        → What to monitor (11 sources)
scraper.py          → Fetches + deduplicates new items (SQLite)
summarizer.py       → Claude Haiku summarizes each item
formatter.py        → Jinja2 HTML email template
sender.py           → Beehiiv API delivery + Telegram alerts
pipeline.py         → Orchestrator (cron or --schedule mode)
landing_page.html   → Subscriber acquisition page
deploy.sh           → One-shot VPS deployment
```

---

## Quick Start

### 1. Clone & configure
```bash
git clone <your-repo> rcmaas && cd rcmaas
cp .env.example .env
nano .env   # fill in your keys
```

### 2. Install dependencies
```bash
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Test dry run
```bash
DRY_RUN=true python pipeline.py
# Check logs/rcmaas.log for output
# Check Telegram for your alert
```

### 4. Deploy to VPS
```bash
chmod +x deploy.sh
./deploy.sh
```

---

## Environment Variables

| Variable | Description | Example |
|---|---|---|
| `ANTHROPIC_API_KEY` | Your Anthropic API key | `sk-ant-...` |
| `CLAUDE_MODEL` | Model to use | `claude-haiku-4-5-20251001` |
| `TELEGRAM_BOT_TOKEN` | Bot token from @BotFather | `7123456789:AAF...` |
| `TELEGRAM_CHAT_ID` | Your personal chat ID | `123456789` |
| `BEEHIIV_API_KEY` | Beehiiv API key | `...` |
| `BEEHIIV_PUBLICATION_ID` | Publication ID from Beehiiv | `pub_...` |
| `STRIPE_SECRET_KEY` | Stripe secret key | `sk_live_...` |
| `DRY_RUN` | Safety flag — `true` = no emails sent | `true` |
| `MIN_QUALITY_SCORE` | Min score (1-10) before sending | `7` |
| `DIGEST_SEND_HOUR` | Hour to send (24h, local) | `7` |
| `TIMEZONE` | Your timezone | `America/Chicago` |

---

## Getting API Keys

### Anthropic (Claude)
1. Go to console.anthropic.com
2. API Keys → Create Key
3. Model: `claude-haiku-4-5-20251001` (cheapest, ~$0.25/1M tokens)

### Telegram Bot (your alerts)
1. Message @BotFather on Telegram
2. `/newbot` → follow prompts → get token
3. Start your bot, then: `https://api.telegram.org/bot<TOKEN>/getUpdates`
4. Copy the `chat.id` value

### Beehiiv (email delivery)
1. Sign up at beehiiv.com (free up to 2,500 subs)
2. Settings → API → Generate Key
3. Copy your Publication ID from the URL

### Stripe (payments)
1. Sign up at stripe.com
2. Developers → API Keys → Secret Key
3. Create a $99/month subscription Product
4. Share the payment link on your landing page

---

## Cost Estimate

At 100 subscribers, 20 items/day avg:
- Claude Haiku: ~20 items × 800 tokens × 30 days = ~480K tokens/month ≈ **$0.12/month**
- VPS (existing): **$0 additional**
- Beehiiv (free tier): **$0**
- Total infra cost: **< $5/month**
- Revenue at 100 subs: **$9,900/month**

---

## Monitoring

The pipeline sends you a Telegram message every run with:
- Items found and sent
- Quality score
- Active subscriber count  
- Any errors

Check logs anytime:
```bash
tail -f ~/rcmaas/logs/rcmaas.log
sudo systemctl status rcmaas
```

---

## Scaling to Other Niches

Once validated, clone to new niches by:
1. Copy `sources.yaml` → `sources_hipaa.yaml`
2. Update source URLs and tags
3. Update system prompt in `summarizer.py` for the new domain
4. Create new Beehiiv publication
5. Deploy as a second systemd service: `rcmaas-hipaa.service`

---

## Legal Disclaimer

This service aggregates publicly available regulatory information.
It is not legal advice. Include this disclaimer in every email digest.
