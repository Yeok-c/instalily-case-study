from flask import Flask, render_template, request, jsonify, send_from_directory, session
from flask_socketio import SocketIO, emit
from flask_cors import CORS
from flask_session import Session
import uuid
# Add these imports
import datetime
from cosmos import setup_chat_history_container, save_chat_history, get_chat_history, clear_chat_history
from azure.cosmos import CosmosClient

from cosmos import test_upload_json_files, run_cosmos_queries as run_queries
from azure_openai_agent import query_azure_openai

import os

app = Flask(__name__, static_folder='static', static_url_path='')
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'default_secret_key_for_dev')
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_PERMANENT'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = 86400  # 24 hours

# Initialize Flask-Session
Session(app)

# Enable CORS properly with specific origins
CORS(app, 
     resources={r"/api/*": {"origins": "*"}}, 
     supports_credentials=True)  # Important for maintaining session cookies

socket = SocketIO(
    app,
    cors_allowed_origins="*",
    transports=["websocket", "polling"]
)

# Chat history storage (in-memory for development, use database for production)
chat_histories = {}

# Add to app.py
@app.route("/api/health", methods=["GET"])
def health_check():
    return jsonify({"status": "ok", "message": "API is running"}), 200


# Initialize Cosmos DB clients
client = CosmosClient.from_connection_string(os.getenv("COSMOS_CONNECTION_STRING"))
database = client.get_database_client(os.getenv("CONFIGURATION__AZURECOSMOSDB__DATABASENAME", "cosmicworks"))
chat_history_container = setup_chat_history_container(database)

@app.route("/api/query", methods=["POST"])
def api_query():
    try:
        data = request.json
        if not data or "query" not in data:
            return jsonify({"error": "Invalid request. 'query' field is required"}), 400
        
        # Get or create a chat session ID
        chat_id = data.get("chat_id")
        if not chat_id:
            chat_id = str(uuid.uuid4())
        
        # Get user ID from session or create one
        user_id = session.get("user_id")
        if not user_id:
            user_id = str(uuid.uuid4())
            session["user_id"] = user_id
        
        # Get chat history from Cosmos DB
        history = get_chat_history(chat_history_container, user_id, chat_id)
        
        # Process query
        class OutputCollector:
            def __init__(self):
                self.output = []
            def collect(self, message, isCode=False):
                self.output.append({"message": message, "isCode": isCode})
        
        collector = OutputCollector()
        result = query_azure_openai(data["query"], collector.collect, history)
        
        # Update chat history with the new messages
        history.append({"role": "user", "content": data["query"]})
        history.append({"role": "assistant", "content": result})
        
        # Save updated history to Cosmos DB
        save_chat_history(chat_history_container, user_id, chat_id, history)
        
        # Return the result as JSON with chat ID
        return jsonify({
            "response": result,
            "chat_id": chat_id,
            "debug_output": collector.output
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/history/<chat_id>", methods=["GET"])
def get_chat_history_endpoint(chat_id):
    try:
        user_id = session.get("user_id")
        if not user_id:
            return jsonify({"history": [], "chat_id": chat_id})
        
        history = get_chat_history(chat_history_container, user_id, chat_id)
        return jsonify({"history": history, "chat_id": chat_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/history/<chat_id>", methods=["DELETE"])
def clear_chat_history_endpoint(chat_id):
    try:
        user_id = session.get("user_id")
        if not user_id:
            return jsonify({"success": True, "message": "No chat history found"})
        
        success = clear_chat_history(chat_history_container, user_id, chat_id)
        if success:
            return jsonify({"success": True, "message": "Chat history cleared"})
        else:
            return jsonify({"success": False, "message": "Failed to clear chat history"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
# # API endpoint implementation
# @app.route("/api/query", methods=["POST"])
# def api_query():
#     try:
#         data = request.json
#         if not data or "query" not in data:
#             return jsonify({"error": "Invalid request. 'query' field is required"}), 400
        
#         # Get or create a chat session ID
#         chat_id = data.get("chat_id")
#         if not chat_id:
#             chat_id = str(uuid.uuid4())
        
#         # Get existing chat history or initialize new one
#         history = chat_histories.get(chat_id, [])
        
#         # Process query without socket.io
#         class OutputCollector:
#             def __init__(self):
#                 self.messages = []
            
#             def collect(self, message, isCode=False):
#                 self.messages.append(message)
        
#         collector = OutputCollector()
#         result = query_azure_openai(data["query"], collector.collect, history)
        
#         # Update chat history with the new messages
#         history.append({"role": "user", "content": data["query"]})
#         history.append({"role": "assistant", "content": result})
        
#         # Save updated history
#         chat_histories[chat_id] = history
        
#         # Return the result as JSON with chat ID
#         return jsonify({
#             "response": result, 
#             "debug_logs": collector.messages,
#             "chat_id": chat_id
#         })
#     except Exception as e:
#         print(f"API Error: {str(e)}")
#         return jsonify({"error": str(e)}), 500

# # New endpoint to get chat history
# @app.route("/api/history/<chat_id>", methods=["GET"])
# def get_chat_history(chat_id):
#     try:
#         history = chat_histories.get(chat_id, [])
#         return jsonify({"history": history, "chat_id": chat_id})
#     except Exception as e:
#         return jsonify({"error": str(e)}), 500

# # New endpoint to clear chat history
# @app.route("/api/history/<chat_id>", methods=["DELETE"])
# def clear_chat_history(chat_id):
#     try:
#         if chat_id in chat_histories:
#             chat_histories[chat_id] = []
#         return jsonify({"success": True, "message": "Chat history cleared"})
#     except Exception as e:
#         return jsonify({"error": str(e)}), 500

# # Make sure this is below the API routes
# @app.route('/', defaults={'path': ''})
# @app.route('/<path:path>')
# def serve_react(path):
#     if path != "" and os.path.exists(app.static_folder + '/' + path):
#         return send_from_directory(app.static_folder, path)
#     else:
#         return send_from_directory(app.static_folder, 'index.html')


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