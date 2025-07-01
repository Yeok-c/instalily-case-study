from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_socketio import SocketIO, emit
from flask_cors import CORS

from cosmos import test_upload_json_files, run_cosmos_queries as run_queries
from azure_openai_agent import query_azure_openai

import os

app = Flask(__name__, static_folder='static', static_url_path='')
# Enable CORS properly with specific origins
CORS(app, resources={r"/api/*": {"origins": "*"}})

socket = SocketIO(
    app,
    cors_allowed_origins="*",
    transports=["websocket", "polling"]
)

# Add to app.py
@app.route("/api/health", methods=["GET"])
def health_check():
    return jsonify({"status": "ok", "message": "API is running"}), 200

# API endpoint implementation
@app.route("/api/query", methods=["POST"])
def api_query():
    try:
        data = request.json
        if not data or "query" not in data:
            return jsonify({"error": "Invalid request. 'query' field is required"}), 400
        
        # Process query without socket.io
        class OutputCollector:
            def __init__(self):
                self.messages = []
            
            def collect(self, message, isCode=False):
                self.messages.append(message)
        
        collector = OutputCollector()
        result = query_azure_openai(data["query"], collector.collect)
        
        # Return the result as JSON
        return jsonify({"response": result, "debug_logs": collector.messages})
    except Exception as e:
        print(f"API Error: {str(e)}")
        return jsonify({"error": str(e)}), 500

# Other routes remain unchanged...

# Make sure this is below the API routes
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_react(path):
    if path != "" and os.path.exists(app.static_folder + '/' + path):
        return send_from_directory(app.static_folder, path)
    else:
        return send_from_directory(app.static_folder, 'index.html')

if __name__ == "__main__":
    port = int(os.getenv("PORT", default=5000))
    debug = os.getenv("DEBUG", default="True").lower() == "true"
    
    print(f"Starting server on port {port}, debug={debug}")
    socket.run(
        app,
        host="0.0.0.0",
        port=port,
        debug=debug
    )