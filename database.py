import sqlite3
from datetime import datetime, timedelta
from flask_bcrypt import Bcrypt

bcrypt = Bcrypt()

def get_db_connection():
    conn = sqlite3.connect('room_bookings.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS rooms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_id INTEGER,
            date TEXT,
            time_slot TEXT,
            user_name TEXT,
            password_hash TEXT,
            group_id TEXT,
            FOREIGN KEY (room_id) REFERENCES rooms (id)
        )
    ''')
    c.execute('SELECT COUNT(*) FROM rooms')
    if c.fetchone()[0] == 0:
        c.executemany('INSERT INTO rooms (name) VALUES (?)',
                     [('룸 1',), ('룸 2',), ('룸 3',)])
    conn.commit()
    conn.close()

def get_rooms():
    conn = get_db_connection()
    rooms = [{'id': row['id'], 'name': row['name']} for row in conn.execute('SELECT * FROM rooms').fetchall()]
    conn.close()
    return rooms

def get_bookings():
    conn = get_db_connection()
    bookings = [{'id': row['id'], 'room_id': row['room_id'], 'date': row['date'],
                 'time_slot': row['time_slot'], 'user_name': row['user_name'],
                 'group_id': row['group_id']}
                for row in conn.execute('SELECT * FROM bookings').fetchall()]
    conn.close()
    return bookings

def get_recent_bookings():
    conn = get_db_connection()
    one_month_ago = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    # 그룹화된 예약 조회
    c = conn.cursor()
    c.execute('''
        SELECT room_id, date, MIN(time_slot) as start_time, MAX(time_slot) as end_time, 
               user_name, group_id
        FROM bookings 
        WHERE date >= ?
        GROUP BY group_id
        ORDER BY date, start_time
    ''', (one_month_ago,))
    bookings = [{'room_id': row['room_id'], 'date': row['date'], 
                 'start_time': row['start_time'], 'end_time': row['end_time'], 
                 'user_name': row['user_name'], 'group_id': row['group_id']}
                for row in c.fetchall()]
    conn.close()
    return bookings

def book_room(room_id, date, time_slot, user_name, password, group_id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('SELECT * FROM bookings WHERE room_id = ? AND date = ? AND time_slot = ?',
              (room_id, date, time_slot))
    if c.fetchone():
        conn.close()
        return False
    password_hash = bcrypt.generate_password_hash(password).decode('utf-8')
    c.execute('INSERT INTO bookings (room_id, date, time_slot, user_name, password_hash, group_id) VALUES (?, ?, ?, ?, ?, ?)',
              (room_id, date, time_slot, user_name, password_hash, group_id))
    conn.commit()
    conn.close()
    return True

def cancel_booking(booking_id, password):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('SELECT password_hash, group_id FROM bookings WHERE id = ?', (booking_id,))
    booking = c.fetchone()
    if not booking:
        conn.close()
        return False, "예약을 찾을 수 없습니다."
    if not bcrypt.check_password_hash(booking['password_hash'], password):
        conn.close()
        return False, "비밀번호가 일치하지 않습니다."
    c.execute('DELETE FROM bookings WHERE group_id = ?', (booking['group_id'],))
    conn.commit()
    conn.close()
    return True, "예약이 취소되었습니다."
