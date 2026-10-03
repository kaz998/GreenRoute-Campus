from datetime import datetime
import csv
import io
import os

from flask import Flask, Response, flash, jsonify, redirect, render_template, request, session, url_for
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFProtect
from werkzeug.security import check_password_hash, generate_password_hash

from .config import Config
from .db import close_db, get_db, init_db
from .ml.copilot import advise
from .ml.recommender import recommend
from .services.cloud_ai import configured as cloud_ai_configured
from .services.cloud_ai import recommend as cloud_ai_recommend
from .services.mobility import build_candidates, driving_baseline, mode_metrics
from .services.points import award_badges, level, stats
from .services.routing import geocode, route_details
from .services.weather import conditions

csrf = CSRFProtect()
limiter = Limiter(key_func=get_remote_address, default_limits=[])


def create_app(test_config=None):
    app = Flask(__name__, template_folder="../templates", static_folder="../static", static_url_path="/static")
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)

    os.makedirs(os.path.dirname(app.config["DATABASE"]), exist_ok=True)
    csrf.init_app(app)
    limiter.init_app(app)
    app.teardown_appcontext(close_db)

    with app.app_context():
        init_db()

    def user():
        user_id = session.get("user_id")
        if user_id:
            return get_db().execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        return None

    def modes():
        return get_db().execute("SELECT * FROM transport_modes ORDER BY name").fetchall()

    @app.context_processor
    def inject():
        return {
            "current_user": user(),
            "app_version": app.config.get("APP_VERSION", "4.0"),
        }

    def login_required(fn):
        from functools import wraps

        @wraps(fn)
        def wrapped(*args, **kwargs):
            if not user():
                return redirect(url_for("login", next=request.path))
            return fn(*args, **kwargs)

        return wrapped

    def admin_required(fn):
        from functools import wraps

        @wraps(fn)
        def wrapped(*args, **kwargs):
            if not user() or user()["role"] != "admin":
                return ("Forbidden", 403)
            return fn(*args, **kwargs)

        return wrapped

    @app.errorhandler(413)
    def too_large(_):
        return jsonify({"error": "Request is too large."}), 413

    @app.errorhandler(429)
    def rate_limited(_):
        if request.path.startswith("/api/"):
            return jsonify({"error": "Too many requests. Please wait a moment and try again."}), 429
        flash("Too many requests. Please wait a moment and try again.", "error")
        return redirect(request.referrer or url_for("home"))

    @app.get("/health")
    def health():
        db_ok = True
        try:
            get_db().execute("SELECT 1").fetchone()
        except Exception:
            db_ok = False
        return jsonify(
            {
                "ok": db_ok,
                "version": app.config.get("APP_VERSION", "4.0"),
                "database": db_ok,
                "cloud_ai_configured": cloud_ai_configured(),
            }
        )

    @app.route("/")
    def home():
        db = get_db()
        totals = db.execute(
            "SELECT COUNT(*) trips, ROUND(COALESCE(SUM(co2_saved_kg),0),1) saved, "
            "COUNT(DISTINCT user_id) commuters FROM trip_log"
        ).fetchone()
        baseline = db.execute(
            "SELECT COALESCE(SUM(distance_km * 0.18 + 8),0) baseline FROM trip_log"
        ).fetchone()
        car = db.execute(
            "SELECT COUNT(*) trips, COALESCE(AVG(t.co2_kg),0) co2 "
            "FROM trip_log t JOIN transport_modes m ON m.id=t.mode_id WHERE m.code='car'"
        ).fetchone()
        bus = db.execute(
            "SELECT COALESCE(AVG(t.co2_kg),0) co2 FROM trip_log t "
            "JOIN transport_modes m ON m.id=t.mode_id WHERE m.code='bus'"
        ).fetchone()
        baseline_kg = float(baseline["baseline"] or 0)
        saved_kg = float(totals["saved"] or 0)
        avoided_pct = round(min(100, max(0, saved_kg / baseline_kg * 100))) if baseline_kg else 0
        home_stats = {
            "trips": int(totals["trips"] or 0),
            "saved": saved_kg,
            "commuters": int(totals["commuters"] or 0),
            "car_trips": int(car["trips"] or 0),
            "car_co2": float(car["co2"] or 0),
            "bus_co2": float(bus["co2"] or 0),
            "baseline": round(baseline_kg, 1),
            "avoided_pct": avoided_pct,
        }
        return render_template(
            "index.html",
            weather=conditions(),
            home_stats=home_stats,
            systems={
                "AI": "Cloud AI" if cloud_ai_configured() else "Offline fallback",
                "Route": "OSRM + fallback",
                "Weather": "Open-Meteo + fallback",
            },
        )

    @app.route("/register", methods=["GET", "POST"])
    @limiter.limit("10 per minute")
    def register():
        if request.method == "POST":
            f = request.form
            name = f.get("name", "").strip()
            email = f.get("email", "").strip().lower()
            pwd = f.get("password", "")
            if not name or "@" not in email or len(pwd) < 6:
                flash("Enter a name, valid email and 6+ character password.", "error")
            else:
                try:
                    db = get_db()
                    db.execute(
                        "INSERT INTO users(name,email,password_hash,role,department,year,home_area) "
                        "VALUES(?,?,?,?,?,?,?)",
                        (
                            name,
                            email,
                            generate_password_hash(pwd),
                            "student",
                            f.get("department", "CSE"),
                            f.get("year", "1st"),
                            f.get("home_area", "Lucknow"),
                        ),
                    )
                    db.commit()
                    flash("Account created. Please log in.", "success")
                    return redirect(url_for("login"))
                except Exception:
                    flash("That email is already registered.", "error")
        return render_template("auth.html", register=True)

    @app.route("/login", methods=["GET", "POST"])
    @limiter.limit("10 per minute")
    def login():
        if request.method == "POST":
            r = get_db().execute(
                "SELECT * FROM users WHERE email=?", (request.form.get("email", "").strip().lower(),)
            ).fetchone()
            if r and check_password_hash(r["password_hash"], request.form.get("password", "")):
                session.clear()
                session["user_id"] = r["id"]
                return redirect(url_for("dashboard"))
            flash("Invalid email or password.", "error")
        return render_template("auth.html", register=False)

    @app.get("/logout")
    def logout():
        session.clear()
        return redirect(url_for("home"))

    @app.get("/planner")
    @login_required
    def planner():
        return render_template("planner.html", modes=[dict(r) for r in modes()], weather=conditions())

    @app.post("/api/geocode")
    @login_required
    @limiter.limit("20 per minute")
    def api_geocode():
        d = request.get_json(silent=True) or {}
        q = str(d.get("q", "")).strip()
        if not q or len(q) > 120:
            return jsonify({"error": "Enter a place name up to 120 characters."}), 400
        x = geocode(q)
        if not x:
            return jsonify({"error": "Place not found. Try a nearby landmark or click the map."}), 404
        return jsonify({"lat": x[0], "lon": x[1], "label": x[2]})

    @app.post("/api/route")
    @login_required
    @limiter.limit("30 per minute")
    def api_route():
        d = request.get_json(silent=True) or {}
        try:
            coords = [float(d[k]) for k in ("olat", "olon", "dlat", "dlon")]
            if not all(-90 <= coords[i] <= 90 for i in (0, 2)) or not all(-180 <= coords[i] <= 180 for i in (1, 3)):
                raise ValueError
        except (KeyError, TypeError, ValueError):
            return jsonify({"error": "Route coordinates are invalid."}), 400
        km, mins, source, geometry = route_details(*coords)
        return jsonify(
            {
                "distance_km": round(km, 2),
                "duration_min": round(mins, 1),
                "source": source,
                "geometry": geometry,
            }
        )

    @app.post("/api/compare")
    @login_required
    @limiter.limit("30 per minute")
    def api_compare():
        d = request.get_json(silent=True) or {}
        try:
            km = float(d.get("distance_km"))
            if km <= 0 or km > 100:
                raise ValueError
        except (TypeError, ValueError):
            return jsonify({"error": "Distance must be between 0 and 100 km."}), 400
        weather = conditions()
        out = build_candidates(modes(), km, weather)
        baseline = driving_baseline(km)
        return jsonify({"items": out, "weather": weather, "driving_baseline": round(baseline["co2"], 2), "driving_cost": round(baseline["cost"], 2)})

    @app.post("/api/take-trip")
    @login_required
    @limiter.limit("30 per minute")
    def take_trip():
        d = request.get_json(silent=True) or {}
        try:
            km = float(d.get("distance_km"))
            if km <= 0 or km > 100:
                raise ValueError
        except (TypeError, ValueError):
            return jsonify({"error": "Distance must be between 0 and 100 km."}), 400

        db = get_db()
        mode = db.execute("SELECT * FROM transport_modes WHERE code=?", (d.get("mode", ""),)).fetchone()
        if not mode:
            return jsonify({"error": "That transport mode is not available."}), 400

        weather = conditions()
        metrics = mode_metrics(mode, km, weather)
        baseline = driving_baseline(km)
        saved = max(0, baseline["co2"] - metrics["co2"])
        money = max(0, baseline["cost"] - metrics["cost"])
        origin = str(d.get("origin", "Map point"))[:160]
        destination = str(d.get("destination", "BBDNITM"))[:160]
        db.execute(
            "INSERT INTO trip_log(user_id,mode_id,origin,destination,distance_km,duration_min,co2_kg,"
            "co2_saved_kg,money_saved,calories,weather,aqi) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                session["user_id"],
                mode["id"],
                origin,
                destination,
                km,
                metrics["time"],
                metrics["co2"],
                saved,
                money,
                metrics["calories"],
                weather["label"],
                weather["aqi"],
            ),
        )
        db.commit()
        streak = award_badges(session["user_id"])
        return jsonify(
            {
                "saved": round(saved, 2),
                "money_saved": round(money, 2),
                "points": round(saved * 10),
                "streak": streak,
                "mode": mode["name"],
                "time": metrics["time"],
            }
        )

    @app.get("/dashboard")
    @login_required
    def dashboard():
        db = get_db()
        s = stats(session["user_id"])
        badges = db.execute(
            "SELECT b.* FROM badges b JOIN user_badges ub ON ub.badge_id=b.id "
            "WHERE ub.user_id=? ORDER BY ub.earned_at DESC",
            (session["user_id"],),
        ).fetchall()
        streak = award_badges(session["user_id"])
        points = round(s["saved"] * 10)
        return render_template("dashboard.html", stats=s, level=level(points), points=points, badges=badges, streak=streak)

    @app.get("/api/dashboard")
    @login_required
    def api_dashboard():
        db = get_db()
        rows = db.execute(
            "SELECT substr(started_at,1,10) day,SUM(co2_saved_kg) saved,SUM(money_saved) money,"
            "SUM(calories) calories FROM trip_log WHERE user_id=? GROUP BY day ORDER BY day",
            (session["user_id"],),
        ).fetchall()
        split = db.execute(
            "SELECT m.name,COUNT(*) n FROM trip_log t JOIN transport_modes m ON m.id=t.mode_id "
            "WHERE t.user_id=? GROUP BY m.name",
            (session["user_id"],),
        ).fetchall()
        latest = db.execute(
            "SELECT t.origin,t.destination,t.distance_km,t.duration_min,t.co2_saved_kg,m.name mode,t.started_at "
            "FROM trip_log t JOIN transport_modes m ON m.id=t.mode_id WHERE t.user_id=? ORDER BY t.started_at DESC LIMIT 5",
            (session["user_id"],),
        ).fetchall()
        return jsonify({"daily": [dict(r) for r in rows], "split": [dict(r) for r in split], "latest": [dict(r) for r in latest]})

    @app.get("/leaderboard")
    @login_required
    def leaderboard():
        db = get_db()
        period = request.args.get("period", "all")
        where = ""
        params = []
        if period == "week":
            where = "AND t.started_at >= datetime('now','-7 day')"
        elif period == "month":
            where = "AND t.started_at >= datetime('now','-30 day')"
        rows = db.execute(
            f"SELECT u.name,u.department,u.year,ROUND(COALESCE(SUM(t.co2_saved_kg),0),1) saved,COUNT(t.id) trips "
            f"FROM users u LEFT JOIN trip_log t ON t.user_id=u.id {where} GROUP BY u.id ORDER BY saved DESC LIMIT 25",
            params,
        ).fetchall()
        return render_template("leaderboard.html", rows=rows, period=period)

    @app.get("/challenges")
    @login_required
    def challenges():
        db = get_db()
        rows = db.execute("SELECT * FROM challenges ORDER BY end_date").fetchall()
        s = stats(session["user_id"])
        return render_template("challenges.html", challenges=rows, saved=s["saved"])

    @app.get("/carpool")
    @login_required
    def carpool():
        rows = get_db().execute(
            'SELECT p.*,u.name FROM carpool_posts p JOIN users u ON u.id=p.user_id '
            'WHERE p.status="open" ORDER BY p.depart_at'
        ).fetchall()
        return render_template("carpool.html", posts=rows)

    @app.post("/api/carpool")
    @login_required
    def add_carpool():
        d = request.form
        try:
            seats = min(max(int(d.get("seats", 1)), 1), 4)
        except ValueError:
            seats = 1
        get_db().execute(
            "INSERT INTO carpool_posts(user_id,kind,origin,destination,depart_at,seats) VALUES(?,?,?,?,?,?)",
            (session["user_id"], d["kind"], d["origin"].strip(), d["destination"].strip(), d["depart_at"], seats),
        )
        get_db().commit()
        return redirect(url_for("carpool"))

    @app.post("/api/carpool/<int:pid>/request")
    @login_required
    def request_carpool(pid):
        db = get_db()
        db.execute(
            "INSERT OR IGNORE INTO carpool_requests(post_id,rider_id) VALUES(?,?)",
            (pid, session["user_id"]),
        )
        db.commit()
        return redirect(url_for("carpool"))

    @app.get("/demo")
    def demo():
        r = get_db().execute("SELECT id FROM users WHERE email=?", ("student@greenroute.local",)).fetchone()
        if not r:
            return redirect(url_for("register"))
        session.clear()
        session["user_id"] = r["id"]
        return redirect(url_for("dashboard"))

    @app.get("/api/forecast")
    @login_required
    def forecast():
        try:
            shift_pct = min(max(float(request.args.get("shift", 10)), 0), 50)
        except ValueError:
            return jsonify({"error": "Shift must be between 0% and 50%."}), 400
        db = get_db()
        r = db.execute(
            "SELECT COALESCE(SUM(co2_kg),0) current,COUNT(*) trips FROM trip_log "
            "WHERE started_at>=datetime('now','-28 day')"
        ).fetchone()
        weekly = r["current"] / 4 if r["trips"] else 0
        shift = shift_pct / 100
        return jsonify({
            "weeks": [round(max(0, weekly * (1 - shift * i / 4)), 1) for i in range(1, 5)],
            "shift_pct": shift_pct,
        })

    @app.get("/ai")
    @login_required
    def ai_copilot():
        return render_template(
            "ai.html",
            weather=conditions(),
            cloud_ai=cloud_ai_configured(),
            ai_model=os.getenv("OPENAI_MODEL", "gpt-5.6-luna"),
        )

    @app.get("/api/ai-status")
    @login_required
    def api_ai_status():
        configured = cloud_ai_configured()
        return jsonify(
            {
                "cloud_configured": configured,
                "provider": "OpenAI cloud" if configured else "Local ML fallback",
                "model": os.getenv("OPENAI_MODEL", "gpt-5.6-luna"),
                "note": "The browser never receives the API key.",
            }
        )

    @app.post("/api/ai-advice")
    @login_required
    @limiter.limit("12 per hour")
    def api_ai_advice():
        d = request.get_json(silent=True) or {}
        text = str(d.get("message", "")).strip()
        if not text or len(text) > 1600:
            return jsonify({"error": "Write a commute request between 1 and 1600 characters."}), 400
        try:
            distance = float(d.get("distance_km", 5) or 5)
            hour = int(d.get("time_hour", 8) or 8)
            if distance <= 0 or distance > 100 or hour < 0 or hour > 23:
                raise ValueError
        except (TypeError, ValueError):
            return jsonify({"error": "Distance must be 0–100 km and departure hour must be 0–23."}), 400

        history = d.get("history", [])
        if not isinstance(history, list):
            history = []
        clean_history = []
        for item in history[-6:]:
            if isinstance(item, dict):
                role = str(item.get("role", "user"))[:20]
                content = str(item.get("content", ""))[:500]
                if content:
                    clean_history.append({"role": role, "content": content})

        weather = conditions()
        mode_rows = modes()
        candidate_items = build_candidates(mode_rows, distance, weather)
        local = advise(text, distance, hour, weather)

        if cloud_ai_configured():
            try:
                cloud_meta = cloud_ai_recommend(
                    text, distance, hour, weather, candidate_items, history=clean_history
                )
                selected = next(x for x in candidate_items if x["code"] == cloud_meta["mode"])
                feasible_alts = [
                    x for x in sorted(candidate_items, key=lambda x: (not x["feasible"], x["cost"], x["time"]))
                    if x["code"] != selected["code"] and x["feasible"]
                ][:4]
                return jsonify(
                    {
                        **local,
                        "mode": selected["code"],
                        "name": selected["name"],
                        "confidence": cloud_meta["confidence"],
                        "intent": cloud_meta["priority"],
                        "reason": cloud_meta["explanation"],
                        "tips": cloud_meta["tips"],
                        "provider": "openai",
                        "model": cloud_meta["model"],
                        "cloud_ai": True,
                        "time": selected["time"],
                        "cost": selected["cost"],
                        "co2": selected["co2"],
                        "calories": selected["calories"],
                        "alternatives": [
                            {
                                "name": x["name"],
                                "cost": x["cost"],
                                "time": x["time"],
                                "co2": x["co2"],
                                "green_score": x["green_score"],
                            }
                            for x in feasible_alts
                        ],
                    }
                )
            except Exception as exc:
                app.logger.warning("Cloud AI unavailable; using local fallback: %s", exc)
                local["cloud_error"] = "Cloud AI request failed, so GreenRoute used its offline model instead."

        local["provider"] = "local"
        local["model"] = "local-ml-fallback"
        local["cloud_ai"] = False
        local.setdefault("tips", [])
        return jsonify(local)

    @app.get("/smart")
    @login_required
    def smart():
        w = conditions()
        rec = recommend(session["user_id"], 5, 8, w)
        return render_template("smart.html", weather=w, rec=rec)

    @app.get("/admin")
    @admin_required
    def admin():
        db = get_db()
        totals = db.execute(
            "SELECT COUNT(*) trips,ROUND(COALESCE(SUM(co2_saved_kg),0),1) saved FROM trip_log"
        ).fetchone()
        modesplit = db.execute(
            "SELECT m.name,COUNT(*) n FROM trip_log t JOIN transport_modes m ON m.id=t.mode_id "
            "GROUP BY m.name ORDER BY n DESC"
        ).fetchall()
        routes = db.execute(
            "SELECT origin,destination,COUNT(*) n FROM trip_log GROUP BY origin,destination ORDER BY n DESC LIMIT 8"
        ).fetchall()
        deps = db.execute(
            "SELECT u.department,ROUND(SUM(t.co2_saved_kg),1) saved,COUNT(t.id) trips "
            "FROM users u LEFT JOIN trip_log t ON t.user_id=u.id GROUP BY u.department ORDER BY saved DESC"
        ).fetchall()
        return render_template("admin.html", totals=totals, modesplit=modesplit, routes=routes, deps=deps)

    @app.get("/admin/export.csv")
    @admin_required
    def export_csv():
        db = get_db()
        rows = db.execute(
            "SELECT t.started_at,u.name,u.department,t.origin,t.destination,m.name mode,t.distance_km,"
            "t.co2_saved_kg,t.money_saved FROM trip_log t JOIN users u ON u.id=t.user_id "
            "JOIN transport_modes m ON m.id=t.mode_id ORDER BY t.started_at DESC"
        ).fetchall()
        s = io.StringIO()
        w = csv.writer(s)
        w.writerow(rows[0].keys() if rows else ["started_at"])
        for row in rows:
            w.writerow(list(row))
        return Response(
            s.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment; filename=greenroute_report.csv"},
        )

    @app.get("/admin/print")
    @admin_required
    def print_report():
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas

        db = get_db()
        total = db.execute(
            "SELECT COUNT(*) c,COALESCE(SUM(co2_saved_kg),0) s,COALESCE(SUM(money_saved),0) m FROM trip_log"
        ).fetchone()
        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=A4)
        c.setFont("Helvetica-Bold", 20)
        c.drawString(50, 800, "GreenRoute Campus — Impact Summary")
        c.setFont("Helvetica", 12)
        c.drawString(50, 760, f"Trips logged: {total['c']}")
        c.drawString(50, 740, f"CO2 saved: {total['s']:.1f} kg")
        c.drawString(50, 720, f"Money saved: Rs {total['m']:.0f}")
        c.drawString(50, 680, "BBDNITM, Lucknow | Innovating for a Sustainable Tomorrow")
        c.save()
        buf.seek(0)
        return Response(
            buf.getvalue(),
            mimetype="application/pdf",
            headers={"Content-Disposition": "inline; filename=greenroute_summary.pdf"},
        )

    @app.get("/assumptions")
    def assumptions():
        return render_template("assumptions.html", modes=modes())

    @app.route("/profile", methods=["GET", "POST"])
    @login_required
    def profile():
        db = get_db()
        if request.method == "POST":
            db.execute(
                "UPDATE users SET name=?,department=?,year=?,home_area=? WHERE id=?",
                (
                    request.form["name"].strip(),
                    request.form["department"],
                    request.form["year"],
                    request.form["home_area"].strip(),
                    session["user_id"],
                ),
            )
            db.commit()
            flash("Profile updated.", "success")
        return render_template("profile.html", u=user())

    return app
