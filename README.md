🔥 Client Hunter — Automated Lead Generation System
<!-- Badges --> <p align="center"> <img src="https://img.shields.io/badge/Python-3.10%2B-blue" /> <img src="https://img.shields.io/badge/Flask-API%20Backend-black" /> <img src="https://img.shields.io/badge/Playwright-Scraping-green" /> <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" /></a> <img src="https://img.shields.io/badge/Contributions-Welcome-brightgreen" /> <img src="https://img.shields.io/github/issues/your-username/client-hunter" /> <img src="https://img.shields.io/github/stars/your-username/client-hunter?style=social" /> <img src="https://img.shields.io/github/last-commit/your-username/client-hunter" /> </p>
🚀 Overview

Client Hunter is an automated lead-generation and outreach system designed for freelancers, agencies, and businesses that want to scale client acquisition without manual effort.

It performs everything end-to-end:

✔ Lead Scraping

Scrapes business categories (mobile repair, salons, gyms, etc.) using:

Google Maps (Playwright-powered)

(soon) Google Places API + custom ML ranking

✔ Lead Intelligence

Each lead is analyzed with:

Website presence detection

Broken / free-host website scoring

Business category matching

Priority scoring (100 = hot lead)

✔ Automated Outreach

Client Hunter auto-sends:

Email outreach

WhatsApp outreach

Custom AI-generated messages based on category + lead status

✔ Dashboard

A clean built-in dashboard to view:

Leads

Status

Priority

Message history

🧰 Tech Stack
Component	Technology
Backend	Flask
Scraper	Playwright (headless browser scraping)
Database	SQLite (default)
Scheduler	APScheduler
Messaging	Email (SMTP), WhatsApp (Twilio or custom sender)
AI Messaging	Custom template generator
📦 Features
🔎 Lead Scraping

Searches Google Maps using category + city

Extracts business name, address, phone, website

Scores leads automatically

🤖 Auto Messaging

Sends personalized outreach messages

Avoids duplicates

Enforces cool-down period

🧠 Smart Scoring

100: No website

95: Broken website

90: Free-host website

Rejects fully professional sites

📊 Dashboard

Shows all leads in an organized UI.

🛠 Installation
git clone https://github.com/fkkhan19/client-hunter
cd client-hunter
pip install -r requirements.txt
playwright install

▶️ Running The App
python run.py


This will:

Start the Flask backend

Start the APScheduler

Launch scraping jobs in a separate Playwright process

🤝 Contributing

Contributions are welcome!
You can help by:

Improving the scraper

Adding browserless scraping upgrades

Improving UI/UX of dashboard

Integrating Google Places API

Optimizing performance

Just open a Pull Request 😄

📄 License

MIT — free to use, modify, and distribute.


