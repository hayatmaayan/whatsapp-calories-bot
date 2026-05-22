from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from openai import OpenAI
import os, json, sqlite3
from datetime import datetime

app = Flask(__name__)
DB = "calories.db"
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

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

def now_time():
    return datetime.now().strftime("%H:%M")

def save_items(sender, items):
    conn = sqlite3.connect(DB)
    for x in items:
        conn.execute(
            "INSERT INTO meals (day, time, sender, item, calories) VALUES (?, ?, ?, ?, ?)",
            (today(), now_time(), sender, x["item"], int(x["calories"]))
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

def daily_summary(sender):
    conn = sqlite3.connect(DB)
    rows = conn.execute(
        "SELECT time, item, calories FROM meals WHERE day=? AND sender=? ORDER BY id",
        (today(), sender)
    ).fetchall()
    conn.close()
    return rows

def reset_today(sender):
    conn = sqlite3.connect(DB)
    conn.execute("DELETE FROM meals WHERE day=? AND sender=?", (today(), sender))
    conn.commit()
    conn.close()

def openai_parse(msg):
    prompt = f"""
אתה בוט קלוריות בעברית.

המשתמש כתב:
{msg}

החזר JSON בלבד בפורמט:
{{
  "items": [
    {{"item": "שם מוצר וכמות", "calories": 100}}
  ]
}}

חוקים:
1. אם המשתמש כתב קלוריות מדויקות, השתמש בהן בדיוק.
2. אם לא נכתבו קלוריות מדויקות, הערך קלוריות והוסף 3%-5% מרווח ביטחון.
3. אם יש כמה מוצרים, פצל למוצרים נפרדים.
4. אם ההודעה לא קשורה לאוכל, החזר items ריק.
5. calories חייב להיות מספר שלם בלבד.
6. אל תחזיר טקסט מחוץ ל-JSON.
"""

    ai = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )

    raw = ai.choices[0].message.content.strip()
    raw = raw.replace("```json", "").replace("```", "").strip()
    return json.loads(raw).get("items", [])

@app.route("/")
def home():
    init_db()
    return "Bot Running"

@app.route("/whatsapp", methods=["POST"])
def whatsapp():
    init_db()

    msg = request.form.get("Body", "").strip()
    sender = request.form.get("From", "")
    command = msg.upper()

    try:
        if command == "RESET":
            reset_today(sender)
            reply = "✅ היום אופס בהצלחה\nסה״כ היום: 0 קלוריות"

        elif command in ["TOTAL", "סהכ", "סה״כ"]:
            reply = f"סה״כ יומי עד כה: {daily_total(sender)} קלוריות"

        elif command in ["SUMMARY", "סיכום"]:
            rows = daily_summary(sender)

            if not rows:
                reply = "אין עדיין פריטים שנרשמו היום."
            else:
                lines = ["📊 סיכום יומי", ""]
                for time, item, calories in rows:
                    lines.append(f"{time} | {item} - {calories} קל׳")
                lines.append("")
                lines.append(f"סה״כ היום: {daily_total(sender)} קלוריות")
                reply = "\n".join(lines)

        else:
            items = openai_parse(msg)

            if not items:
                reply = "לא זיהיתי אוכל 😕\nכתבי למשל: אכלתי ביצה ופרוסת לחם"
            else:
                save_items(sender, items)
                total = daily_total(sender)

                lines = ["נרשם ✅", ""]
                for x in items:
                    lines.append(f'{x["item"]} - {int(x["calories"])} קל׳')

                lines.append("")
                lines.append(f"סה״כ יומי עד כה: {total} קלוריות")
                reply = "\n".join(lines)

    except Exception as e:
        reply = f"שגיאה בחישוב 😕\n{str(e)}"

    resp = MessagingResponse()
    resp.message(reply)
    return str(resp)

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000)
