import os
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

# Tải các biến môi trường từ tệp .env (cho SECRET_KEY)
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'a_very_secret_key_that_should_be_random_and_long') # Thay đổi cái này trong môi trường sản xuất
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db' # Tệp cơ sở dữ liệu SQLite
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Mô hình người dùng
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    is_admin = db.Column(db.Boolean, default=False) # Thêm cờ admin

    def __repr__(self):
        return f'<User {self.username}>'

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

# Tạo bảng cơ sở dữ liệu
with app.app_context():
    db.create_all()
    # Tùy chọn: Tạo người dùng admin nếu không có cho thiết lập ban đầu
    if not User.query.filter_by(username='admin').first():
        admin_user = User(username='admin', is_admin=True)
        admin_user.set_password('adminpassword') # THAY ĐỔI MẬT KHẨU NÀY NGAY LẬP TỨC!
        db.session.add(admin_user)
        db.session.commit()
        print("Người dùng admin 'admin' đã được tạo với mật khẩu 'adminpassword'")

# Các tuyến đường

@app.route('/')
def login_page():
    return render_template('index.html') # Trang đăng nhập của bạn

@app.route('/register')
def register_page():
    return render_template('register.html') # Trang đăng ký của bạn

@app.route('/dashboard')
def dashboard_page():
    if 'user_id' not in session:
        return redirect(url_for('login_page'))
    return render_template('dashboard.html') # Trang bảng điều khiển của bạn

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    user = User.query.filter_by(username=username).first()

    if user and user.check_password(password):
        session['user_id'] = user.id
        session['username'] = user.username
        session['is_admin'] = user.is_admin
        return jsonify({'message': 'Đăng nhập thành công!', 'redirect': url_for('dashboard_page')}), 200
    else:
        return jsonify({'message': 'Sai tên đăng nhập hoặc mật khẩu.'}), 401

@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({'message': 'Tên đăng nhập và mật khẩu không được để trống.'}), 400

    existing_user = User.query.filter_by(username=username).first()
    if existing_user:
        return jsonify({'message': 'Tên đăng nhập đã tồn tại.'}), 409

    new_user = User(username=username)
    new_user.set_password(password)
    db.session.add(new_user)
    db.session.commit()

    return jsonify({'message': 'Đăng ký thành công!'}), 201

@app.route('/logout', methods=['POST'])
def logout():
    session.pop('user_id', None)
    session.pop('username', None)
    session.pop('is_admin', None)
    return jsonify({'message': 'Đăng xuất thành công!'}), 200

# Các điểm cuối API để quản lý người dùng
@app.route('/api/user_info', methods=['GET'])
def get_user_info():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'message': 'Chưa đăng nhập.'}), 401
    
    user = User.query.get(user_id)
    if user:
        return jsonify({'username': user.username, 'is_admin': user.is_admin}), 200
    return jsonify({'message': 'Người dùng không tồn tại.'}), 404


@app.route('/api/users', methods=['GET'])
def get_all_users():
    if not session.get('is_admin'):
        return jsonify({'message': 'Không có quyền truy cập.'}), 403
    
    users = User.query.all()
    user_list = [{'username': user.username, 'is_admin': user.is_admin} for user in users]
    return jsonify(user_list), 200

@app.route('/api/users/<username>', methods=['PUT'])
def update_user(username):
    if not session.get('is_admin'):
        return jsonify({'message': 'Không có quyền truy cập.'}), 403

    user_to_update = User.query.filter_by(username=username).first()
    if not user_to_update:
        return jsonify({'message': 'Người dùng không tồn tại.'}), 404

    data = request.get_json()
    new_password = data.get('new_password')
    # Bạn có thể thêm các trường khác để cập nhật ở đây nếu cần, như trạng thái is_admin

    if new_password:
        user_to_update.set_password(new_password)
        db.session.commit()
        return jsonify({'message': f'Mật khẩu của {username} đã được cập nhật.'}), 200
    else:
        return jsonify({'message': 'Không có mật khẩu mới được cung cấp để cập nhật.'}), 400

@app.route('/api/users/<username>', methods=['DELETE'])
def delete_user(username):
    if not session.get('is_admin'):
        return jsonify({'message': 'Không có quyền truy cập.'}), 403

    user_to_delete = User.query.filter_by(username=username).first()
    if not user_to_delete:
        return jsonify({'message': 'Người dùng không tồn tại.'}), 404
    
    if user_to_delete.username == session.get('username'): # Ngăn quản trị viên tự xóa tài khoản của họ
        return jsonify({'message': 'Bạn không thể xóa tài khoản của chính mình.'}), 400

    db.session.delete(user_to_delete)
    db.session.commit()
    return jsonify({'message': f'Tài khoản {username} đã được xóa.'}), 200


if __name__ == '__main__':
    app.run(debug=True) # Đặt debug=False trong môi trường sản xuất
# app.py
import os
# ...
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///database.db')
# ...