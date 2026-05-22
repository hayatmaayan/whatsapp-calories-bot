from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot Running"

@app.route("/whatsapp", methods=["POST"])
def whatsapp():
    msg = request.form.get("Body", "")

    resp = MessagingResponse()
    resp.message(f"קיבלתי:\n{msg}")

    return str(resp)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)