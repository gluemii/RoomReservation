요청하신 기능을 구현하기 위해 기존 코드를 수정하겠습니다. 다음 요구사항을 반영합니다:

1. **연속 슬롯 일괄 취소**: 연속적으로 예약된 슬롯을 한 번에 취소할 수 있도록, 예약 시 그룹 ID를 추가해 연속 예약을 관리.
2. **종료 시간 드롭다운 제한**: 예약 폼에서 시작 시간을 선택하면 종료 시간 드롭다운이 시작 시간 이후로 제한되도록 JavaScript 추가.
3. **최근 1개월 예약 리포트**: 최근 1개월간의 예약을 리스트 형식으로 표시하는 페이지와 버튼 추가.

### 구현 개요
- **데이터베이스**:
  - `bookings` 테이블에 `group_id` 컬럼을 추가해 연속 예약을 그룹화.
  - `cancel_booking` 함수를 수정해 동일 `group_id`의 모든 예약을 한 번에 삭제.
- **예약 폼**:
  - `book.html`에 JavaScript를 추가해 시작 시간 선택 시 종료 시간 드롭다운을 동적으로 제한.
- **리포트 페이지**:
  - 새로운 `/report` 라우트와 `report.html` 템플릿을 추가해 최근 1개월 예약을 리스트로 표시.
  - `index.html`에 리포트 페이지로 이동하는 버튼 추가.
- **UI/기능**:
  - 취소 시 동일 그룹의 모든 슬롯을 삭제하도록 `cancel.html`과 로직 수정.
  - 캘린더와 예약/취소 기능은 기존 유지.

---

### 프로젝트 구조 (업데이트)
```
room_booking_app/
├── app.py
├── database.py
├── templates/
│   ├── index.html
│   ├── book.html
│   ├── cancel.html
│   ├── report.html  # 신규
├── static/
│   └── style.css
└── room_bookings.db
```

---

### 1. `app.py` (수정)
- `/report` 라우트 추가.
- `book` 라우트에서 연속 슬롯 예약 시 `group_id` 생성.
- `generate_week_dates`와 `generate_time_slots`는 기존 유지.

```python
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
        
        # 연속 슬롯 생성 및 그룹 ID 생성
        group_id = str(uuid.uuid4())
        slots_to_book = []
        current = start_dt
        while current <= end_dt:
            slots_to_book.append(current.strftime("%H:%M"))
            current = current + timedelta(minutes=30)
        
        # 모든 슬롯 예약 시도
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
    for i in range(16 * 7):  # 4개월 ≈ 16주
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
    bookings = get_recent_bookings()
    return render_template('report.html', bookings=bookings)

if __name__ == '__main__':
    app.run(debug=True)
```

---

### 2. `database.py` (수정)
- `bookings` 테이블에 `group_id` 컬럼 추가.
- `book_room`에 `group_id` 매개변수 추가.
- `cancel_booking`을 수정해 동일 `group_id`의 모든 예약 삭제.
- `get_recent_bookings` 함수 추가.

```python
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
    bookings = [{'id': row['id'], 'room_id': row['room_id'], 'date': row['date'],
                 'time_slot': row['time_slot'], 'user_name': row['user_name'],
                 'group_id': row['group_id']}
                for row in conn.execute('SELECT * FROM bookings WHERE date >= ? ORDER BY date, time_slot',
                                       (one_month_ago,)).fetchall()]
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
    # 동일 group_id의 모든 예약 삭제
    c.execute('DELETE FROM bookings WHERE group_id = ?', (booking['group_id'],))
    conn.commit()
    conn.close()
    return True, "예약이 취소되었습니다."
```

---

### 3. `templates/index.html` (수정)
- 리포트 페이지로 이동하는 버튼 추가.

