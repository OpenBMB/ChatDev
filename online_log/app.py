import logging

import requests
import os
from flask import Flask, send_from_directory, request, jsonify

app = Flask(__name__, static_folder='static')

app.logger.setLevel(logging.ERROR)

log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

messages = []


def send_msg(role, text):
    try:
        data = {"role": role, "text": text}
        response = requests.post("http://127.0.0.1:8000/send_message", json=data)
        if response.status_code == 200:
            print("Message sent successfully!")
        else:
            print("Failed to send message.")
    except:
        logging.info("flask app.py did not start for online log")


@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/chain_visualizer")
def chain_visualizer():
    return send_from_directory("static", "chain_visualizer.html")

@app.route("/replay")
def replay():
    return send_from_directory("static", "replay.html")

@app.route("/get_messages")
def get_messages():
    return jsonify(messages)


@app.route("/send_message", methods=["POST"])
def send_message():
    data = request.get_json()
    role = data.get("role")
    text = data.get("text")

    avatarUrl = find_avatar_url(role)

    message = {"role": role, "text": text, "avatarUrl": avatarUrl}
    messages.append(message)
    return jsonify(message)


def find_avatar_url(role):
    role = role.replace(" ", "%20")
    avatar_filename = f"avatars/{role}.png"
    avatar_url = f"/static/{avatar_filename}"
    return avatar_url


if __name__ == "__main__":
    print("please visit http://127.0.0.1:8000/ for demo")
    app.run(debug=False, port=8000)
