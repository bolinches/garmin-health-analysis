# Garmin Health Analysis

> Talk to your Garmin data naturally. Activity splits, sleep, HRV, Body Battery, training readiness, and more.

**Forked from [eversonl/ClawdBot-garmin-health-analysis](https://github.com/eversonl/ClawdBot-garmin-health-analysis).** The original was a solid start but didn't cover what I needed — per-activity splits, auth resilience, extended metrics, and time-based queries. This version adds all of that. ALso original version seems to be outadated for over 6 months

---

## What's Different Here

| Feature | Original | This Fork |
|---------|----------|-----------|
| Activity splits (per-km/lap HR + pace) | ❌ | ✅ |
| Auth resilience (429 retry, token fallback, legacy migration) | ❌ | ✅ |
| Time-based queries ("what was my HR at 3pm?") | ❌ | ✅ |
| Extended metrics (VO2max, training readiness, endurance score) | ❌ | ✅ |
| FIT/GPX file download and analysis | ❌ | ✅ |
| Per-second activity detail queries | ❌ | ✅ |
| Interactive HTML dashboards | ❌ | ✅ |

## Installation

```bash
# Install via clawdhub
clawdhub install garmin-health-analysis

# Or manually
cd ~/.clawdbot/skills
git clone https://github.com/bolinches/garmin-health-analysis.git garmin-health-analysis
pip3 install garminconnect fitparse gpxpy
python3 scripts/garmin_auth.py login
```

Full setup guide in [SKILL.md](SKILL.md).

## What You Can Do

- "How did I sleep last night?" — sleep hours, stages, score
- "Show me my last run with splits" — per-km pace, HR, cadence
- "What's my recovery like this week?" — Body Battery, HRV, readiness
- "Is my VO2max improving?" — trend over time
- "Download the GPX for Sunday's run" — route data
- "What was my heart rate at 3pm yesterday?" — time-based queries

## What's Included

```
scripts/
├── garmin_auth.py              # Login, token refresh, credential resolution
├── garmin_data.py              # Core metrics: sleep, HRV, Body Battery, activities
├── garmin_data_extended.py     # VO2max, training readiness, endurance score
├── garmin_activity_files.py    # FIT/GPX download and analysis
├── garmin_query.py             # Time-based queries
└── garmin_chart.py             # HTML dashboard generation
```

## License

Apache 2.0. See [LICENSE](LICENSE).

## Credits

Original by EversonL. Extended by bolinches.
