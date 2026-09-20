"""
IncidentIQ Local Web Server
Runs a local HTTP server providing the frontend UI and the /api/analyze agent endpoint.

Run:
    python src/server.py
"""

import json
from pathlib import Path
from flask import Flask, jsonify, request, send_from_directory
from agent import analyze_incident

app = Flask(__name__, static_folder=None)
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"


@app.route("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.route("/api/analyze", methods=["POST"])
def analyze():
    data = request.get_json(silent=True) or {}
    log_group = data.get("log_group")
    minutes_back = data.get("minutes_back", 10)

    if not log_group:
        return jsonify({"error": "log_group is required"}), 400

    try:
        raw_result = analyze_incident(log_group=log_group, minutes_back=minutes_back)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    try:
        parsed = json.loads(raw_result)
        return jsonify(parsed)
    except Exception:
        return raw_result, 200, {"Content-Type": "application/json"}


if __name__ == "__main__":
    print("=" * 60)
    print("IncidentIQ web application running at: http://127.0.0.1:5000")
    print("Open this URL in your web browser and click 'Analyze Incident'")
    print("=" * 60)
    app.run(host="127.0.0.1", port=5000, debug=False)
