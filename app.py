from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from openai import OpenAI
import os

app = Flask(__name__)

client = OpenAI(
    api_key=os.environ["OPENAI_API_KEY"]
)

@app.route("/")
def home():
    return "Bot Running"

@app.route("/whatsapp", methods=["POST"])
def whatsapp():

    msg = request.form.get("Body", "")

    prompt = f"""
User sent food list in Hebrew:

{msg}

Return:
1. Each food item
2. Estimated calories per item
3. Total calories

Answer in Hebrew only.
"""

    response = client.chat.completions.create(
        model="gpt-5-mini",
        messages=[
            {"role": "user", "content": prompt}
        ]
    )

    answer = response.choices[0].message.content

    twilio_response = MessagingResponse()
    twilio_response.message(answer)

    return str(twilio_response)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
