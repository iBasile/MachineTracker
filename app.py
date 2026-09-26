from __future__ import annotations

import json
import os
import socket
import sqlite3
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, render_template, request
from flask_socketio import SocketIO

BASE_DIR = Path(__file__).resolve().parent
DATABASE = Path(os.environ.get("LINGE_DB", BASE_DIR / "linges.db"))
TCP_PORT = int(os.environ.get("LINGE_TCP_PORT", "9000"))
DEBOUNCE_SECONDS = 3

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("LINGE_SECRET", "change-me-in-production")
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")
state_lock = threading.Lock()
last_reads: dict[str, float] = {}
add_mode = False

FIELDS = (
    "epc", "nom", "type", "couleur", "temperature", "matiere",
    "proprietaire", "date_dernier_lavage", "instructions",
)


def connect_db() -> sqlite3.Connection:
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db() -> None:
    with connect_db() as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS habits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                epc TEXT NOT NULL UNIQUE COLLATE NOCASE,
                nom TEXT NOT NULL,
                type TEXT NOT NULL,
                couleur TEXT NOT NULL,
                temperature INTEGER NOT NULL CHECK (temperature BETWEEN 0 AND 100),
                matiere TEXT NOT NULL,
                proprietaire TEXT NOT NULL,
                date_dernier_lavage TEXT,
                instructions TEXT NOT NULL DEFAULT '',
                present INTEGER NOT NULL DEFAULT 0,
                derniere_detection TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS detections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                epc TEXT NOT NULL,
                detected_at TEXT NOT NULL,
                known INTEGER NOT NULL DEFAULT 0
            );
        """)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return dict(row)


def validate_habit(payload: dict[str, Any], partial: bool = False) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for field in FIELDS:
        if field in payload:
            values[field] = payload[field]
        elif not partial:
            raise ValueError(f"Le champ « {field} » est obligatoire.")
    if "epc" in values:
        values["epc"] = str(values["epc"]).strip().upper()
        if not values["epc"]:
            raise ValueError("L’EPC ne peut pas être vide.")
    for field in ("nom", "type", "couleur", "matiere", "proprietaire"):
        if field in values and not str(values[field]).strip():
            raise ValueError(f"Le champ « {field} » ne peut pas être vide.")
    if "temperature" in values:
        try:
            values["temperature"] = int(values["temperature"])
        except (TypeError, ValueError) as exc:
            raise ValueError("La température doit être un nombre entier.") from exc
        if not 0 <= values["temperature"] <= 100:
            raise ValueError("La température doit être comprise entre 0 et 100 °C.")
    if "date_dernier_lavage" in values and values["date_dernier_lavage"]:
        try:
            datetime.strptime(str(values["date_dernier_lavage"]), "%Y-%m-%d")
        except ValueError as exc:
            raise ValueError("La date doit être au format AAAA-MM-JJ.") from exc
    values.setdefault("instructions", "")
    return values


def process_scan(epc: str) -> dict[str, Any]:
    global add_mode
    epc = epc.strip().upper()
    if not epc:
        raise ValueError("EPC vide.")
    current_time = time.monotonic()
    with state_lock:
        if current_time - last_reads.get(epc, 0) < DEBOUNCE_SECONDS:
            return {"epc": epc, "ignored": True, "reason": "debounced"}
        last_reads[epc] = current_time

    detected_at = now_iso()
    with connect_db() as db:
        habit = db.execute("SELECT * FROM habits WHERE epc = ?", (epc,)).fetchone()
        db.execute(
            "INSERT INTO detections (epc, detected_at, known) VALUES (?, ?, ?)",
            (epc, detected_at, int(habit is not None)),
        )
        if habit:
            db.execute(
                "UPDATE habits SET present = 1, derniere_detection = ?, "
                "updated_at = ? WHERE epc = ?",
                (detected_at, detected_at, epc),
            )
            habit = db.execute("SELECT * FROM habits WHERE epc = ?", (epc,)).fetchone()
        db.commit()

    result = {"epc": epc, "known": habit is not None, "detected_at": detected_at}
    if habit:
        result["habit"] = row_to_dict(habit)
    if add_mode and not habit:
        socketio.emit("tag_detected", {"epc": epc})
    socketio.emit("scan", result)
    return result


@app.get("/")
def dashboard():
    return render_template("index.html")


@app.get("/admin")
def admin():
    return render_template("admin.html")


@app.get("/api/habits")
def list_habits():
    with connect_db() as db:
        rows = db.execute("SELECT * FROM habits ORDER BY nom COLLATE NOCASE").fetchall()
    return jsonify([row_to_dict(row) for row in rows])


@app.post("/api/habits")
def create_habit():
    try:
        values = validate_habit(request.get_json(silent=True) or {})
        columns = ", ".join(values)
        placeholders = ", ".join("?" for _ in values)
        with connect_db() as db:
            cursor = db.execute(
                f"INSERT INTO habits ({columns}) VALUES ({placeholders})",
                tuple(values.values()),
            )
            habit = db.execute("SELECT * FROM habits WHERE id = ?", (cursor.lastrowid,)).fetchone()
            db.commit()
        socketio.emit("habit_updated", row_to_dict(habit))
        return jsonify(row_to_dict(habit)), 201
    except ValueError as error:
        return jsonify(error=str(error)), 400
    except sqlite3.IntegrityError:
        return jsonify(error="Cet EPC est déjà enregistré."), 409


@app.put("/api/habits/<int:habit_id>")
def update_habit(habit_id: int):
    try:
        values = validate_habit(request.get_json(silent=True) or {}, partial=True)
        if not values:
            return jsonify(error="Aucune modification fournie."), 400
        assignments = ", ".join(f"{key} = ?" for key in values)
        values["updated_at"] = now_iso()
        with connect_db() as db:
            cursor = db.execute(
                f"UPDATE habits SET {assignments}, updated_at = ? WHERE id = ?",
                (*[values[key] for key in values if key != "updated_at"], values["updated_at"], habit_id),
            )
            if cursor.rowcount == 0:
                return jsonify(error="Habit introuvable."), 404
            habit = db.execute("SELECT * FROM habits WHERE id = ?", (habit_id,)).fetchone()
            db.commit()
        socketio.emit("habit_updated", row_to_dict(habit))
        return jsonify(row_to_dict(habit))
    except ValueError as error:
        return jsonify(error=str(error)), 400
    except sqlite3.IntegrityError:
        return jsonify(error="Cet EPC est déjà enregistré."), 409


@app.delete("/api/habits/<int:habit_id>")
def delete_habit(habit_id: int):
    with connect_db() as db:
        cursor = db.execute("DELETE FROM habits WHERE id = ?", (habit_id,))
        db.commit()
    if cursor.rowcount == 0:
        return jsonify(error="Habit introuvable."), 404
    socketio.emit("habit_deleted", {"id": habit_id})
    return "", 204


@app.get("/api/state")
def state():
    with connect_db() as db:
        total = db.execute("SELECT COUNT(*) FROM habits").fetchone()[0]
        present = db.execute("SELECT COUNT(*) FROM habits WHERE present = 1").fetchone()[0]
        dirty = db.execute("SELECT * FROM habits WHERE present = 1 ORDER BY temperature, couleur, nom").fetchall()
        history = db.execute("""
            SELECT d.*, h.nom FROM detections d LEFT JOIN habits h ON h.epc = d.epc
            ORDER BY d.id DESC LIMIT 20
        """).fetchall()
    return jsonify({"add_mode": add_mode, "total": total, "present": present,
                    "suggestions": build_suggestions([row_to_dict(row) for row in dirty]),
                    "history": [row_to_dict(row) for row in history]})


def build_suggestions(dirty_habits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group dirty habits into conservative loads sharing wash constraints."""
    groups: dict[tuple[int, str], list[dict[str, Any]]] = {}
    for habit in dirty_habits:
        key = (int(habit["temperature"]), habit["matiere"].strip().lower())
        groups.setdefault(key, []).append(habit)

    suggestions = []
    for (temperature, matiere), habits in groups.items():
        colors = {habit["couleur"].strip().lower() for habit in habits}
        color_label = "couleurs mélangées" if len(colors) > 1 else habits[0]["couleur"]
        suggestions.append({
            "temperature": temperature,
            "matiere": matiere,
            "couleur": color_label,
            "count": len(habits),
            "habits": [{"id": h["id"], "nom": h["nom"]} for h in habits],
            "instructions": sorted({
                h["instructions"].strip() for h in habits if h["instructions"].strip()
            }),
        })
    return sorted(suggestions, key=lambda item: (item["temperature"], item["matiere"]))


