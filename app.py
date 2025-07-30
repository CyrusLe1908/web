# app.py
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
import os

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
    """Khởi tạo cơ sở dữ liệu và tạo bảng người dùng."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                is_admin BOOLEAN NOT NULL DEFAULT 0
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

# Xóa bỏ route đăng ký công khai
# @app.route('/register', methods=['GET', 'POST'])
# def register():
#     ... (đoạn mã này đã bị xóa)

@app.route('/dashboard')
def dashboard():
    """Hiển thị trang quản lý hoặc trang người dùng."""
    if 'user_id' not in session:
        flash('Vui lòng đăng nhập để truy cập trang này.', 'warning')
        return redirect(url_for('login'))

    conn = get_db_connection()
    users = []
    if session.get('is_admin'):
        users = conn.execute('SELECT id, username, is_admin FROM users').fetchall()
    conn.close()
    return render_template('dashboard.html', users=users, is_admin=session.get('is_admin'))

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

if __name__ == '__main__':
    app.run(debug=True)
