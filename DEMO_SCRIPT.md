# GreenRoute Campus — 3-minute exhibition walkthrough

## 0:00–0:25 — Problem + landing page
“GreenRoute Campus turns a daily commute into a measurable decision. Instead of hiding cost, time, emissions and activity in separate places, the platform puts them on one screen and feeds the result into a campus feedback loop.”

Point out the **live stack**: routing, weather/AQI, SQLite and AI each have a fallback path.

## 0:25–1:05 — Live route comparison
Login as the demo student. Open **Plan**. Search **Gomti Nagar → BBDNITM**. Explain that OSRM can supply the road route and geometry; if it is unavailable, GreenRoute uses its transparent Haversine fallback. Click **Compare all modes** and sort by time, cost, activity or the comparative impact index.

Click **Ask AI about this route**. This carries the route distance into the AI page automatically.

## 1:05–1:40 — Real AI moment
On **AI Copilot**, type:

> I have ₹50 and need to reach campus in under 35 minutes with low emissions.

Set a sample distance such as 6 km and click **Ask AI**.

Explain the architecture plainly:
1. GreenRoute computes the transport candidates first.
2. When `OPENAI_API_KEY` is configured, the real cloud model receives the user request, recent conversation, distance, departure hour and weather/AQI context.
3. The model returns one candidate code and a short explanation.
4. GreenRoute validates the code, then uses its **own server-side numbers** for time, cost, CO₂ and activity.
5. If the cloud call fails, the local ML/scoring fallback keeps the feature usable.

The browser never receives the API key.

## 1:40–2:05 — Personal impact
Open **Impact**. Show CO₂ avoided, money saved, calories, points, level, badges and charts. Explain that the seeded demo includes 90 days of commute records so the dashboard looks like a living system rather than an empty mockup.

## 2:05–2:25 — Adaptive + social layer
Open **Smart** to show history-based recommendation plus weather/AQI. Then show **Carpool**, **Leaderboard** and **Challenges**. The point is to turn an individual travel decision into repeat behavior and campus participation.

## 2:25–3:00 — Admin evidence
Open **Admin** as `admin@greenroute.local / demo123`. Show totals, mode split, repeated routes, department patterns, CSV export and printable PDF. Close with:

> “The project is not just a sustainability score. It is a working mobility system: it helps a commuter decide, measures what happened, and turns repeated trips into evidence a campus can act on.”

# Likely judge questions

1. **Why Flask + SQLite?** — Fast local deployment, transparent schema and zero required paid infrastructure for the prototype.
2. **What happens without internet?** — Routing falls back to Haversine, weather/AQI fall back to safe defaults, and the database/analytics remain local.
3. **How does the AI differ from hardcoded if/else logic?** — The primary path uses a real cloud model for natural-language interpretation and candidate selection; the server constrains and validates the result.
4. **Can the AI invent the numbers?** — The UI displays numbers copied from GreenRoute's server-computed candidate table after the model selects a candidate.
5. **What happens if the API call fails?** — The local ML/scoring fallback is returned and the UI identifies that fallback.
6. **How trustworthy are the emission numbers?** — They are explicitly labeled educational estimates and are editable in the `transport_modes` table.
7. **Why Random Forest?** — The personalized recommender is separate from the cloud AI and learns from small historical behavior data such as trip distance and commute hour.
8. **How is carpooling modeled?** — The prototype divides vehicle emissions and cost across a shared passenger capacity; real institutional deployment would calibrate occupancy assumptions with measured data.
9. **How is security handled?** — Password hashing, sessions, CSRF protection, parameterized SQL, input validation, role checks and rate limits are included.
10. **What would come next?** — Verified campus shuttle schedules, better Indian-specific emission calibration, privacy-preserving aggregate heatmaps and institutional SSO.
