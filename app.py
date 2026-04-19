from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import sqlite3, os, hashlib
import qrcode
import qrcode.image.svg
from io import BytesIO
import base64
from datetime import datetime, date

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'church-secret-key')

DATABASE = 'attendance.db'

# ── Helpers ──────────────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in.', 'error')
            return redirect(url_for('login'))
        if session.get('role') != 'admin':
            flash('Admin access required.', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated

# ── Database ─────────────────────────────────────────────────────

def init_db():
    conn = get_db()

    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            username   TEXT    UNIQUE NOT NULL,
            password   TEXT    NOT NULL,
            full_name  TEXT    NOT NULL,
            role       TEXT    NOT NULL DEFAULT 'staff',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conn.execute('''
        CREATE TABLE IF NOT EXISTS services (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            service_name    TEXT    NOT NULL,
            service_date    DATE    NOT NULL,
            service_type    TEXT    DEFAULT 'regular',
            is_holiday      INTEGER DEFAULT 0,
            men             INTEGER NOT NULL DEFAULT 0,
            women           INTEGER NOT NULL DEFAULT 0,
            children        INTEGER NOT NULL DEFAULT 0,
            visitors        INTEGER NOT NULL DEFAULT 0,
            first_timers    INTEGER NOT NULL DEFAULT 0,
            salvations      INTEGER NOT NULL DEFAULT 0,
            rededications   INTEGER NOT NULL DEFAULT 0,
            baptisms        INTEGER NOT NULL DEFAULT 0,
            notes           TEXT,
            archived_notes  TEXT,
            created_by      TEXT,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conn.execute('''
        CREATE TABLE IF NOT EXISTS service_types (
            id   INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        )
    ''')

    conn.execute('''
        CREATE TABLE IF NOT EXISTS ministry_events (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            service_id   INTEGER NOT NULL,
            event_type   TEXT    NOT NULL,
            person_name  TEXT,
            notes        TEXT,
            created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (service_id) REFERENCES services(id)
        )
    ''')

    conn.execute('''
        CREATE TABLE IF NOT EXISTS milestones (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            milestone_type TEXT    NOT NULL,
            description    TEXT    NOT NULL,
            milestone_date DATE    NOT NULL,
            notes          TEXT,
            created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conn.execute('''
        CREATE TABLE IF NOT EXISTS childrens_ministry (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            service_id   INTEGER,
            service_date DATE    NOT NULL,
            class_name   TEXT    NOT NULL,
            boys         INTEGER DEFAULT 0,
            girls        INTEGER DEFAULT 0,
            teachers     INTEGER DEFAULT 0,
            notes        TEXT,
            created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (service_id) REFERENCES services(id)
        )
    ''')

    conn.execute('''
        CREATE TABLE IF NOT EXISTS departments (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            department_name TEXT    NOT NULL,
            service_date    DATE    NOT NULL,
            service_id      INTEGER,
            members_present INTEGER DEFAULT 0,
            notes           TEXT,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (service_id) REFERENCES services(id)
        )
    ''')

    conn.execute('''
        CREATE TABLE IF NOT EXISTS church_profile (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            church_name  TEXT,
            pastor_name  TEXT,
            address      TEXT,
            city         TEXT,
            state        TEXT,
            zip_code     TEXT,
            phone        TEXT,
            email        TEXT,
            website      TEXT,
            founded_year TEXT,
            denomination TEXT,
            updated_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Default admin
    existing = conn.execute('SELECT COUNT(*) FROM users').fetchone()[0]
    if existing == 0:
        conn.execute(
            'INSERT INTO users (username, password, full_name, role) VALUES (?, ?, ?, ?)',
            ('admin', hash_password('admin123'), 'Administrator', 'admin')
        )

    # Default church profile
    profile = conn.execute('SELECT COUNT(*) FROM church_profile').fetchone()[0]
    if profile == 0:
        conn.execute(
            'INSERT INTO church_profile (church_name, pastor_name) VALUES (?, ?)',
            ('Living God International Christian Center', 'Pastor')
        )

    # Default service types
    for t in ['Sunday Service', 'Weekly Bible Study', 'Prayer Night', 'Youth Service']:
        try:
            conn.execute('INSERT INTO service_types (name) VALUES (?)', (t,))
        except:
            pass

    conn.commit()
    conn.close()

init_db()

# ── Login / Logout ────────────────────────────────────────────────

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        conn     = get_db()
        user     = conn.execute(
            'SELECT * FROM users WHERE username = ? AND password = ?',
            (username, hash_password(password))
        ).fetchone()
        conn.close()
        if user:
            session['user_id']   = user['id']
            session['username']  = user['username']
            session['full_name'] = user['full_name']
            session['role']      = user['role']
            flash(f'Welcome back, {user["full_name"]}!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password.', 'error')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))

# ── Dashboard ─────────────────────────────────────────────────────

@app.route('/', methods=['GET', 'POST'])
@login_required
def index():
    if request.method == 'POST':
        name           = request.form.get('service_name', '').strip()
        date           = request.form.get('service_date', '').strip()
        service_type   = request.form.get('service_type_tag', 'regular').strip()
        is_holiday     = 1 if request.form.get('is_holiday') else 0
        men            = int(request.form.get('men', 0) or 0)
        women          = int(request.form.get('women', 0) or 0)
        children       = int(request.form.get('children', 0) or 0)
        visitors       = int(request.form.get('visitors', 0) or 0)
        first_timers   = int(request.form.get('first_timers', 0) or 0)
        salvations     = int(request.form.get('salvations', 0) or 0)
        rededications  = int(request.form.get('rededications', 0) or 0)
        baptisms       = int(request.form.get('baptisms', 0) or 0)
        notes          = request.form.get('notes', '').strip()
        archived_notes = request.form.get('archived_notes', '').strip()

        if not name or not date:
            flash('Service name and date are required.', 'error')
            return redirect(url_for('index'))

        total  = men + women + children + visitors
        conn   = get_db()
        cursor = conn.execute('''
            INSERT INTO services
            (service_name, service_date, service_type, is_holiday,
             men, women, children, visitors, first_timers,
             salvations, rededications, baptisms,
             notes, archived_notes, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (name, date, service_type, is_holiday,
              men, women, children, visitors, first_timers,
              salvations, rededications, baptisms,
              notes, archived_notes, session['username']))

        service_id = cursor.lastrowid

        for name_entry in request.form.get('salvation_names', '').split('\n'):
            if name_entry.strip():
                conn.execute(
                    'INSERT INTO ministry_events (service_id, event_type, person_name) VALUES (?, ?, ?)',
                    (service_id, 'salvation', name_entry.strip())
                )
        for name_entry in request.form.get('rededication_names', '').split('\n'):
            if name_entry.strip():
                conn.execute(
                    'INSERT INTO ministry_events (service_id, event_type, person_name) VALUES (?, ?, ?)',
                    (service_id, 'rededication', name_entry.strip())
                )
        for name_entry in request.form.get('baptism_names', '').split('\n'):
            if name_entry.strip():
                conn.execute(
                    'INSERT INTO ministry_events (service_id, event_type, person_name) VALUES (?, ?, ?)',
                    (service_id, 'baptism', name_entry.strip())
                )

        conn.commit()
        conn.close()
        flash(f'Service recorded with {total} attendees!', 'success')
        return redirect(url_for('index'))

    conn               = get_db()
    total_services     = conn.execute('SELECT COUNT(*) FROM services').fetchone()[0]
    total_people       = conn.execute('SELECT COALESCE(SUM(men+women+children+visitors), 0) FROM services').fetchone()[0]
    avg_attendance     = conn.execute('SELECT COALESCE(AVG(men+women+children+visitors), 0) FROM services').fetchone()[0]
    highest            = conn.execute('SELECT MAX(men+women+children+visitors) FROM services').fetchone()[0] or 0
    total_salvations   = conn.execute('SELECT COALESCE(SUM(salvations), 0) FROM services').fetchone()[0]
    total_baptisms     = conn.execute('SELECT COALESCE(SUM(baptisms), 0) FROM services').fetchone()[0]
    total_first_timers = conn.execute('SELECT COALESCE(SUM(first_timers), 0) FROM services').fetchone()[0]
    recent             = conn.execute('SELECT * FROM services ORDER BY service_date DESC, id DESC LIMIT 5').fetchall()
    service_types      = conn.execute('SELECT name FROM service_types ORDER BY name').fetchall()
    profile            = conn.execute('SELECT * FROM church_profile LIMIT 1').fetchone()
    conn.close()

    return render_template('index.html',
        total_services=total_services,
        total_people=total_people,
        avg_attendance=round(avg_attendance),
        highest=highest,
        total_salvations=total_salvations,
        total_baptisms=total_baptisms,
        total_first_timers=total_first_timers,
        recent=recent,
        service_types=service_types,
        profile=profile
    )

# ── History ───────────────────────────────────────────────────────

@app.route('/history')
@login_required
def history():
    conn     = get_db()
    services = conn.execute('SELECT * FROM services ORDER BY service_date DESC, id DESC').fetchall()
    conn.close()
    return render_template('history.html', services=services)

# ── Delete ────────────────────────────────────────────────────────

@app.route('/delete/<int:service_id>', methods=['POST'])
@login_required
def delete(service_id):
    conn = get_db()
    s    = conn.execute('SELECT service_name FROM services WHERE id = ?', (service_id,)).fetchone()
    if s:
        conn.execute('DELETE FROM ministry_events WHERE service_id = ?', (service_id,))
        conn.execute('DELETE FROM services WHERE id = ?', (service_id,))
        conn.commit()
        flash(f'"{s["service_name"]}" deleted.', 'success')
    conn.close()
    return redirect(url_for('history'))

# ── Ministry ──────────────────────────────────────────────────────

@app.route('/ministry')
@login_required
def ministry():
    conn = get_db()

    summary = conn.execute('''
        SELECT
            COALESCE(SUM(salvations), 0)    as total_salvations,
            COALESCE(SUM(rededications), 0) as total_rededications,
            COALESCE(SUM(baptisms), 0)      as total_baptisms,
            COALESCE(SUM(first_timers), 0)  as total_first_timers
        FROM services
    ''').fetchone()

    ytd = conn.execute('''
        SELECT
            COALESCE(SUM(salvations), 0)    as ytd_salvations,
            COALESCE(SUM(rededications), 0) as ytd_rededications,
            COALESCE(SUM(baptisms), 0)      as ytd_baptisms,
            COALESCE(SUM(first_timers), 0)  as ytd_first_timers
        FROM services
        WHERE strftime('%Y', service_date) = strftime('%Y', 'now')
    ''').fetchone()

    recent_events = conn.execute('''
        SELECT s.service_name, s.service_date,
               s.salvations, s.rededications, s.baptisms, s.first_timers
        FROM services s
        WHERE s.salvations > 0 OR s.rededications > 0
              OR s.baptisms > 0 OR s.first_timers > 0
        ORDER BY s.service_date DESC LIMIT 10
    ''').fetchall()

    event_names = conn.execute('''
        SELECT me.event_type, me.person_name, me.created_at,
               s.service_name, s.service_date
        FROM ministry_events me
        JOIN services s ON me.service_id = s.id
        ORDER BY me.created_at DESC LIMIT 20
    ''').fetchall()

    monthly_ministry = list(reversed(conn.execute('''
        SELECT strftime('%Y-%m', service_date) as month,
               SUM(salvations)    as salvations,
               SUM(rededications) as rededications,
               SUM(baptisms)      as baptisms,
               SUM(first_timers)  as first_timers
        FROM services
        GROUP BY month ORDER BY month DESC LIMIT 12
    ''').fetchall()))

    milestones = conn.execute(
        'SELECT * FROM milestones ORDER BY milestone_date DESC'
    ).fetchall()

    children_records = conn.execute(
        'SELECT * FROM childrens_ministry ORDER BY service_date DESC LIMIT 10'
    ).fetchall()

    dept_records = conn.execute(
        'SELECT * FROM departments ORDER BY service_date DESC LIMIT 10'
    ).fetchall()

    conn.close()

    return render_template('ministry.html',
        summary=summary,
        ytd=ytd,
        recent_events=recent_events,
        event_names=event_names,
        monthly_ministry=monthly_ministry,
        milestones=milestones,
        children_records=children_records,
        dept_records=dept_records
    )

# ── Add Milestone ─────────────────────────────────────────────────

@app.route('/milestone/add', methods=['POST'])
@login_required
def add_milestone():
    milestone_type = request.form.get('milestone_type', '').strip()
    description    = request.form.get('description', '').strip()
    milestone_date = request.form.get('milestone_date', '').strip()
    notes          = request.form.get('notes', '').strip()
    if not milestone_type or not description or not milestone_date:
        flash('All milestone fields are required.', 'error')
        return redirect(url_for('ministry'))
    conn = get_db()
    conn.execute(
        'INSERT INTO milestones (milestone_type, description, milestone_date, notes) VALUES (?, ?, ?, ?)',
        (milestone_type, description, milestone_date, notes)
    )
    conn.commit()
    conn.close()
    flash('Milestone recorded!', 'success')
    return redirect(url_for('ministry'))

# ── Children Ministry ─────────────────────────────────────────────

@app.route('/children/add', methods=['POST'])
@login_required
def add_children_record():
    service_date = request.form.get('service_date', '').strip()
    class_name   = request.form.get('class_name', '').strip()
    boys         = int(request.form.get('boys', 0) or 0)
    girls        = int(request.form.get('girls', 0) or 0)
    teachers     = int(request.form.get('teachers', 0) or 0)
    notes        = request.form.get('notes', '').strip()
    conn = get_db()
    conn.execute(
        'INSERT INTO childrens_ministry (service_date, class_name, boys, girls, teachers, notes) VALUES (?, ?, ?, ?, ?, ?)',
        (service_date, class_name, boys, girls, teachers, notes)
    )
    conn.commit()
    conn.close()
    flash('Children\'s ministry record added!', 'success')
    return redirect(url_for('ministry'))

# ── Department Tracking ───────────────────────────────────────────

@app.route('/department/add', methods=['POST'])
@login_required
def add_department_record():
    dept_name    = request.form.get('department_name', '').strip()
    service_date = request.form.get('service_date', '').strip()
    members      = int(request.form.get('members_present', 0) or 0)
    notes        = request.form.get('notes', '').strip()
    conn = get_db()
    conn.execute(
        'INSERT INTO departments (department_name, service_date, members_present, notes) VALUES (?, ?, ?, ?)',
        (dept_name, service_date, members, notes)
    )
    conn.commit()
    conn.close()
    flash(f'Department record saved!', 'success')
    return redirect(url_for('ministry'))

# ── Church Profile ────────────────────────────────────────────────

@app.route('/profile/church', methods=['GET', 'POST'])
@admin_required
def church_profile():
    conn = get_db()
    if request.method == 'POST':
        conn.execute('''
            UPDATE church_profile SET
                church_name  = ?,
                pastor_name  = ?,
                address      = ?,
                city         = ?,
                state        = ?,
                zip_code     = ?,
                phone        = ?,
                email        = ?,
                website      = ?,
                founded_year = ?,
                denomination = ?,
                updated_at   = CURRENT_TIMESTAMP
            WHERE id = 1
        ''', (
            request.form.get('church_name', ''),
            request.form.get('pastor_name', ''),
            request.form.get('address', ''),
            request.form.get('city', ''),
            request.form.get('state', ''),
            request.form.get('zip_code', ''),
            request.form.get('phone', ''),
            request.form.get('email', ''),
            request.form.get('website', ''),
            request.form.get('founded_year', ''),
            request.form.get('denomination', '')
        ))
        conn.commit()
        flash('Church profile updated!', 'success')
        return redirect(url_for('church_profile'))
    profile = conn.execute('SELECT * FROM church_profile LIMIT 1').fetchone()
    conn.close()
    return render_template('church_profile.html', profile=profile)

# ── Reports ───────────────────────────────────────────────────────

@app.route('/reports')
@login_required
def reports():
    conn = get_db()

    monthly_rows = list(reversed(conn.execute('''
        SELECT strftime('%Y-%m', service_date) as month,
               COALESCE(SUM(men+women+children+visitors), 0) as total,
               COALESCE(SUM(men), 0)      as men,
               COALESCE(SUM(women), 0)    as women,
               COALESCE(SUM(children), 0) as children,
               COALESCE(SUM(visitors), 0) as visitors
        FROM services
        GROUP BY month ORDER BY month DESC LIMIT 12
    ''').fetchall()))

    monthly_labels   = [r['month'] for r in monthly_rows]
    monthly_totals   = [r['total'] for r in monthly_rows]
    monthly_men      = [r['men'] for r in monthly_rows]
    monthly_women    = [r['women'] for r in monthly_rows]
    monthly_children = [r['children'] for r in monthly_rows]
    monthly_visitors = [r['visitors'] for r in monthly_rows]

    service_rows = conn.execute('''
        SELECT service_name,
               COALESCE(SUM(men+women+children+visitors), 0) as total,
               COUNT(*) as service_count,
               CAST(ROUND(COALESCE(AVG(men+women+children+visitors), 0)) AS INTEGER) as avg_attendance
        FROM services GROUP BY service_name ORDER BY total DESC
    ''').fetchall()

    service_names  = [r['service_name'] for r in service_rows]
    service_totals = [r['total'] for r in service_rows]
    service_avgs   = [r['avg_attendance'] for r in service_rows]

    categories = conn.execute('''
        SELECT COALESCE(SUM(men), 0)      as total_men,
               COALESCE(SUM(women), 0)    as total_women,
               COALESCE(SUM(children), 0) as total_children,
               COALESCE(SUM(visitors), 0) as total_visitors
        FROM services
    ''').fetchone()

    ytd = conn.execute('''
        SELECT COALESCE(SUM(men+women+children+visitors), 0) as ytd_total,
               COUNT(*) as ytd_services,
               CAST(ROUND(COALESCE(AVG(men+women+children+visitors), 0)) AS INTEGER) as ytd_avg
        FROM services
        WHERE strftime('%Y', service_date) = strftime('%Y', 'now')
    ''').fetchone()

    record = conn.execute('''
        SELECT service_name, service_date, men+women+children+visitors as total
        FROM services ORDER BY total DESC LIMIT 1
    ''').fetchone()

    best_month = conn.execute('''
        SELECT strftime('%Y-%m', service_date) as month,
               SUM(men+women+children+visitors) as total
        FROM services GROUP BY month ORDER BY total DESC LIMIT 1
    ''').fetchone()

    visitor_rows = list(reversed(conn.execute('''
        SELECT strftime('%Y-%m', service_date) as month,
               COALESCE(SUM(visitors), 0) as visitors
        FROM services GROUP BY month ORDER BY month DESC LIMIT 12
    ''').fetchall()))

    visitor_labels = [r['month'] for r in visitor_rows]
    visitor_data   = [r['visitors'] for r in visitor_rows]

    conn.close()

    return render_template('reports.html',
        monthly_labels=monthly_labels,
        monthly_totals=monthly_totals,
        monthly_men=monthly_men,
        monthly_women=monthly_women,
        monthly_children=monthly_children,
        monthly_visitors=monthly_visitors,
        has_monthly=len(monthly_rows) > 0,
        service_rows=service_rows,
        service_names=service_names,
        service_totals=service_totals,
        service_avgs=service_avgs,
        has_services=len(service_rows) > 0,
        categories=categories,
        ytd=ytd,
        record=record,
        best_month=best_month,
        visitor_labels=visitor_labels,
        visitor_data=visitor_data,
        has_visitors=len(visitor_rows) > 0
    )

# ── Configuration ─────────────────────────────────────────────────

@app.route('/config', methods=['GET', 'POST'])
@admin_required
def config():
    conn = get_db()
    if request.method == 'POST':
        new_type = request.form.get('service_type', '').strip()
        if new_type:
            try:
                conn.execute('INSERT INTO service_types (name) VALUES (?)', (new_type,))
                conn.commit()
                flash(f'"{new_type}" added!', 'success')
            except:
                flash('That service type already exists!', 'error')
        conn.close()
        return redirect(url_for('config'))
    types = conn.execute('SELECT * FROM service_types ORDER BY name').fetchall()
    conn.close()
    return render_template('config.html', types=types)

@app.route('/config/delete/<int:type_id>', methods=['POST'])
@admin_required
def delete_service_type(type_id):
    conn = get_db()
    conn.execute('DELETE FROM service_types WHERE id=?', (type_id,))
    conn.commit()
    conn.close()
    flash('Service type removed.', 'success')
    return redirect(url_for('config'))

# ── Manage Users ──────────────────────────────────────────────────

@app.route('/users', methods=['GET', 'POST'])
@admin_required
def manage_users():
    conn = get_db()
    if request.method == 'POST':
        username  = request.form.get('username', '').strip()
        password  = request.form.get('password', '').strip()
        full_name = request.form.get('full_name', '').strip()
        role      = request.form.get('role', 'staff').strip()
        if not username or not password or not full_name:
            flash('All fields are required.', 'error')
            return redirect(url_for('manage_users'))
        try:
            conn.execute(
                'INSERT INTO users (username, password, full_name, role) VALUES (?, ?, ?, ?)',
                (username, hash_password(password), full_name, role)
            )
            conn.commit()
            flash(f'User "{username}" created!', 'success')
        except:
            flash('Username already exists.', 'error')
        conn.close()
        return redirect(url_for('manage_users'))
    users = conn.execute('SELECT * FROM users ORDER BY full_name').fetchall()
    conn.close()
    return render_template('manage_users.html', users=users)

@app.route('/users/delete/<int:user_id>', methods=['POST'])
@admin_required
def delete_user(user_id):
    if user_id == session['user_id']:
        flash('You cannot delete your own account.', 'error')
        return redirect(url_for('manage_users'))
    conn = get_db()
    conn.execute('DELETE FROM users WHERE id = ?', (user_id,))
    conn.commit()
    conn.close()
    flash('User deleted.', 'success')
    return redirect(url_for('manage_users'))

@app.route('/users/reset/<int:user_id>', methods=['POST'])
@admin_required
def reset_password(user_id):
    new_password = request.form.get('new_password', '').strip()
    if not new_password:
        flash('Password cannot be empty.', 'error')
        return redirect(url_for('manage_users'))
    conn = get_db()
    conn.execute('UPDATE users SET password = ? WHERE id = ?',
                (hash_password(new_password), user_id))
    conn.commit()
    conn.close()
    flash('Password reset successfully.', 'success')
    return redirect(url_for('manage_users'))

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    conn = get_db()
    if request.method == 'POST':
        current  = request.form.get('current_password', '').strip()
        new_pass = request.form.get('new_password', '').strip()
        confirm  = request.form.get('confirm_password', '').strip()
        user = conn.execute(
            'SELECT * FROM users WHERE id = ? AND password = ?',
            (session['user_id'], hash_password(current))
        ).fetchone()
        if not user:
            flash('Current password is incorrect.', 'error')
        elif new_pass != confirm:
            flash('New passwords do not match.', 'error')
        elif len(new_pass) < 6:
            flash('Password must be at least 6 characters.', 'error')
        else:
            conn.execute('UPDATE users SET password = ? WHERE id = ?',
                        (hash_password(new_pass), session['user_id']))
            conn.commit()
            flash('Password changed successfully!', 'success')
    conn.close()
    return render_template('profile.html')

# ── Visitor Form (Public — No Login) ─────────────────────────────

@app.route('/visitor', methods=['GET', 'POST'])
def visitor_form():
    conn = get_db()

    # Create visitors table if not exists
    conn.execute('''
        CREATE TABLE IF NOT EXISTS visitors (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name          TEXT NOT NULL,
            last_name           TEXT NOT NULL,
            phone               TEXT,
            email               TEXT,
            address             TEXT,
            heard_about_us      TEXT,
            first_time          INTEGER DEFAULT 1,
            service_attended    TEXT,
            visit_date          DATE,
            is_saved            INTEGER DEFAULT 0,
            wants_contact       INTEGER DEFAULT 1,
            ministry_interest   TEXT,
            prayer_request      TEXT,
            follow_up_status    TEXT DEFAULT 'pending',
            follow_up_notes     TEXT,
            follow_up_date      DATE,
            assigned_to         TEXT,
            created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()

    if request.method == 'POST':
        first_name       = request.form.get('first_name', '').strip()
        last_name        = request.form.get('last_name', '').strip()
        phone            = request.form.get('phone', '').strip()
        email            = request.form.get('email', '').strip()
        address          = request.form.get('address', '').strip()
        heard_about_us   = request.form.get('heard_about_us', '').strip()
        first_time       = 1 if request.form.get('first_time') == 'yes' else 0
        service_attended = request.form.get('service_attended', '').strip()
        visit_date       = request.form.get('visit_date', '').strip()
        is_saved         = 1 if request.form.get('is_saved') == 'yes' else 0
        wants_contact    = 1 if request.form.get('wants_contact') == 'yes' else 0
        ministry_interest = ','.join(request.form.getlist('ministry_interest'))
        prayer_request   = request.form.get('prayer_request', '').strip()

        if not first_name or not last_name:
            flash('First and last name are required.', 'error')
            return redirect(url_for('visitor_form'))

        conn.execute('''
            INSERT INTO visitors
            (first_name, last_name, phone, email, address,
             heard_about_us, first_time, service_attended, visit_date,
             is_saved, wants_contact, ministry_interest, prayer_request)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (first_name, last_name, phone, email, address,
              heard_about_us, first_time, service_attended, visit_date,
              is_saved, wants_contact, ministry_interest, prayer_request))
        conn.commit()
        conn.close()
        return redirect(url_for('visitor_thankyou'))

    service_types = conn.execute('SELECT name FROM service_types ORDER BY name').fetchall()
    profile       = conn.execute('SELECT * FROM church_profile LIMIT 1').fetchone()
    conn.close()
    return render_template('visitor_form.html',
        service_types=service_types,
        profile=profile,
        today=date.today().isoformat()
    )

@app.route('/visitor/thankyou')
def visitor_thankyou():
    return render_template('visitor_thankyou.html')

# ── Visitor Admin Dashboard ───────────────────────────────────────

@app.route('/visitors')
@login_required
def visitors():
    conn = get_db()

    conn.execute('''
        CREATE TABLE IF NOT EXISTS visitors (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name          TEXT NOT NULL,
            last_name           TEXT NOT NULL,
            phone               TEXT,
            email               TEXT,
            address             TEXT,
            heard_about_us      TEXT,
            first_time          INTEGER DEFAULT 1,
            service_attended    TEXT,
            visit_date          DATE,
            is_saved            INTEGER DEFAULT 0,
            wants_contact       INTEGER DEFAULT 1,
            ministry_interest   TEXT,
            prayer_request      TEXT,
            follow_up_status    TEXT DEFAULT 'pending',
            follow_up_notes     TEXT,
            follow_up_date      DATE,
            assigned_to         TEXT,
            created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()

    all_visitors = conn.execute(
        'SELECT * FROM visitors ORDER BY created_at DESC'
    ).fetchall()

    total_visitors  = len(all_visitors)
    pending_followup = conn.execute(
        "SELECT COUNT(*) FROM visitors WHERE follow_up_status = 'pending' AND wants_contact = 1"
    ).fetchone()[0]
    first_timers = conn.execute(
        'SELECT COUNT(*) FROM visitors WHERE first_time = 1'
    ).fetchone()[0]
    this_month = conn.execute(
        "SELECT COUNT(*) FROM visitors WHERE strftime('%Y-%m', created_at) = strftime('%Y-%m', 'now')"
    ).fetchone()[0]

    conn.close()
    return render_template('visitors.html',
        visitors=all_visitors,
        total_visitors=total_visitors,
        pending_followup=pending_followup,
        first_timers=first_timers,
        this_month=this_month
    )

@app.route('/visitors/followup/<int:visitor_id>', methods=['POST'])
@login_required
def update_followup(visitor_id):
    status     = request.form.get('follow_up_status', 'pending')
    notes      = request.form.get('follow_up_notes', '').strip()
    followup_date = request.form.get('follow_up_date', '').strip()
    assigned_to   = request.form.get('assigned_to', '').strip()

    conn = get_db()
    conn.execute('''
        UPDATE visitors SET
            follow_up_status = ?,
            follow_up_notes  = ?,
            follow_up_date   = ?,
            assigned_to      = ?
        WHERE id = ?
    ''', (status, notes, followup_date, assigned_to, visitor_id))
    conn.commit()
    conn.close()
    flash('Follow-up updated!', 'success')
    return redirect(url_for('visitors'))

@app.route('/visitors/delete/<int:visitor_id>', methods=['POST'])
@login_required
def delete_visitor(visitor_id):
    conn = get_db()
    conn.execute('DELETE FROM visitors WHERE id = ?', (visitor_id,))
    conn.commit()
    conn.close()
    flash('Visitor record deleted.', 'success')
    return redirect(url_for('visitors'))

@app.route('/visitors/export')
@login_required
def export_visitors():
    import csv
    from flask import Response
    conn     = get_db()
    visitors = conn.execute('SELECT * FROM visitors ORDER BY created_at DESC').fetchall()
    conn.close()

    def generate():
        headers = [
            'ID', 'First Name', 'Last Name', 'Phone', 'Email', 'Address',
            'Heard About Us', 'First Time', 'Service', 'Visit Date',
            'Saved', 'Wants Contact', 'Ministry Interest',
            'Prayer Request', 'Follow Up Status', 'Follow Up Notes',
            'Follow Up Date', 'Assigned To', 'Created At'
        ]
        yield ','.join(headers) + '\n'
        for v in visitors:
            row = [
                str(v['id']),
                v['first_name'] or '',
                v['last_name'] or '',
                v['phone'] or '',
                v['email'] or '',
                v['address'] or '',
                v['heard_about_us'] or '',
                'Yes' if v['first_time'] else 'No',
                v['service_attended'] or '',
                v['visit_date'] or '',
                'Yes' if v['is_saved'] else 'No',
                'Yes' if v['wants_contact'] else 'No',
                v['ministry_interest'] or '',
                v['prayer_request'] or '',
                v['follow_up_status'] or '',
                v['follow_up_notes'] or '',
                v['follow_up_date'] or '',
                v['assigned_to'] or '',
                v['created_at'] or ''
            ]
            yield ','.join(f'"{r}"' for r in row) + '\n'

    return Response(
        generate(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=visitors.csv'}
    )

# ── QR Code ──────────────────────────────────────────────────────

@app.route('/qrcode')
@login_required
def qr_code():
    host        = request.host_url
    visitor_url = f"{host}visitor"

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(visitor_url)
    qr.make(fit=True)

    img = qr.make_image(fill_color='#1976D2', back_color='white')

    buffer = BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    img_b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')

    return render_template('qr_code.html',
        qr_image=img_b64,
        visitor_url=visitor_url
    )

if __name__ == '__main__':
    app.run(debug=True)
