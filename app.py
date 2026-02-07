from flask import Flask, render_template, request, jsonify
import pandas as pd
from datetime import datetime
import os
import secrets

app = Flask(__name__)

# --------------------------------------------------
# Paths
# --------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STUDENTS_FILE = os.path.join(BASE_DIR, "students.xlsx")
PASSKEY_FILE = os.path.join(BASE_DIR, "passkeys.xlsx")

# --------------------------------------------------
# Admin secret (ONLY for admin actions)
# --------------------------------------------------
ADMIN_SECRET = os.environ.get("ADMIN_SECRET", "NIETadmin0000")

# --------------------------------------------------
# Helper: Normalize UUID (REMOVE LAST UNDERSCORE PART)
# --------------------------------------------------
def normalize_uuid(u):
    return str(u).strip().rsplit("_", 1)[0]

# --------------------------------------------------
# Helper: Load active volunteer keys
# --------------------------------------------------
def get_active_volunteer_keys():
    if not os.path.exists(PASSKEY_FILE):
        return set()

    df = pd.read_excel(PASSKEY_FILE)
    df.columns = df.columns.str.strip()

    active_keys = df[
        df["active"].astype(str).str.strip().str.lower() == "yes"
    ]["pass_key"].astype(str).str.strip()

    return set(active_keys.values)

# --------------------------------------------------
# Helper: Validate volunteer key
# --------------------------------------------------
def is_valid_volunteer_key(key):
    if not key:
        return False
    return key in get_active_volunteer_keys()

# --------------------------------------------------
# Home (Volunteer scanner UI)
# --------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html")

# --------------------------------------------------
# Admin UI
# --------------------------------------------------
@app.route("/admin")
def admin():
    return render_template("admin.html")

# --------------------------------------------------
# Admin: Generate volunteer key
# --------------------------------------------------
@app.route("/admin/generate-key", methods=["POST"])
def generate_key():
    data = request.get_json()
    if not data or data.get("admin_secret") != ADMIN_SECRET:
        return jsonify({"status": "unauthorized"}), 401

    erp_id = str(data.get("erp_id", "")).strip()
    if not erp_id:
        return jsonify({"status": "error", "message": "ERP ID required"}), 400

    new_key = secrets.token_hex(4).upper()

    if os.path.exists(PASSKEY_FILE):
        df = pd.read_excel(PASSKEY_FILE)
    else:
        df = pd.DataFrame(columns=["pass_key", "erp_id", "active"])

    df = pd.concat([df, pd.DataFrame([{
        "pass_key": new_key,
        "erp_id": erp_id,
        "active": "yes"
    }])], ignore_index=True)

    df.to_excel(PASSKEY_FILE, index=False)

    return jsonify({
        "status": "success",
        "pass_key": new_key,
        "erp_id": erp_id
    })

# --------------------------------------------------
# Admin: Disable volunteer key
# --------------------------------------------------
@app.route("/admin/delete-key", methods=["POST"])
def delete_key():
    data = request.get_json()
    if not data or data.get("admin_secret") != ADMIN_SECRET:
        return jsonify({"status": "unauthorized"}), 401

    pass_key = str(data.get("pass_key", "")).strip()
    if not pass_key:
        return jsonify({"status": "error", "message": "Pass key required"}), 400

    df = pd.read_excel(PASSKEY_FILE)
    df.columns = df.columns.str.strip()

    df.loc[df["pass_key"].astype(str).str.strip() == pass_key, "active"] = "no"
    df.to_excel(PASSKEY_FILE, index=False)

    return jsonify({"status": "success", "message": "Pass key disabled"})

# --------------------------------------------------
# Admin: View verification status
# --------------------------------------------------
@app.route("/admin/stats", methods=["POST"])
def admin_stats():
    data = request.get_json()
    if not data or data.get("admin_secret") != ADMIN_SECRET:
        return jsonify({"status": "unauthorized"}), 401

    df = pd.read_excel(STUDENTS_FILE)
    df.columns = df.columns.str.strip()

    total = len(df)
    verified = (
        df["verifyed status"]
        .astype(str)
        .str.strip()
        .str.lower()
        .isin(["yes", "present"])
        .sum()
    )

    return jsonify({
        "status": "success",
        "total_students": int(total),
        "verified": int(verified),
        "unverified": int(total - verified)
    })

# --------------------------------------------------
# Verify student (UUID MATCH BEFORE LAST UNDERSCORE)
# --------------------------------------------------
@app.route("/verify", methods=["POST"])
def verify_student():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "Invalid request"}), 400

        volunteer_key = str(data.get("volunteer_key", "")).strip()
        if not is_valid_volunteer_key(volunteer_key):
            return jsonify({
                "status": "forbidden",
                "message": "Invalid or disabled volunteer key"
            }), 403

        qr_uuid = normalize_uuid(data.get("uuid", ""))
        if not qr_uuid:
            return jsonify({"status": "error", "message": "UUID missing"}), 400

        df = pd.read_excel(STUDENTS_FILE)
        df.columns = df.columns.str.strip()

        df["UUID_norm"] = df["UUID"].astype(str).apply(normalize_uuid)

        if qr_uuid not in df["UUID_norm"].values:
            return jsonify({"status": "invalid"})

        idx = df[df["UUID_norm"] == qr_uuid].index[0]
        student = df.loc[idx]

        status = str(student.get("verifyed status", "")).strip().lower()

        if status in ["yes", "present"]:
            return jsonify({
                "status": "valid",
                "already_verified": True,
                "name": student["NAME"],
                "branch": student["BRANCH"],
                "uuid": student["UUID"],
                "time": student.get("time", "")
            })

        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        df.at[idx, "verifyed status"] = "Yes"
        df.at[idx, "time"] = current_time
        df.drop(columns=["UUID_norm"], inplace=True)

        df.to_excel(STUDENTS_FILE, index=False)

        return jsonify({
            "status": "valid",
            "already_verified": False,
            "name": student["NAME"],
            "branch": student["BRANCH"],
            "uuid": student["UUID"],
            "time": current_time
        })

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# --------------------------------------------------
# Admin: View volunteer keys
# --------------------------------------------------
@app.route("/admin/keys", methods=["POST"])
def admin_keys():
    data = request.get_json()
    if not data or data.get("admin_secret") != ADMIN_SECRET:
        return jsonify({"status": "unauthorized"}), 401

    if not os.path.exists(PASSKEY_FILE):
        return jsonify({"status": "success", "keys": []})

    df = pd.read_excel(PASSKEY_FILE, dtype=str)
    df.columns = df.columns.str.strip()

    return jsonify({
        "status": "success",
        "keys": df.to_dict(orient="records")
    })

# --------------------------------------------------
# Run
# --------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
