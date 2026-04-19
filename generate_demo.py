import sqlite3
import random
from datetime import date, timedelta

DATABASE = 'attendance.db'

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

# ── Service Types ─────────────────────────────────────────────────
SERVICE_TYPES = [
    'Sunday Service',
    'Weekly Bible Study',
    'Prayer Night',
    'Youth Service'
]

# ── Special Events ────────────────────────────────────────────────
SPECIAL_EVENTS = {
    # month, day : (name, tag, multiplier, is_holiday)
    (1, 1):   ('New Year Service',        'special',    2.2, 1),
    (3, 29):  ('Good Friday Service',     'special',    1.8, 1),
    (3, 31):  ('Easter Sunday',           'special',    2.8, 1),
    (4, 7):   ('Easter Follow Up',        'regular',    1.4, 0),
    (5, 12):  ('Mother\'s Day',           'special',    2.0, 1),
    (6, 16):  ('Father\'s Day',           'special',    1.7, 1),
    (7, 4):   ('Independence Day',        'special',    1.3, 1),
    (9, 1):   ('Back to School Sunday',   'special',    1.5, 0),
    (10, 31): ('Harvest Night',           'special',    1.6, 0),
    (11, 3):  ('Revival Sunday',          'revival',    2.0, 0),
    (11, 4):  ('Revival Monday',          'revival',    1.8, 0),
    (11, 5):  ('Revival Tuesday',         'revival',    1.7, 0),
    (11, 24): ('Thanksgiving Sunday',     'special',    1.5, 1),
    (12, 1):  ('First Sunday of Advent',  'special',    1.4, 0),
    (12, 15): ('Christmas Concert',       'special',    2.2, 0),
    (12, 22): ('Christmas Sunday',        'special',    2.5, 1),
    (12, 24): ('Christmas Eve Service',   'special',    2.3, 1),
    (12, 25): ('Christmas Day Service',   'special',    1.8, 1),
    (12, 29): ('Year End Sunday',         'special',    1.6, 0),
    (12, 31): ('New Year\'s Eve Service', 'special',    2.0, 1),
}

# ── Notes Pool ────────────────────────────────────────────────────
REGULAR_NOTES = [
    'Regular service',
    'Strong attendance',
    'Guest speaker',
    'Communion Sunday',
    'Worship night',
    'Youth led service',
    'Praise and worship',
    'Teaching series',
    'Prayer focus',
    'Evangelism Sunday',
    '',
    '',
    '',
]

# ── Base Attendance Ranges ────────────────────────────────────────
BASE_RANGES = {
    'Sunday Service':      (55, 85),
    'Weekly Bible Study':  (20, 40),
    'Prayer Night':        (15, 30),
    'Youth Service':       (25, 45),
}

# ── Growth Factor (church grows over 3 years) ────────────────────
def growth_factor(service_date, start_date):
    days = (service_date - start_date).days
    years = days / 365
    return 1 + (years * 0.18)  # 18% growth per year

# ── Generate Attendance ───────────────────────────────────────────
def generate_counts(base_min, base_max, multiplier, gf):
    total = int(random.randint(base_min, base_max) * multiplier * gf)
    total = max(total, 5)

    # Split into categories
    men_pct      = random.uniform(0.28, 0.35)
    women_pct    = random.uniform(0.32, 0.40)
    children_pct = random.uniform(0.12, 0.20)
    visitors_pct = random.uniform(0.05, 0.15)

    men      = max(1, int(total * men_pct))
    women    = max(1, int(total * women_pct))
    children = max(0, int(total * children_pct))
    visitors = max(0, int(total * visitors_pct))

    # Adjust to hit total
    diff = total - (men + women + children + visitors)
    women += diff

    return men, women, children, visitors

# ── Generate Ministry Numbers ─────────────────────────────────────
def generate_ministry(total, service_type, is_special):
    if service_type == 'Weekly Bible Study':
        first_timers  = random.randint(0, 2)
        salvations    = random.randint(0, 1) if is_special else 0
        rededications = random.randint(0, 1)
        baptisms      = 0
    elif is_special:
        first_timers  = random.randint(3, max(4, int(total * 0.12)))
        salvations    = random.randint(1, max(2, int(total * 0.06)))
        rededications = random.randint(1, max(2, int(total * 0.04)))
        baptisms      = random.randint(0, 3)
    else:
        first_timers  = random.randint(0, max(1, int(total * 0.05)))
        salvations    = random.randint(0, 2) if random.random() > 0.6 else 0
        rededications = random.randint(0, 1) if random.random() > 0.7 else 0
        baptisms      = 1 if random.random() > 0.92 else 0

    return first_timers, salvations, rededications, baptisms

