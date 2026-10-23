# Loom walkthrough — 7 minute script

Target 7:00. Record at 1600×1000 with the app already open and both servers running.
Have the trip preset **Nairobi → Mombasa** loaded and the plan already generated once
(so the second click is warm and the UI feels instant).

---

## 0:00 – 0:35 · What it is

> "This is a weather-aware truck routing app: React on the front, Django on the back.
> You give it two places, a departure time and a load weight. It returns three road routes,
> samples the hourly forecast along each one at the truck's *arrival* time, scores every
> checkpoint with the risk rules from the brief, and recommends the safest route."

Show the header: title, live-forecast pill, provider pill.

## 0:35 – 1:30 · Planning a trip

- Point at origin/destination, departure, the 10/25/50-mile selector.
- Drag the weight slider and read the hint underneath:
  > "The load rules are why this slider matters. Above 30,000 lb a 45–54 mph wind becomes
  > No Travel; above 40,000 lb a 35–44 mph wind becomes Severe."
- Click **Plan safest route**. While it loads, mention what it is doing:
  > "One request. The backend fetches three OSRM routes, samples them every 25 miles,
  > batches all those coordinates into a handful of Open-Meteo calls, and scores each one."

## 1:30 – 2:40 · Reading the result

- The recommendation card: read the first two bullets aloud.
  > "It ranks by fewest severe miles, then fewest high miles, then average risk, then time —
  > the order from the brief. Notice it picked the 8½ hour route over the 6 hour one, because
  > the fast route crosses more severe road."
- Point at a route card:
  > "Each card carries the risk mix as a bar, plus severe, high, no-travel miles and the
  > distance-weighted average risk."
- Click another route card — the map redraws around it. Mention the geometry swap is instant
  because all three routes arrive in the same response.

## 2:40 – 3:40 · Checkpoints and ETAs

- Click a checkpoint dot.
  > "Every checkpoint carries wind, rain, snow, temperature, the ETA it was sampled at, and
  > *why* it got its level — so a reviewer can audit the classification instead of trusting it."
- Point at two dots with the same city but different colours if visible:
  > "Same road, different hour, different risk — because the sample time tracks the truck."

## 3:40 – 5:00 · The 0–48 hour slider

- Enable **Corridor heat**, drag the slider slowly from 0 to 24.
  > "The heat map is the corridor, not the route line. Each cell is a stretch of road and the
  > colour is that stretch re-scored for a departure offset by `h` hours. At zero it matches
  > the checkpoint colours exactly — that's asserted in a test."
- Hit the play button for a few seconds.
  > "It's a canvas layer, so this is one repaint per frame, not sixty DOM nodes."
- If the corridor is calm, switch to **Storm demo** (labelled simulated) and re-plan:
  > "Real weather was mild today, so I built a labelled simulated system to exercise the
  > Severe and No Travel branches. Same code path, different provider."

## 5:00 – 5:50 · Weight sensitivity (the load rules)

- Edit trip → set weight to 18,000 → plan → compare the bars.
- Edit trip → set weight to 52,000 → plan.
  > "Same weather, different load. The rules escalate High into Severe and Severe into
  > No Travel exactly as specified — this is the part most implementations get wrong."

## 5:50 – 6:40 · Code tour

Open `backend/routing/services/risk.py`:

> "The risk model is a pure module with no Django imports. Thresholds as half-open buckets,
> the load rules applied afterwards, and a deliberate decision recorded in the docstring:
> where the brief writes a closed range the upper bound is inclusive, where it writes an open
> bound it isn't."

Open `backend/routing/tests/test_risk.py`:

> "Seventy-six tests. Every threshold probed from both sides — 54.9 is Severe, 55.0 is No Travel."

Open `planner.py` briefly:

> "The planner is the only place that knows the order of operations: routes, samples, one
> weather fetch for the union of every coordinate, then classify, aggregate, rank."

## 6:40 – 7:00 · Close

> "Repo has the README, the deploy configs for Render and Vercel, and the tests. If I had
> another day I'd self-host OSRM for latency and use per-segment speed annotations for the
> ETAs on mountain passes."

---

## Pre-flight checklist

- [ ] `backend`: `python manage.py runserver 8000` running
- [ ] `frontend`: `npm run dev` running, browser at `127.0.0.1:5173`
- [ ] One plan already generated (warm cache → sub-second re-plan)
- [ ] Zoom the map to the corridor before recording
- [ ] Close other tabs; hide the bookmarks bar
- [ ] Re-read the weight numbers so you say them correctly on camera

## Numbers to have ready

| Thing | Value |
| --- | --- |
| Tests | 76 passing |
| Cold plan | ~2–6 s (public OSRM), warm ~0.4 s |
| Payload | ~90 KB JSON, gzipped |
| Heat resolution | 25-mile cells × 49 hourly offsets |
| Checkpoint spacing options | 10 / 25 / 50 mi |
