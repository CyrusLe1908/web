# app.py
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import os
import datetime

app = Flask(__name__)
app.secret_key = 'your_secret_key_here' # Thay thế bằng một khóa bí mật mạnh hơn trong môi trường sản phẩm

# Đường dẫn đến cơ sở dữ liệu SQLite
DATABASE = 'database.db'

def get_db_connection():
    """Tạo kết nối đến cơ sở dữ liệu."""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row # Cho phép truy cập các cột bằng tên
    return conn

def init_db():
    """Khởi tạo cơ sở dữ liệu và tạo bảng người dùng và bảng chấm công."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        # Tạo bảng users nếu chưa tồn tại
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                is_admin BOOLEAN NOT NULL DEFAULT 0
            )
        ''')
        # Tạo bảng attendance nếu chưa tồn tại
        # Cập nhật schema: clock_in_time, clock_out_time, duration_minutes
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                clock_in_time TEXT NOT NULL,
                clock_out_time TEXT, -- NULL nếu đang online
                duration_minutes REAL, -- NULL nếu đang online, tính toán khi tan ca
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        # Kiểm tra nếu chưa có người dùng nào, tạo người dùng admin đầu tiên
        cursor.execute("SELECT COUNT(*) FROM users")
        if cursor.fetchone()[0] == 0:
            admin_username = "admin"
            admin_password_hash = generate_password_hash("adminpass") # Mật khẩu mặc định cho admin đầu tiên
            cursor.execute("INSERT INTO users (username, password, is_admin) VALUES (?, ?, ?)",
                           (admin_username, admin_password_hash, True))
            conn.commit()
            print(f"Người dùng quản trị '{admin_username}' đã được tạo với mật khẩu 'adminpass'.")
        conn.commit()

# Hàm tiện ích để định dạng phút thành HH:MM
def format_minutes_to_hhmm(minutes):
    if minutes is None:
        return "N/A"
    total_seconds = int(minutes * 60)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    return f"{hours:02d}h {minutes:02d}m"

# Khởi tạo cơ sở dữ liệu khi ứng dụng bắt đầu
with app.app_context():
    init_db()

@app.route('/')
def index():
    """Chuyển hướng đến trang đăng nhập."""
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Xử lý đăng nhập người dùng."""
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()

        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['is_admin'] = bool(user['is_admin'])
            flash('Đăng nhập thành công!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Tên đăng nhập hoặc mật khẩu không đúng.', 'danger')
    return render_template('index.html')

@app.route('/dashboard')
def dashboard():
    """Hiển thị trang quản lý hoặc trang người dùng."""
    if 'user_id' not in session:
        flash('Vui lòng đăng nhập để truy cập trang này.', 'warning')
        return redirect(url_for('login'))

    conn = get_db_connection()
    current_user_id = session['user_id']
    
    # Lấy trạng thái chấm công gần nhất của người dùng hiện tại
    current_user_last_attendance = conn.execute(
        'SELECT clock_out_time FROM attendance WHERE user_id = ? ORDER BY clock_in_time DESC LIMIT 1',
        (current_user_id,)
    ).fetchone()
    # Nếu clock_out_time là NULL, nghĩa là đang online
    current_user_status = 'online' if current_user_last_attendance and current_user_last_attendance['clock_out_time'] is None else 'offline'

    users_data = []
    if session.get('is_admin'):
        all_users = conn.execute('SELECT id, username, is_admin FROM users ORDER BY username ASC').fetchall()
        
        for user in all_users:
            user_dict = dict(user) # Chuyển Row thành dict để dễ dàng thêm trường mới
            
            # Lấy trạng thái online/offline hiện tại
            last_session = conn.execute(
                'SELECT clock_out_time, clock_in_time FROM attendance WHERE user_id = ? ORDER BY clock_in_time DESC LIMIT 1',
                (user['id'],)
            ).fetchone()
            
            user_dict['current_status'] = 'online' if last_session and last_session['clock_out_time'] is None else 'offline'
            
            # Tính tổng thời gian online
            total_online_minutes = 0.0
            completed_sessions = conn.execute(
                'SELECT duration_minutes FROM attendance WHERE user_id = ? AND duration_minutes IS NOT NULL',
                (user['id'],)
            ).fetchall()
            
            for session_record in completed_sessions:
                total_online_minutes += session_record['duration_minutes']
            
            # Nếu người dùng đang online, thêm thời gian của phiên hiện tại
            if user_dict['current_status'] == 'online' and last_session and last_session['clock_in_time']:
                try:
                    clock_in_dt = datetime.datetime.strptime(last_session['clock_in_time'], '%Y-%m-%d %H:%M:%S')
                    current_duration = (datetime.datetime.now() - clock_in_dt).total_seconds() / 60.0
                    total_online_minutes += current_duration
                except ValueError:
                    # Xử lý lỗi nếu định dạng thời gian không khớp
                    pass

            user_dict['total_online_minutes_formatted'] = format_minutes_to_hhmm(total_online_minutes)
            users_data.append(user_dict)
    
    conn.close()
    return render_template('dashboard.html',
                           users=users_data,
                           is_admin=session.get('is_admin'),
                           current_user_status=current_user_status)

