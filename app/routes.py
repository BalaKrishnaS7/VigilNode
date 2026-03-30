from flask import Blueprint, render_template, request, session, redirect, url_for, jsonify
from functools import wraps
from config import Config
from app.database import get_recent_alerts
from app.monitors.system import get_system_stats
from app.monitors.network import get_network_stats

main = Blueprint("main", __name__)


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("main.login"))
        return f(*args, **kwargs)
    return decorated


@main.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if username == Config.DASHBOARD_USERNAME and password == Config.DASHBOARD_PASSWORD:
            session["logged_in"] = True
            return redirect(url_for("main.dashboard"))
        error = "Invalid credentials"
    return render_template("login.html", error=error)


@main.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("main.login"))


@main.route("/")
@login_required
def dashboard():
    alerts = get_recent_alerts(50)
    return render_template("dashboard.html", alerts=alerts)


@main.route("/api/stats")
@login_required
def api_stats():
    stats = get_system_stats()
    net = get_network_stats()
    return jsonify({**stats, "network": net})


@main.route("/api/alerts")
@login_required
def api_alerts():
    alerts = get_recent_alerts(50)
    return jsonify(alerts)
