import sqlite3
import csv

DATABASE = 'attendance.db'
CSV_FILE = 'demo_attendance.csv'

def import_csv():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    with open(CSV_FILE, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows_imported = 0

        for row in reader:
            try:
                cursor.execute('''
                    INSERT INTO services 
                    (service_name, service_date, men, women, children, visitors, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    row['service_name'],
                    row['service_date'],
                    int(row['men']),
                    int(row['women']),
                    int(row['children']),
                    int(row['visitors']),
                    row['notes']
                ))
                rows_imported += 1
            except Exception as e:
                print(f'Skipped row: {row} — Reason: {e}')

    conn.commit()
    conn.close()
    print(f'✅ Done! {rows_imported} rows imported successfully.')

import_csv()