```html
<!DOCTYPE html>
<html>
<head>
    <title>룸 예약 관리</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="{{ url_for('static', filename='style.css') }}">
</head>
<body>
    <div class="container">
        <h1 class="my-4">룸 예약 관리</h1>
        <div class="d-flex justify-content-between mb-3">
            <a href="{{ url_for('index', week_offset=week_offset-1) }}" 
               class="btn btn-secondary {% if week_offset <= 0 %}disabled{% endif %}">이전 주</a>
            <div>
                <a href="{{ url_for('book') }}" class="btn btn-primary">예약하기</a>
                <a href="{{ url_for('report') }}" class="btn btn-info">예약 리포트</a>
            </div>
            <a href="{{ url_for('index', week_offset=week_offset+1) }}" 
               class="btn btn-secondary {% if week_offset >= 16 %}disabled{% endif %}">다음 주</a>
        </div>
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="alert alert-{{ category }}">{{ message }}</div>
                {% endfor %}
            {% endif %}
        {% endwith %}
        {% for room in rooms %}
            <h3>{{ room.name }}</h3>
            <table class="table table-bordered">
                <thead>
                    <tr>
                        <th>시간</th>
                        {% for date in week_dates %}
                            <th>{{ date.strftime('%Y-%m-%d') }} ({{ ['월', '화', '수', '목', '금', '토', '일'][date.weekday()] }})</th>
                        {% endfor %}
                    </tr>
                </thead>
                <tbody>
                    {% for slot in time_slots %}
                        <tr>
                            <td>{{ slot }}</td>
                            {% for date in week_dates %}
                                <td>
                                    {% set booking = calendar[room.id][date.strftime('%Y-%m-%d')][slot] %}
                                    {% if booking %}
                                        {{ booking.user_name }} 
                                        <a href="{{ url_for('cancel', booking_id=booking.id) }}" 
                                           class="btn btn-sm btn-danger">취소</a>
                                    {% else %}
                                        비어 있음
                                    {% endif %}
                                </td>
                            {% endfor %}
                        </tr>
                    {% endfor %}
                </tbody>
            </table>
        {% endfor %}
    </div>
</body>
</html>
```

---

### 4. `templates/book.html` (수정)
- JavaScript로 시작 시간 선택 시 종료 시간 드롭다운 제한.

```html
<!DOCTYPE html>
<html>
<head>
    <title>예약하기</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="{{ url_for('static', filename='style.css') }}">
</head>
<body>
    <div class="container">
        <h1 class="my-4">예약하기</h1>
        <a href="{{ url_for('index') }}" class="btn btn-secondary mb-3">돌아가기</a>
        <form method="POST">
            <div class="mb-3">
                <label for="room_id" class="form-label">룸 선택</label>
                <select name="room_id" class="form-select" required>
                    {% for room in rooms %}
                        <option value="{{ room.id }}">{{ room.name }}</option>
                    {% endfor %}
                </select>
            </div>
            <div class="mb-3">
                <label for="date" class="form-label">날짜</label>
                <select name="date" class="form-select" required>
                    {% for date in week_dates %}
                        <option value="{{ date.strftime('%Y-%m-%d') }}">{{ date.strftime('%Y-%m-%d') }}</option>
                    {% endfor %}
                </select>
            </div>
            <div class="mb-3">
                <label for="start_time" class="form-label">시작 시간</label>
                <select name="start_time" id="start_time" class="form-select" required>
                    {% for slot in time_slots %}
                        <option value="{{ slot }}">{{ slot }}</option>
                    {% endfor %}
                </select>
            </div>
            <div class="mb-3">
                <label for="end_time" class="form-label">종료 시간</label>
                <select name="end_time" id="end_time" class="form-select" required>
                    {% for slot in time_slots %}
                        <option value="{{ slot }}">{{ slot }}</option>
                    {% endfor %}
                </select>
            </div>
            <div class="mb-3">
                <label for="user_name" class="form-label">예약자 이름</label>
                <input type="text" name="user_name" class="form-control" required>
            </div>
            <div class="mb-3">
                <label for="password" class="form-label">비밀번호</label>
                <input type="password" name="password" class="form-control" required>
            </div>
            <button type="submit" class="btn btn-primary">예약</button>
        </form>
    </div>
    <script>
        const startTimeSelect = document.getElementById('start_time');
        const endTimeSelect = document.getElementById('end_time');
        const timeSlots = {{ time_slots | tojson }};

        startTimeSelect.addEventListener('change', () => {
            const selectedStartTime = startTimeSelect.value;
            const startIndex = timeSlots.indexOf(selectedStartTime);
            endTimeSelect.innerHTML = '';
            for (let i = startIndex + 1; i < timeSlots.length; i++) {
                const option = document.createElement('option');
                option.value = timeSlots[i];
                option.text = timeSlots[i];
                endTimeSelect.appendChild(option);
            }
        });

        // 초기 로드 시 종료 시간 업데이트
        const initialStartTime = startTimeSelect.value;
        const startIndex = timeSlots.indexOf(initialStartTime);
        endTimeSelect.innerHTML = '';
        for (let i = startIndex + 1; i < timeSlots.length; i++) {
            const option = document.createElement('option');
            option.value = timeSlots[i];
            option.text = timeSlots[i];
            endTimeSelect.appendChild(option);
        }
    </script>
</body>
</html>
```

---

