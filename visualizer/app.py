import logging
import requests
import os
from flask import Flask, send_from_directory, request, jsonify
import argparse

app = Flask(__name__, static_folder='static')
app.logger.setLevel(logging.ERROR)
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)
messages = []
port = [8000]

def send_msg(role, text):
    try:
        data = {"role": role, "text": text}
        response = requests.post(f"http://127.0.0.1:{port[-1]}/send_message", json=data)
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

# Define rout to send team a project
# to run a project we must call run.py 
# run.py [-h] [--config CONFIG] [--org ORG] [--task TASK] [--name NAME] [--model MODEL] [--path PATH]
import subprocess

@app.route("/send_project", methods=["POST"])
def send_project():
    data = request.get_json()
    cmd = ["python3", "run.py"]
    
    for arg in ["task", "config", "org", "name", "model", "path"]:
        if data.get(arg):
            cmd.extend([f"--{arg}", data[arg]])
    
    try:
        subprocess.run(cmd, check=True)
        return jsonify({"status": "success"}), 200
    except subprocess.CalledProcessError as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# Example form for sending a project
# <form id="send_project" action="/send_project" method="post">
#     <input type="text" name="org" placeholder="Organization" />
#     <input type="text" name="task" placeholder="Task" />
#     <input type="text" name="role" placeholder="Role" />
#     <input type="text" name="project" placeholder="Project" />
#     <input type="text" name="port" placeholder="Port" />
#     <input type="text" name="config" placeholder="Config" />
#     <button type="submit">Send Project</button>
# </form>
# Let's override the default send_project form action and instead use js to send the project
# document.getElementById("send_project").addEventListener("submit", function(e) {
#     e.preventDefault();
#     var org = document.querySelector("input[name=org]").value;
#     var task = document.querySelector("input[name=task]").value;
#     var role = document.querySelector("input[name=role]").value;
#     var project = document.querySelector("input[name=project]").value;
#     var port = document.querySelector("input[name=port]").value;
#     var config = document.querySelector("input[name=config]").value;
#     fetch("/send_project", {
#         method: "POST",
#         headers: {
#             "Content-Type": "application/json"
#         },
#         body: JSON.stringify({
#             org: org,
#             task: task,
#             role: role,
#             project: project,
#             port: port,
#             config: config
#         })
#     });
# });



#Define the favicon route
@app.route('/favicon.ico')
def favicon():
    #Return the favicon found in static folder root
    return send_from_directory(os.path.join(app.root_path, 'static'),
                               'favicon.ico', mimetype='image/vnd.microsoft.icon')
def find_avatar_url(role):
    role = role.replace(" ", "%20")
    avatar_filename = f"avatars/{role}.png"
    avatar_url = f"/static/{avatar_filename}"
    return avatar_url

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='argparse')
    parser.add_argument('--port', type=int, default=8000, help="port")
    args = parser.parse_args()
    port.append(args.port)
    print(f"Please visit http://127.0.0.1:{port[-1]}/ for the front-end display page. \nIn the event of a port conflict, please modify the port argument (e.g., python3 app.py --port 8012).")
    app.run(host='0.0.0.0', debug=False, port=port[-1])
