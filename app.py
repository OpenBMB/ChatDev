import logging
import os
from flask import Flask, send_from_directory, render_template, request, jsonify

from god_mode import GodMode
from chatdev.utils import send_msg

app = Flask(__name__, static_folder='online_log/static')

app.logger.setLevel(logging.ERROR)

log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

messages = []
project = None



@app.route("/")
def index():
    return send_from_directory("online_log/static", "index.html")


@app.route("/chain_visualizer")
def chain_visualizer():
    return send_from_directory("online_log/static", "chain_visualizer.html")

@app.route("/replay")
def replay():
    return send_from_directory("online_log/static", "replay.html")

@app.route("/get_messages")
def get_messages():
    return jsonify(messages)

@app.route("/send_god_message", methods=["POST"])
def send_god_message():
    text = request.form.get('god-message')
    if project is not None:
        project.chat_chain.update_god_message(text)
    send_msg("Customer", text)
    return jsonify({"status": "success"})

@app.route("/project_description")
def project_description():
    if project is None:
        return "No project started."
    return jsonify({"name": project.name, "description": project.description})

@app.route("/send_message", methods=["POST"])
def send_message():
    data = request.get_json()
    role = data.get("role")
    text = data.get("text")

    avatarUrl = find_avatar_url(role)

    message = {"role": role, "text": text, "avatarUrl": avatarUrl}
    messages.append(message)
    return jsonify(message)

@app.route("/start_new_project", methods=["POST"])
def start_new_project():
    project_name = request.form.get('project-name')
    project_description = request.form.get('project-description')
    print(f"Starting a new project, name: {project_name}, description: {project_description})")
    global project
    project = GodMode(project_name=project_name, project_description=project_description)
    return jsonify({"status": "success", "name": project.name, "description": project.description})

@app.route("/start_working", methods=["POST"])
def start_working():
    project.next()
    return jsonify({"status": "success"})

def find_avatar_url(role):
    role = role.replace(" ", "%20")
    avatar_filename = f"avatars/{role}.png"
    avatar_url = f"/static/{avatar_filename}"
    return avatar_url


if __name__ == "__main__":
    print("please visit http://127.0.0.1:8000/ for demo")
    app.run(debug=False, port=8000)