### 5. `templates/cancel.html` (수정)
- 취소 메시지를 "연속 예약 취소"로 변경.

```html
<!DOCTYPE html>
<html>
<head>
    <title>예약 취소</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="{{ url_for('static', filename='style.css') }}">
</head>
<body>
    <div class="container">
        <h1 class="my-4">예약 취소</h1>
        <a href="{{ url_for('index') }}" class="btn btn-secondary mb-3">돌아가기</a>
        <form method="POST">
            <div class="mb-3">
                <label for="password" class="form-label">예약 시 설정한 비밀번호</label>
                <input type="password" name="password" class="form-control" required>
            </div>
            <button type="submit" class="btn btn-danger">연속 예약 취소</button>
        </form>
    </div>
</body>
</html>
```

---

### 6. `templates/report.html` (신규)
- 최근 1개월 예약을 리스트로 표시.

```html
<!DOCTYPE html>
<html>
<head>
    <title>예약 리포트</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="{{ url_for('static', filename='style.css') }}">
</head>
<body>
    <div class="container">
        <h1 class="my-4">최근 1개월 예약 리포트</h1>
        <a href="{{ url_for('index') }}" class="btn btn-secondary mb-3">돌아가기</a>
        {% if bookings %}
            <table class="table table-bordered">
                <thead>
                    <tr>
                        <th>룸 ID</th>
                        <th>날짜</th>
                        <th>시간</th>
                        <th>예약자</th>
                        <th>그룹 ID</th>
                    </tr>
                </thead>
                <tbody>
                    {% for booking in bookings %}
                        <tr>
                            <td>{{ booking.room_id }}</td>
                            <td>{{ booking.date }}</td>
                            <td>{{ booking.time_slot }}</td>
                            <td>{{ booking.user_name }}</td>
                            <td>{{ booking.group_id }}</td>
                        </tr>
                    {% endfor %}
                </tbody>
            </table>
        {% else %}
            <p>최근 1개월 동안 예약이 없습니다.</p>
        {% endif %}
    </div>
</body>
</html>
```

---

### 7. `static/style.css` (수정)
- 리포트 테이블 스타일링 추가.

```css
body {
    background-color: #f8f9fa;
}
.table {
    background-color: white;
}
.alert {
    margin-top: 10px;
}
.d-flex {
    align-items: center;
}
.btn-secondary:disabled {
    opacity: 0.5;
}
.btn-info {
    margin-left: 10px;
}
```

---

### 실행 방법
1. **패키지 설치**:
   ```bash
   pip install flask flask-bcrypt
   ```

2. **데이터베이스 재설정**:
   - `group_id` 컬럼 추가로 인해 기존 `room_bookings.db`를 삭제해야 함:
     ```bash
     del room_bookings.db  # Windows
     python app.py
     ```

3. **애플리케이션 실행**:
   ```bash
   python app.py
   ```
   - 브라우저에서 `http://127.0.0.1:5000` 접속.

---

### 추가 기능 설명
- **연속 슬롯 일괄 취소**:
  - 예약 시 `group_id` (UUID)를 생성해 연속 슬롯을 그룹화.
  - 취소 시 `group_id`로 동일 그룹의 모든 슬롯을 한 번에 삭제.
- **종료 시간 드롭다운 제한**:
  - JavaScript로 시작 시간 선택 시 종료 시간 옵션을 시작 시간 이후로 동적으로 제한.
  - 페이지 로드 시 초기 시작 시간에 맞춰 종료 시간 업데이트.
- **최근 1개월 리포트**:
  - `/report` 페이지에서 최근 1개월 예약을 테이블로 표시(룸 ID, 날짜, 시간, 예약자, 그룹 ID).
  - `index.html`에 "예약 리포트" 버튼 추가.
- **기존 기능 유지**:
  - 4개월 캘린더, 페이지네이션, 비밀번호 기반 예약/취소 유지.

---

### 추가 개발 검토
- **리포트 개선**:
  - 리포트에 필터(예: 룸별, 날짜 범위)나 정렬 옵션 .
- **UI 개선**:
  - 종료 시간 드롭다운이 JavaScript로 동적 업데이트되지만, 성능 최적화나 UX 개선(예: 로딩 표시) 
- **보안**:
  - 비밀번호는 Bcrypt로 보안,  CSRF 토큰, HTTPS 등 추가 보안 개발필요.
- **확장 가능성**:
  - 연속 예약 시 최대 슬롯 제한 설정(예: 최대 4시간)에 대한 수정 검토
  - 룸 3개 예약되나  룸이름 변경, 룸 갯수 조정등 관리 기능 추가 검토