# ── Build Schedule ────────────────────────────────────────────────
def build_schedule(start_date, end_date):
    schedule = []
    current  = start_date

    while current <= end_date:
        month = current.month
        day   = current.day
        key   = (month, day)

        # Check special event
        if key in SPECIAL_EVENTS:
            name, tag, mult, is_holiday = SPECIAL_EVENTS[key]
            schedule.append({
                'date':        current,
                'service':     name,
                'tag':         tag,
                'multiplier':  mult,
                'is_holiday':  is_holiday,
                'is_special':  True,
                'base_service': 'Sunday Service'
            })

        # Sunday Service
        elif current.weekday() == 6:  # Sunday
            schedule.append({
                'date':        current,
                'service':     'Sunday Service',
                'tag':         'regular',
                'multiplier':  1.0,
                'is_holiday':  0,
                'is_special':  False,
                'base_service': 'Sunday Service'
            })

        # Wednesday Bible Study
        elif current.weekday() == 2:  # Wednesday
            schedule.append({
                'date':        current,
                'service':     'Weekly Bible Study',
                'tag':         'regular',
                'multiplier':  1.0,
                'is_holiday':  0,
                'is_special':  False,
                'base_service': 'Weekly Bible Study'
            })

        # Friday Prayer Night (every other week)
        elif current.weekday() == 4 and current.isocalendar()[1] % 2 == 0:
            schedule.append({
                'date':        current,
                'service':     'Prayer Night',
                'tag':         'regular',
                'multiplier':  1.0,
                'is_holiday':  0,
                'is_special':  False,
                'base_service': 'Prayer Night'
            })

        # Youth Service (2nd and 4th Saturday)
        elif current.weekday() == 5:
            week_num = (day - 1) // 7 + 1
            if week_num in [2, 4]:
                schedule.append({
                    'date':        current,
                    'service':     'Youth Service',
                    'tag':         'regular',
                    'multiplier':  1.0,
                    'is_holiday':  0,
                    'is_special':  False,
                    'base_service': 'Youth Service'
                })

        current += timedelta(days=1)

    return schedule

# ── Main Import ───────────────────────────────────────────────────
def generate_demo():
    conn       = get_db()
    start_date = date(2023, 1, 1)
    end_date   = date(2025, 12, 31)
    schedule   = build_schedule(start_date, end_date)

    # Limit to 500 records
    if len(schedule) > 500:
        # Keep all special events + sample the rest
        specials = [s for s in schedule if s['is_special']]
        regulars = [s for s in schedule if not s['is_special']]
        remaining = 500 - len(specials)
        regulars_sampled = random.sample(regulars, min(remaining, len(regulars)))
        schedule = sorted(specials + regulars_sampled, key=lambda x: x['date'])

    print(f'Generating {len(schedule)} service records...')

    # Clear existing data
    conn.execute('DELETE FROM services')
    conn.execute('DELETE FROM ministry_events')
    conn.commit()

    inserted = 0

    for item in schedule:
        svc_date    = item['date'].isoformat()
        svc_name    = item['service']
        svc_tag     = item['tag']
        is_holiday  = item['is_holiday']
        is_special  = item['is_special']
        base_svc    = item['base_service']
        multiplier  = item['multiplier']

        # Growth factor
        gf = growth_factor(item['date'], start_date)

        # Get base range
        base_min, base_max = BASE_RANGES.get(base_svc, (40, 70))

        # Generate counts
        men, women, children, visitors = generate_counts(
            base_min, base_max, multiplier, gf
        )
        total = men + women + children + visitors

        # Generate ministry numbers
        first_timers, salvations, rededications, baptisms = generate_ministry(
            total, svc_name, is_special
        )

        # Notes
        if is_special:
            notes = svc_name
        else:
            notes = random.choice(REGULAR_NOTES)

        # Insert service
        cursor = conn.execute('''
            INSERT INTO services
            (service_name, service_date, service_type, is_holiday,
             men, women, children, visitors,
             first_timers, salvations, rededications, baptisms,
             notes, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            svc_name, svc_date, svc_tag, is_holiday,
            men, women, children, visitors,
            first_timers, salvations, rededications, baptisms,
            notes, 'demo_import'
        ))

        service_id = cursor.lastrowid

        # Insert individual salvation names for special events
        if salvations > 0 and is_special:
            names = [
                'James Wilson', 'Maria Garcia', 'David Johnson',
                'Sarah Brown', 'Michael Davis', 'Jennifer Martinez',
                'Robert Taylor', 'Lisa Anderson', 'William Thomas',
                'Patricia Jackson', 'Charles White', 'Barbara Harris',
                'Joseph Martin', 'Susan Thompson', 'Richard Garcia',
                'Jessica Martinez', 'Daniel Robinson', 'Nancy Clark',
                'Matthew Rodriguez', 'Karen Lewis'
            ]
            for i in range(min(salvations, len(names))):
                conn.execute(
                    'INSERT INTO ministry_events (service_id, event_type, person_name) VALUES (?, ?, ?)',
                    (service_id, 'salvation', random.choice(names))
                )

        # Insert baptism names
        if baptisms > 0:
            baptism_names = [
                'Anthony Moore', 'Michelle Lee', 'Kevin Walker',
                'Amanda Hall', 'Brian Allen', 'Stephanie Young',
                'Ronald King', 'Carolyn Wright', 'Timothy Scott',
                'Sharon Green'
            ]
            for i in range(min(baptisms, len(baptism_names))):
                conn.execute(
                    'INSERT INTO ministry_events (service_id, event_type, person_name) VALUES (?, ?, ?)',
                    (service_id, 'baptism', random.choice(baptism_names))
                )

        inserted += 1

    conn.commit()
    conn.close()

    print(f'')
    print(f'✅ Done! {inserted} records inserted.')
    print(f'')
    print(f'📊 Summary:')
    print(f'   Date range: {start_date} to {end_date}')
    print(f'   Special events: Easter, Christmas, New Year, Mother\'s Day, etc.')
    print(f'   Growth: ~18% per year')
    print(f'   Service types: Sunday, Bible Study, Prayer Night, Youth')
    print(f'')
    print(f'🚀 Open [localhost](http://localhost:5000) to see your data!')

generate_demo()
