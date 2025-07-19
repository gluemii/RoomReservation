from flask import Flask, render_template, request, redirect, url_for, flash
from flask_bcrypt import Bcrypt
from database import init_db, get_rooms, get_bookings, book_room, cancel_booking, get_recent_bookings
from datetime import datetime, timedelta
import uuid

app = Flask(__name__)
app.secret_key = 'your-secret-key'
bcrypt = Bcrypt(app)

# 데이터베이스 초기화
init_db()

# 주간 캘린더 날짜 생성 (페이지네이션 지원)
def generate_week_dates(week_offset=0):
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    start_date = today + timedelta(weeks=week_offset)
    return [start_date + timedelta(days=i) for i in range(7)]

def generate_time_slots():
    start_time = datetime.strptime("08:00", "%H:%M").time()
    end_time = datetime.strptime("22:00", "%H:%M").time()
    slots = []
    current = start_time
    while current <= end_time:
        slots.append(current.strftime("%H:%M"))
        current = (datetime.combine(datetime.today(), current) + timedelta(minutes=30)).time()
    return slots

@app.route('/')
def index():
    week_offset = int(request.args.get('week_offset', 0))
    if week_offset < 0 or week_offset > 16:
        flash('캘린더 범위를 벗어났습니다.', 'danger')
        week_offset = 0
    
    rooms = get_rooms()
    week_dates = generate_week_dates(week_offset)
    time_slots = generate_time_slots()
    bookings = get_bookings()
    
    calendar = {}
    for room in rooms:
        calendar[room['id']] = {}
        for date in week_dates:
            date_str = date.strftime("%Y-%m-%d")
            calendar[room['id']][date_str] = {}
            for slot in time_slots:
                calendar[room['id']][date_str][slot] = None
                for booking in bookings:
                    booking_date = datetime.strptime(booking['date'], "%Y-%m-%d").date()
                    if (booking['room_id'] == room['id'] and 
                        booking_date == date.date() and 
                        booking['time_slot'] == slot):
                        calendar[room['id']][date_str][slot] = booking
    
    return render_template('index.html', rooms=rooms, week_dates=week_dates, 
                         time_slots=time_slots, calendar=calendar, week_offset=week_offset)

@app.route('/book', methods=['GET', 'POST'])
def book():
    if request.method == 'POST':
        room_id = int(request.form['room_id'])
        date = request.form['date']
        start_time = request.form['start_time']
        end_time = request.form['end_time']
        user_name = request.form['user_name']
        password = request.form['password']
        
        time_slots = generate_time_slots()
        if start_time not in time_slots or end_time not in time_slots:
            flash('유효하지 않은 시간 슬롯입니다.', 'danger')
            return redirect(url_for('book'))
        
        start_dt = datetime.strptime(start_time, "%H:%M")
        end_dt = datetime.strptime(end_time, "%H:%M")
        if start_dt >= end_dt:
            flash('종료 시간은 시작 시간보다 늦어야 합니다.', 'danger')
            return redirect(url_for('book'))
        
        group_id = str(uuid.uuid4())
        slots_to_book = []
        current = start_dt
        while current <= end_dt:
            slots_to_book.append(current.strftime("%H:%M"))
            current = current + timedelta(minutes=30)
        
        success = True
        for slot in slots_to_book:
            if not book_room(room_id, date, slot, user_name, password, group_id):
                success = False
                break
        
        if success:
            flash('예약이 완료되었습니다!', 'success')
        else:
            flash('선택한 시간대 중 일부가 이미 예약되어 있습니다.', 'danger')
        return redirect(url_for('index'))
    
    rooms = get_rooms()
    week_dates = []
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    for i in range(16 * 7):
        week_dates.append(today + timedelta(days=i))
    time_slots = generate_time_slots()
    return render_template('book.html', rooms=rooms, week_dates=week_dates, time_slots=time_slots)

@app.route('/cancel/<int:booking_id>', methods=['GET', 'POST'])
def cancel(booking_id):
    if request.method == 'POST':
        password = request.form['password']
        success, message = cancel_booking(booking_id, password)
        flash(message, 'success' if success else 'danger')
        return redirect(url_for('index'))
    
    return render_template('cancel.html', booking_id=booking_id)

@app.route('/report')
def report():
    rooms = get_rooms()
    bookings = get_recent_bookings()
    return render_template('report.html', bookings=bookings, rooms=rooms)

if __name__ == '__main__':
    app.run(debug=True)
