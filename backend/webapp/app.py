from flask import Flask, render_template
from flask_socketio import SocketIO, emit

from cosmos import test_upload_json_files, run_cosmos_queries as run_queries

import os

app = Flask(__name__)

socket = SocketIO(
    app,
    cors_allowed_origins="*",
    transports=["websocket", "polling"]
)

@app.route("/")
def index():
    return render_template("index.html")


@socket.on("start", namespace="/cosmos-db-nosql")
def start(data):
    emitOutput("Current Status:\tStarting...")
    test_upload_json_files(emitOutput)
    
@socket.on("run_queries", namespace="/cosmos-db-nosql")
def run_cosmos_queries_handler(data=None):
    emitOutput("Current Status:\tRunning queries...")
    run_queries(emitOutput)

def emitOutput(message, isCode=False):
    emit("new_message", {"message": message, "code": isCode})


if __name__ == "__main__":
    socket.run(
        app,
        port=os.getenv("PORT", default=5000),
        debug=os.getenv("DEBUG", default=True),
    )