# app.py - Flask web interface for the network diagnostic agent

import os
import sys
from dotenv import load_dotenv
from flask import Flask, render_template_string, request

load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.agent.core import diagnose
from src.agent.llm import DEFAULT_MODEL, MODEL_OPTIONS

app = Flask(__name__)

HTML = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Network Diagnostic Agent</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
  <style>
    body { background: #f0f2f5; }
    .card { border-radius: 12px; border: none; }
    .label { font-size: 0.72rem; font-weight: 600; letter-spacing: .08em;
             text-transform: uppercase; color: #6c757d; margin-bottom: 4px; }
    ol { padding-left: 1.2rem; margin-bottom: 0; }
    ol li + li { margin-top: 6px; }
  </style>
</head>
<body>
<div class="container py-5" style="max-width: 780px">

  <h1 class="fw-bold mb-1">Network Diagnostic Agent</h1>
  <p class="text-muted mb-4">
    Describe your network problem in plain English and the agent will run diagnostics and explain what it found.
  </p>

  <div class="card shadow-sm mb-4">
    <div class="card-body p-4">
      <form method="POST" action="/diagnose" id="diagForm">

        <div class="mb-3">
          <label class="form-label fw-semibold">Describe your problem</label>
          <textarea class="form-control" name="symptom" rows="3"
            placeholder='e.g. "I can&#39;t load any websites" or "My video calls keep dropping"'
            required>{{ symptom or "" }}</textarea>
        </div>

        <div class="mb-4">
          <label class="form-label fw-semibold">LLM Model</label>
          <select class="form-select" name="model">
            {% for model_id, label in models.items() %}
            <option value="{{ model_id }}" {{ "selected" if model_id == selected_model else "" }}>
              {{ label }}
            </option>
            {% endfor %}
          </select>
          <div class="form-text">
            Make sure the API key for the selected model is in your <code>.env</code> file.
          </div>
        </div>

        <button type="submit" class="btn btn-primary px-4" id="submitBtn">
          Run Diagnostics
        </button>
        <span class="ms-3 text-muted small" id="loadingMsg" style="display:none">
          Running... this may take 30-60 seconds
        </span>

      </form>
    </div>
  </div>

  {% if error %}
  <div class="alert alert-danger">{{ error }}</div>
  {% endif %}

  {% if result %}
  <div class="card shadow-sm">
    <div class="card-body p-4">
      <h5 class="fw-bold mb-4">Diagnosis</h5>

      <div class="mb-3">
        <div class="label">Summary</div>
        <p class="mb-0">{{ result.summary }}</p>
      </div>

      <hr class="my-3">

      <div class="mb-3">
        <div class="label">Root Cause</div>
        <p class="mb-0">{{ result.root_cause }}</p>
      </div>

      <hr class="my-3">

      <div>
        <div class="label">Recommendations</div>
        <ol>
          {% for rec in result.recommendations %}
          <li>{{ rec }}</li>
          {% endfor %}
        </ol>
      </div>

    </div>
  </div>
  {% endif %}

</div>

<script>
  document.getElementById("diagForm").addEventListener("submit", function () {
    document.getElementById("submitBtn").disabled = true;
    document.getElementById("loadingMsg").style.display = "inline";
  });
</script>
</body>
</html>
"""


@app.route("/", methods=["GET"])
def index():
    return render_template_string(
        HTML,
        models=MODEL_OPTIONS,
        selected_model=DEFAULT_MODEL,
        symptom=None,
        result=None,
        error=None,
    )


@app.route("/diagnose", methods=["POST"])
def run_diagnosis():
    symptom = request.form.get("symptom", "").strip()
    model   = request.form.get("model", DEFAULT_MODEL)
    result  = None
    error   = None

    if symptom:
        try:
            result = diagnose(symptom, model=model)
        except Exception as e:
            error = f"Diagnosis failed: {e}"

    return render_template_string(
        HTML,
        models=MODEL_OPTIONS,
        selected_model=model,
        symptom=symptom,
        result=result,
        error=error,
    )


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