@app.route('/logout')
def logout():
    """Đăng xuất người dùng."""
    session.pop('user_id', None)
    session.pop('username', None)
    session.pop('is_admin', None)
    flash('Bạn đã đăng xuất.', 'info')
    return redirect(url_for('login'))

@app.route('/add_user', methods=['POST'])
def add_user():
    """Thêm người dùng mới (chỉ dành cho admin)."""
    if 'user_id' not in session or not session.get('is_admin'):
        flash('Bạn không có quyền thực hiện hành động này.', 'danger')
        return redirect(url_for('dashboard'))

    username = request.form['username']
    password = request.form['password']
    is_admin_new_user = request.form.get('is_admin_new_user') == 'on' # Checkbox value

    if not username or not password:
        flash('Vui lòng điền đầy đủ tên đăng nhập và mật khẩu.', 'danger')
        return redirect(url_for('dashboard'))

    conn = get_db_connection()
    existing_user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
    if existing_user:
        conn.close()
        flash('Tên đăng nhập đã tồn tại. Vui lòng chọn tên khác.', 'danger')
        return redirect(url_for('dashboard'))

    password_hash = generate_password_hash(password)
    try:
        conn.execute('INSERT INTO users (username, password, is_admin) VALUES (?, ?, ?)',
                       (username, password_hash, is_admin_new_user))
        conn.commit()
        flash(f'Người dùng "{username}" đã được thêm thành công!', 'success')
    except Exception as e:
        flash(f'Lỗi khi thêm người dùng: {e}', 'danger')
    finally:
        conn.close()
    return redirect(url_for('dashboard'))


@app.route('/delete_user/<int:user_id>', methods=['POST'])
def delete_user(user_id):
    """Xóa người dùng (chỉ dành cho admin)."""
    if 'user_id' not in session or not session.get('is_admin'):
        flash('Bạn không có quyền thực hiện hành động này.', 'danger')
        return redirect(url_for('dashboard'))

    conn = get_db_connection()
    try:
        # Không cho phép admin tự xóa chính mình nếu là admin duy nhất
        current_admin_id = session['user_id']
        if user_id == current_admin_id:
            # Kiểm tra xem có admin nào khác không
            other_admins = conn.execute("SELECT COUNT(*) FROM users WHERE is_admin = 1 AND id != ?", (current_admin_id,)).fetchone()[0]
            if other_admins == 0:
                flash('Không thể xóa tài khoản quản trị viên duy nhất.', 'danger')
                return redirect(url_for('dashboard'))

        # Xóa các bản ghi chấm công liên quan trước
        conn.execute('DELETE FROM attendance WHERE user_id = ?', (user_id,))
        # Sau đó xóa người dùng
        conn.execute('DELETE FROM users WHERE id = ?', (user_id,))
        conn.commit()
        flash('Người dùng đã được xóa thành công.', 'success')
    except Exception as e:
        flash(f'Lỗi khi xóa người dùng: {e}', 'danger')
    finally:
        conn.close()
    return redirect(url_for('dashboard'))

@app.route('/toggle_admin/<int:user_id>', methods=['POST'])
def toggle_admin(user_id):
    """Thay đổi trạng thái admin của người dùng (chỉ dành cho admin)."""
    if 'user_id' not in session or not session.get('is_admin'):
        flash('Bạn không có quyền thực hiện hành động này.', 'danger')
        return redirect(url_for('dashboard'))

    conn = get_db_connection()
    try:
        user = conn.execute('SELECT is_admin FROM users WHERE id = ?', (user_id,)).fetchone()
        if user:
            new_admin_status = not bool(user['is_admin'])
            
            # Ngăn chặn việc hạ cấp admin duy nhất
            if not new_admin_status and user_id == session['user_id']:
                # Kiểm tra xem có admin nào khác không
                other_admins = conn.execute("SELECT COUNT(*) FROM users WHERE is_admin = 1 AND id != ?", (session['user_id'],)).fetchone()[0]
                if other_admins == 0:
                    flash('Không thể hạ cấp tài khoản quản trị viên duy nhất.', 'danger')
                    return redirect(url_for('dashboard'))

            conn.execute('UPDATE users SET is_admin = ? WHERE id = ?', (new_admin_status, user_id))
            conn.commit()
            flash(f'Trạng thái quản trị của người dùng đã được cập nhật.', 'success')
        else:
            flash('Không tìm thấy người dùng.', 'danger')
    except Exception as e:
        flash(f'Lỗi khi cập nhật trạng thái quản trị: {e}', 'danger')
    finally:
        conn.close()
    return redirect(url_for('dashboard'))

