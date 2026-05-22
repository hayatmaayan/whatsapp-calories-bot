from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from openai import OpenAI
import os, json, sqlite3
from datetime import datetime

app = Flask(__name__)
client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
DB = "calories.db"

def init_db():
    conn = sqlite3.connect(DB)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS meals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            day TEXT,
            time TEXT,
            sender TEXT,
            item TEXT,
            calories INTEGER
        )
    """)
    conn.commit()
    conn.close()

def today():
    return datetime.now().strftime("%Y-%m-%d")

def save_items(sender, items):
    conn = sqlite3.connect(DB)
    for x in items:
        conn.execute(
            "INSERT INTO meals (day, time, sender, item, calories) VALUES (?, ?, ?, ?, ?)",
            (today(), datetime.now().strftime("%H:%M"), sender, x["item"], int(x["calories"]))
        )
    conn.commit()
    conn.close()

def daily_total(sender):
    conn = sqlite3.connect(DB)
    total = conn.execute(
        "SELECT COALESCE(SUM(calories),0) FROM meals WHERE day=? AND sender=?",
        (today(), sender)
    ).fetchone()[0]
    conn.close()
    return total

def reset_today(sender):
    conn = sqlite3.connect(DB)
    conn.execute("DELETE FROM meals WHERE day=? AND sender=?", (today(), sender))
    conn.commit()
    conn.close()

@app.route("/")
def home():
    init_db()
    return "Bot Running"

@app.route("/whatsapp", methods=["POST"])
def whatsapp():
    init_db()

    msg = request.form.get("Body", "").strip()
    sender = request.form.get("From", "")

    if msg.upper() == "RESET":
        reset_today(sender)
        reply = "✅ היום אופס בהצלחה\nסה״כ היום: 0 קלוריות"
    else:
        prompt = f"""
אתה בוט קלוריות בעברית.

המשתמש כתב:
{msg}

החזר JSON בלבד בפורמט:
{{
  "items": [
    {{"item": "שם מוצר וכמות", "calories": מספר}}
  ]
}}

חוקים:
1. אם המשתמש כתב קלוריות מדויקות, השתמש בהן בדיוק.
2. אם לא נכתבו קלוריות מדויקות, הערך קלוריות והוסף 3%-5% מרווח ביטחון.
3. אל תוסיף טקסט מחוץ ל-JSON.
"""

        ai = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )

        data = json.loads(ai.choices[0].message.content)
        items = data["items"]

        save_items(sender, items)
        total = daily_total(sender)

        lines = ["נרשם ✅", ""]
        for x in items:
            lines.append(f'{x["item"]} - {x["calories"]} קל׳')

        lines.append("")
        lines.append(f"סה״כ יומי עד כה: {total} קלוריות")
        reply = "\n".join(lines)

    twilio_response = MessagingResponse()
    twilio_response.message(reply)
    return str(twilio_response)

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000)
