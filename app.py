from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from openai import OpenAI
import os, json, sqlite3, re
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

def extract_json(text):
    text = text.strip()
    text = re.sub(r"^```json\s*", "", text)
    text = re.sub(r"^```\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return json.loads(text)

@app.route("/")
def home():
    init_db()
    return "Bot Running"

@app.route("/whatsapp", methods=["POST"])
def whatsapp():
    init_db()

    msg = request.form.get("Body", "").strip()
    sender = request.form.get("From", "")

    try:
        command = msg.upper()

        if command == "RESET":
            reset_today(sender)
            reply = "✅ היום אופס בהצלחה\nסה״כ היום: 0 קלוריות"

        elif command == "TOTAL":
            total = daily_total(sender)
            reply = f"סה״כ יומי עד כה: {total} קלוריות"

        elif command == "SUMMARY":
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
            prompt = f"""
אתה בוט קלוריות בעברית.

המשתמש כתב:
{msg}

החזר JSON בלבד, בלי טקסט נוסף, בפורמט הזה:
{{
  "items": [
    {{"item": "שם מוצר וכמות", "calories": 100}}
  ]
}}

חוקים:
1. אם המשתמש כתב קלוריות מדויקות, השתמש בהן בדיוק.
2. אם לא נכתבו קלוריות מדויקות, הערך קלוריות והוסף 3%-5% מרווח ביטחון.
3. אם ההודעה כוללת כמה מוצרים, פצל לשורות נפרדות.
4. אם ההודעה לא קשורה לאוכל, החזר items ריק.
5. calories חייב להיות מספר שלם בלבד.
"""

            ai = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0
            )

            raw = ai.choices[0].message.content
            data = extract_json(raw)
            items = data.get("items", [])

            if not items:
                reply = "לא זיהיתי אוכל בהודעה 😕\nאפשר לכתוב למשל: אכלתי ביצה ופרוסת לחם"
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

    twilio_response = MessagingResponse()
    twilio_response.message(reply)
    return str(twilio_response)

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000)