@app.post("/api/laundry/empty")
def empty_laundry_basket():
    with connect_db() as db:
        db.execute("UPDATE habits SET present = 0, updated_at = ?", (now_iso(),))
        db.commit()
    socketio.emit("basket_updated")
    return jsonify(success=True)


@app.post("/api/add-mode")
def set_add_mode():
    global add_mode
    payload = request.get_json(silent=True) or {}
    add_mode = bool(payload.get("enabled", False))
    socketio.emit("add_mode", {"enabled": add_mode})
    return jsonify(enabled=add_mode)


@app.post("/api/scan")
def scan():
    payload = request.get_json(silent=True) or {}
    try:
        result = process_scan(str(payload.get("epc", "")))
        return jsonify(result)
    except ValueError as error:
        return jsonify(error=str(error)), 400


def tcp_listener() -> None:
    """Accept one JSON object per line for ESP32 firmware using raw TCP."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(("0.0.0.0", TCP_PORT))
        server.listen()
        while True:
            client, _ = server.accept()
            with client:
                buffer = b""
                while data := client.recv(1024):
                    buffer += data
                    while b"\n" in buffer:
                        line, buffer = buffer.split(b"\n", 1)
                        try:
                            result = process_scan(json.loads(line).get("epc", ""))
                            client.sendall((json.dumps(result) + "\n").encode())
                        except (ValueError, json.JSONDecodeError) as error:
                            client.sendall((json.dumps({"error": str(error)}) + "\n").encode())


if __name__ == "__main__":
    init_db()
    threading.Thread(target=tcp_listener, daemon=True, name="esp32-tcp").start()
    socketio.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), allow_unsafe_werkzeug=True)