@app.route('/clock_in', methods=['POST'])
def clock_in():
    """Ghi lại trạng thái 'online' cho người dùng hiện tại."""
    if 'user_id' not in session:
        flash('Vui lòng đăng nhập để chấm công.', 'warning')
        return redirect(url_for('login'))

    user_id = session['user_id']
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    conn = get_db_connection()
    try:
        # Kiểm tra xem người dùng có đang online không (clock_out_time is NULL)
        active_session = conn.execute(
            'SELECT id FROM attendance WHERE user_id = ? AND clock_out_time IS NULL',
            (user_id,)
        ).fetchone()

        if active_session:
            flash('Bạn đã vào ca rồi.', 'info')
        else:
            conn.execute('INSERT INTO attendance (user_id, clock_in_time, clock_out_time, duration_minutes) VALUES (?, ?, ?, ?)',
                           (user_id, timestamp, None, None)) # clock_out_time và duration_minutes là NULL ban đầu
            conn.commit()
            flash('Bạn đã vào ca thành công!', 'success')
    except Exception as e:
        flash(f'Lỗi khi vào ca: {e}', 'danger')
    finally:
        conn.close()
    return redirect(url_for('dashboard'))

@app.route('/clock_out', methods=['POST'])
def clock_out():
    """Ghi lại trạng thái 'offline' cho người dùng hiện tại và tính toán thời gian online."""
    if 'user_id' not in session:
        flash('Vui lòng đăng nhập để chấm công.', 'warning')
        return redirect(url_for('login'))

    user_id = session['user_id']
    current_time = datetime.datetime.now()
    conn = get_db_connection()
    try:
        # Tìm phiên làm việc gần đây nhất mà chưa tan ca (clock_out_time IS NULL)
        active_session = conn.execute(
            'SELECT id, clock_in_time FROM attendance WHERE user_id = ? AND clock_out_time IS NULL ORDER BY clock_in_time DESC LIMIT 1',
            (user_id,)
        ).fetchone()

        if not active_session:
            flash('Bạn chưa vào ca.', 'info')
        else:
            session_id = active_session['id']
            clock_in_dt_str = active_session['clock_in_time']
            
            try:
                clock_in_dt = datetime.datetime.strptime(clock_in_dt_str, '%Y-%m-%d %H:%M:%S')
                duration_seconds = (current_time - clock_in_dt).total_seconds()
                duration_minutes = duration_seconds / 60.0 # Chuyển đổi sang phút
                
                conn.execute(
                    'UPDATE attendance SET clock_out_time = ?, duration_minutes = ? WHERE id = ?',
                    (current_time.strftime('%Y-%m-%d %H:%M:%S'), duration_minutes, session_id)
                )
                conn.commit()
                flash(f'Bạn đã tan ca thành công! Thời gian online: {format_minutes_to_hhmm(duration_minutes)}.', 'success')
            except ValueError:
                flash('Lỗi định dạng thời gian khi tính toán thời gian online.', 'danger')
    except Exception as e:
        flash(f'Lỗi khi tan ca: {e}', 'danger')
    finally:
        conn.close()
    return redirect(url_for('dashboard'))

@app.route('/api/user_attendance_history/<int:user_id>')
def get_user_attendance_history(user_id):
    """API để lấy lịch sử chấm công chi tiết của một người dùng."""
    if 'user_id' not in session or not session.get('is_admin'):
        return jsonify({'error': 'Unauthorized'}), 401

    conn = get_db_connection()
    
    # Lấy tất cả các phiên chấm công của người dùng
    attendance_records = conn.execute(
        'SELECT clock_in_time, clock_out_time, duration_minutes FROM attendance WHERE user_id = ? ORDER BY clock_in_time DESC',
        (user_id,)
    ).fetchall()
    
    conn.close()

    history = []
    for record in attendance_records:
        clock_in_time = record['clock_in_time']
        clock_out_time = record['clock_out_time']
        duration_minutes = record['duration_minutes']

        # Định dạng ngày và giờ
        try:
            in_dt = datetime.datetime.strptime(clock_in_time, '%Y-%m-%d %H:%M:%S')
            date_str = in_dt.strftime('%Y-%m-%d')
            in_time_str = in_dt.strftime('%H:%M:%S')
        except ValueError:
            date_str = "N/A"
            in_time_str = "N/A"

        out_time_str = "Đang Online"
        formatted_duration = "Đang Online"

        if clock_out_time:
            try:
                out_dt = datetime.datetime.strptime(clock_out_time, '%Y-%m-%d %H:%M:%S')
                out_time_str = out_dt.strftime('%H:%M:%S')
                formatted_duration = format_minutes_to_hhmm(duration_minutes)
            except ValueError:
                out_time_str = "N/A"
                formatted_duration = "N/A"
        elif clock_in_time: # Nếu đang online, tính thời lượng hiện tại
            try:
                in_dt = datetime.datetime.strptime(clock_in_time, '%Y-%m-%d %H:%M:%S')
                current_duration_seconds = (datetime.datetime.now() - in_dt).total_seconds()
                current_duration_minutes = current_duration_seconds / 60.0
                formatted_duration = f"{format_minutes_to_hhmm(current_duration_minutes)} (hiện tại)"
            except ValueError:
                pass # Giữ nguyên "Đang Online" nếu có lỗi định dạng

        history.append({
            'date': date_str,
            'clock_in': in_time_str,
            'clock_out': out_time_str,
            'duration': formatted_duration
        })
    
    return jsonify(history)

if __name__ == '__main__':
    app.run(debug=True)
