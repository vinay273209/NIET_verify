from flask import Flask, render_template, request, jsonify
import pandas as pd
from datetime import datetime
import os

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
EXCEL_FILE = os.path.join(BASE_DIR, "data", "students.xlsx")

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/verify", methods=["POST"])
def verify_student():
    data = request.get_json()
    qr_uuid = str(data.get("uuid")).strip()

    df = pd.read_excel(EXCEL_FILE)
    df.columns = df.columns.str.strip()  # clean headers

    if qr_uuid not in df["UUID"].astype(str).values:
        return jsonify({"status": "invalid"})

    idx = df[df["UUID"].astype(str) == qr_uuid].index[0]
    student = df.loc[idx]

    status_col = "verifyed status"
    time_col = "time"

    current_status = str(student.get(status_col, "")).strip().lower()
    already_verified = current_status == "yes"

    if not already_verified:
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        df.at[idx, status_col] = "Yes"
        df.at[idx, time_col] = current_time
        df.to_excel(EXCEL_FILE, index=False, engine="openpyxl")
    else:
        current_time = str(student.get(time_col, ""))

    return jsonify({
        "status": "valid",
        "already_verified": already_verified,
        "name": student["NAME"],
        "email": student["EMAIL-ID"],
        "branch": student["BRANCH"],
        "uuid": student["UUID"],
        "time": current_time
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
