from flask import Flask, render_template, request, jsonify, send_from_directory, session
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
import json
import threading
import time
import os
import uuid
from datetime import datetime, timedelta
import sqlite3
import jwt
from functools import wraps

# Import your enhanced modules
from enhanced_sensor_handler import EnhancedSensorDataHandler
from enhanced_analyzer import EnhancedRehabilitationAnalyzer
from enhanced_gpt_advisor import EnhancedGPTRehabilitationAdvisor

import logging
logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
CORS(app, supports_credentials=True)  # Allow cross-origin requests with credentials
app.secret_key = 'rehabtech_pro_secret_key_2025'  # Change in production

# Global variables
current_sessions = {}  # Support multiple concurrent sessions
data_handler = None
analyzer = None
advisor = None
JWT_SECRET = 'jwt_secret_key_rehabtech_pro'  # Change in production

def init_components():
    """Initialize system components"""
    global data_handler, analyzer, advisor

    # Initialize enhanced data handler with WiFi (ESP32 leg.ino)
    # ESP32 WiFi AP模式配置:
    # SSID: "ESP32_Server"
    # 密码: "12345678"
    # 连接后ESP32默认IP: 192.168.4.1
    data_handler = EnhancedSensorDataHandler(
        sensor_ip='192.168.4.207',  # ESP32 AP模式默认IP地址（连接到ESP32_Server后）
        sensor_port=80            # ESP32 WebServer端口
    )

    # Try to connect WiFi sensor (ESP32)
    print("\n[INFO] 正在连接到ESP32传感器...")
    print("[INFO] 请确保已连接到 'ESP32_Server' WiFi热点")
    data_handler.connect_wifi()

    # Initialize enhanced analyzer
    analyzer = EnhancedRehabilitationAnalyzer(db_path="rehabtech_pro.db")

    # Initialize enhanced AI advisor
    advisor = EnhancedGPTRehabilitationAdvisor(db_path="rehabtech_pro.db")

    print("✅ System components initialized successfully")

def token_required(f):
    """JWT token validation decorator"""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'error': 'Token is missing'}), 401
        
        try:
            if token.startswith('Bearer '):
                token = token[7:]
            data = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
            current_user_id = data['user_id']
            # Add user info to request context
            request.current_user_id = current_user_id
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token has expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Token is invalid'}), 401
        
        return f(*args, **kwargs)
    return decorated

# =============================================================================
# AUTHENTICATION ENDPOINTS
# =============================================================================

@app.route('/api/register', methods=['POST'])
def register():
    """User registration"""
    try:
        data = request.json
        name = data.get('name')
        email = data.get('email')
        password = data.get('password')
        role = data.get('role', 'patient')
        
        if not all([name, email, password]):
            return jsonify({'success': False, 'message': 'All fields are required'}), 400
        
        # Check if user already exists
        conn = sqlite3.connect("rehabtech_pro.db")
        cursor = conn.cursor()
        
        cursor.execute('SELECT id FROM users WHERE email = ?', (email,))
        if cursor.fetchone():
            conn.close()
            return jsonify({'success': False, 'message': 'Email already registered'}), 400
        
        # Create new user
        user_id = str(uuid.uuid4())
        password_hash = generate_password_hash(password)
        
        cursor.execute('''
            INSERT INTO users (id, email, password_hash, full_name, role, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, email, password_hash, name, role, datetime.now()))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'User registered successfully',
            'user_id': user_id
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/login', methods=['POST'])
def login():
    """User login"""
    try:
        data = request.json
        email = data.get('email')
        password = data.get('password')
        
        if not all([email, password]):
            return jsonify({'success': False, 'message': 'Email and password are required'}), 400
        
        conn = sqlite3.connect("rehabtech_pro.db")
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, password_hash, full_name, role, age, sex, weight, 
                   rehabilitation_stage, main_problems
            FROM users WHERE email = ?
        ''', (email,))
        
        user = cursor.fetchone()
        conn.close()
        
        if not user or not check_password_hash(user[1], password):
            return jsonify({'success': False, 'message': 'Invalid email or password'}), 401
        
        # Generate JWT token
        token_payload = {
            'user_id': user[0],
            'email': email,
            'role': user[3],
            'exp': datetime.utcnow() + timedelta(hours=24)
        }
        token = jwt.encode(token_payload, JWT_SECRET, algorithm='HS256')
        
        return jsonify({
            'success': True,
            'token': token,
            'user': {
                'id': user[0],
                'email': email,
                'name': user[2],
                'role': user[3],
                'age': user[4],
                'sex': user[5],
                'weight': user[6],
                'rehabilitation_stage': user[7],
                'main_problems': user[8],
                'has_rehab_stage': bool(user[7])
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/logout', methods=['POST'])
@token_required
def logout():
    """User logout"""
    return jsonify({'success': True, 'message': 'Logged out successfully'})

# =============================================================================
# USER MANAGEMENT ENDPOINTS
# =============================================================================

@app.route('/api/users/profile', methods=['GET'])
@token_required
def get_user_profile():
    """Get user profile"""
    try:
        user_id = request.current_user_id
        
        conn = sqlite3.connect("rehabtech_pro.db")
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, email, full_name, role, age, sex, weight,
                   rehabilitation_stage, main_problems, created_at, updated_at
            FROM users WHERE id = ?
        ''', (user_id,))
        
        user = cursor.fetchone()
        conn.close()
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        return jsonify({
            'success': True,
            'user': {
                'id': user[0],
                'email': user[1],
                'full_name': user[2],
                'role': user[3],
                'age': user[4],
                'sex': user[5],
                'weight': user[6],
                'rehabilitation_stage': user[7],
                'main_problems': user[8],
                'created_at': user[9],
                'updated_at': user[10]
            }
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/users/profile', methods=['PUT'])
@token_required
def update_user_profile():
    """Update user profile"""
    try:
        user_id = request.current_user_id
        data = request.json
        
        # Extract fields to update
        full_name = data.get('full_name')
        age = data.get('age')
        sex = data.get('sex')
        weight = data.get('weight')
        rehabilitation_stage = data.get('rehabilitation_stage')
        main_problems = data.get('main_problems')
        
        conn = sqlite3.connect("rehabtech_pro.db")
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE users 
            SET full_name = ?, age = ?, sex = ?, weight = ?, 
                rehabilitation_stage = ?, main_problems = ?, updated_at = ?
            WHERE id = ?
        ''', (full_name, age, sex, weight, rehabilitation_stage, 
              main_problems, datetime.now(), user_id))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Profile updated successfully'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/users/stats', methods=['GET'])
@token_required
def get_user_stats():
    """Get user statistics"""
    try:
        user_id = request.current_user_id
        
        conn = sqlite3.connect("rehabtech_pro.db")
        cursor = conn.cursor()
        
        # Get total sessions
        cursor.execute('SELECT COUNT(*) FROM training_sessions WHERE user_id = ?', (user_id,))
        total_sessions = cursor.fetchone()[0]
        
        # Get current streak (consecutive days with training)
        cursor.execute('''
            SELECT DISTINCT DATE(start_time) as training_date 
            FROM training_sessions 
            WHERE user_id = ? AND status = 'completed'
            ORDER BY training_date DESC
        ''', (user_id,))
        
        training_dates = [row[0] for row in cursor.fetchall()]
        current_streak = calculate_streak(training_dates)
        
        # Get weekly progress (last 7 days)
        cursor.execute('''
            SELECT COUNT(*) FROM training_sessions 
            WHERE user_id = ? AND start_time >= date('now', '-7 days')
        ''', (user_id,))
        weekly_sessions = cursor.fetchone()[0]
        
        # Calculate rehabilitation score (average of recent test scores)
        cursor.execute('''
            SELECT AVG(overall_score) FROM analysis_results ar
            JOIN training_sessions ts ON ar.session_id = ts.session_id
            WHERE ts.user_id = ? AND ar.created_at >= date('now', '-30 days')
        ''', (user_id,))
        
        avg_score_result = cursor.fetchone()
        rehab_score = int(avg_score_result[0]) if avg_score_result[0] else 75
        
        conn.close()
        
        return jsonify({
            'success': True,
            'stats': {
                'total_sessions': total_sessions,
                'current_streak': current_streak,
                'weekly_progress': min(100, weekly_sessions * 20),  # 5 sessions = 100%
                'rehab_score': rehab_score
            }
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def calculate_streak(training_dates):
    """Calculate consecutive training streak"""
    if not training_dates:
        return 0
    
    streak = 0
    current_date = datetime.now().date()
    
    for date_str in training_dates:
        training_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        days_diff = (current_date - training_date).days
        
        if days_diff == streak:
            streak += 1
        elif days_diff == streak + 1:
            streak += 1
        else:
            break
    
    return streak

# =============================================================================
# WIFI SENSOR COMMUNICATION ENDPOINTS (FOR TRAINING)
# =============================================================================

# Global variable to store sensor data stream
sensor_data_stream = {}
training_sessions_data = {}

@app.route('/api/sensor/command', methods=['POST'])
def send_sensor_command():
    """Send command to WiFi sensor (ESP32 leg.ino)

    支持的命令 (leg.ino):
    - 'a11': 训练模式1 - 直接移动
    - 'a12': 训练模式2 - 力值低于阈值时移动
    - 'b11': 训练模式3 - 力值高于阈值时移动
    - 'b12': 训练模式4 - 5秒后停止
    - 'exit': 退出控制模式
    - 舵机控制: 提供servo1和servo2参数 (0-200度)
    """
    try:
        data = request.json
        command = data.get('command')
        servo1 = data.get('servo1')
        servo2 = data.get('servo2')

        print(f"📡 WiFi Sensor Command Received: {command or f'servo control: s1={servo1}, s2={servo2}'}")

        # 使用data_handler发送命令到ESP32
        if data_handler and data_handler.is_connected:
            success = data_handler.send_command(
                command=command,
                servo1=servo1,
                servo2=servo2
            )

            if success:
                return jsonify({
                    'success': True,
                    'message': 'Command sent to ESP32 successfully',
                    'command': command,
                    'servo1': servo1,
                    'servo2': servo2
                })
            else:
                return jsonify({
                    'success': False,
                    'message': 'Failed to send command to ESP32'
                }), 500
        else:
            # WiFi未连接，使用模拟模式
            print("[WARN] WiFi not connected, using simulation mode")
            return jsonify({
                'success': True,
                'message': 'Command received (simulation mode)',
                'command': command,
                'servo1': servo1,
                'servo2': servo2,
                'mode': 'simulation'
            })

    except Exception as e:
        print(f"❌ Error sending sensor command: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/sensor/data', methods=['GET'])
def get_sensor_data():
    """Get latest sensor data from WiFi sensor (ESP32 leg.ino)

    leg.ino返回格式: {"angle": virtual_angle, "yaw": angleY1, "force": force_N}
    """
    try:
        # 使用data_handler从ESP32读取数据
        if data_handler and data_handler.is_connected:
            # 读取所有类型的数据
            sensor_data = data_handler.read_sensor_data('force and angle test')

            if sensor_data:
                return jsonify({
                    'success': True,
                    'data': {
                        'force': sensor_data.get('force_value', 0),
                        'angle': sensor_data.get('angle_value', 0),
                        'yaw': sensor_data.get('yaw_angle', 0),
                        'virtual_angle': sensor_data.get('virtual_angle', 0),
                        'timestamp': sensor_data.get('timestamp'),
                        'data_quality': sensor_data.get('data_quality', 1.0)
                    },
                    'mode': 'wifi'
                })

        # Fallback: return simulated data
        import random
        simulated_data = {
            'force': round(20 + random.random() * 40, 2),
            'angle': round(30 + random.random() * 60, 2),
            'yaw': round(-90 + random.random() * 180, 2),
            'virtual_angle': round(30 + random.random() * 60, 2),
            'timestamp': time.time(),
            'data_quality': 1.0
        }

        return jsonify({
            'success': True,
            'data': simulated_data,
            'mode': 'simulation'
        })

    except Exception as e:
        print(f"❌ Error getting sensor data: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/sensor/stream/start', methods=['POST'])
def start_sensor_stream():
    """Start receiving data stream from WiFi sensor"""
    try:
        data = request.json
        session_id = data.get('session_id', str(uuid.uuid4()))

        # Initialize stream for this session
        training_sessions_data[session_id] = {
            'session_id': session_id,
            'start_time': time.time(),
            'is_streaming': True,
            'data_points': []
        }

        print(f"📡 WiFi sensor stream started - Session: {session_id}")

        # Start background thread to collect data from WiFi sensor
        stream_thread = threading.Thread(
            target=collect_wifi_sensor_data,
            args=(session_id,)
        )
        stream_thread.daemon = True
        stream_thread.start()

        return jsonify({
            'success': True,
            'session_id': session_id,
            'message': 'Sensor stream started'
        })

    except Exception as e:
        print(f"❌ Error starting sensor stream: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/sensor/stream/stop', methods=['POST'])
def stop_sensor_stream():
    """Stop receiving data stream from WiFi sensor"""
    try:
        data = request.json
        session_id = data.get('session_id')

        if session_id in training_sessions_data:
            training_sessions_data[session_id]['is_streaming'] = False
            data_points_count = len(training_sessions_data[session_id]['data_points'])

            print(f"📡 WiFi sensor stream stopped - Session: {session_id}, Data points: {data_points_count}")

            return jsonify({
                'success': True,
                'message': 'Sensor stream stopped',
                'data_points_count': data_points_count
            })
        else:
            return jsonify({'success': False, 'message': 'Session not found'}), 404

    except Exception as e:
        print(f"❌ Error stopping sensor stream: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

def collect_wifi_sensor_data(session_id):
    """Background thread to collect data from WiFi sensor (ESP32 leg.ino)"""
    import random

    print(f"🚀 WiFi sensor data collection started for session: {session_id}")

    while (session_id in training_sessions_data and
           training_sessions_data[session_id]['is_streaming']):
        try:
            # 从ESP32读取数据
            if data_handler and data_handler.is_connected:
                # 使用data_handler从ESP32读取数据
                sensor_data = data_handler.read_sensor_data('force and angle test')

                if sensor_data:
                    force = sensor_data.get('force_value', 0)
                    angle = sensor_data.get('angle_value', 0)
                    yaw = sensor_data.get('yaw_angle', 0)
                    virtual_angle = sensor_data.get('virtual_angle', 0)
                else:
                    # 如果读取失败，使用模拟数据
                    force = round(20 + random.random() * 40, 2)
                    angle = round(30 + random.random() * 60, 2)
                    yaw = round(-90 + random.random() * 180, 2)
                    virtual_angle = round(30 + random.random() * 60, 2)
            else:
                # WiFi未连接，使用模拟数据
                force = round(20 + random.random() * 40, 2)
                angle = round(30 + random.random() * 60, 2)
                yaw = round(-90 + random.random() * 180, 2)
                virtual_angle = round(30 + random.random() * 60, 2)

            data_point = {
                'force': force,
                'angle': angle,
                'yaw': yaw,
                'virtual_angle': virtual_angle,
                'timestamp': time.time()
            }

            training_sessions_data[session_id]['data_points'].append(data_point)

            # Sleep for 500ms (2 Hz update rate, 与leg.ino的stream间隔一致)
            time.sleep(0.5)

        except Exception as e:
            print(f"❌ Error collecting WiFi sensor data: {e}")
            time.sleep(0.5)  # 出错后继续尝试

    print(f"✅ WiFi sensor data collection completed for session: {session_id}")

# =============================================================================
# TESTING ENDPOINTS
# =============================================================================

@app.route('/api/testing/start', methods=['POST'])
@token_required
def start_test():
    """Start rehabilitation test"""
    try:
        user_id = request.current_user_id
        data = request.json
        
        test_type = data.get('test_type')
        duration = int(data.get('duration', 60))
        interval = float(data.get('data_interval', 0.1))
        
        if not test_type:
            return jsonify({'error': 'Test type is required'}), 400
        
        # Create training session
        session_id = data_handler.create_training_session(
            user_id=user_id,
            test_types=[test_type]
        )
        
        # Store session info
        current_sessions[session_id] = {
            'session_id': session_id,
            'user_id': user_id,
            'test_type': test_type,
            'duration': duration,
            'interval': interval,
            'start_time': datetime.now(),
            'data_count': 0,
            'is_collecting': True
        }
        
        # Start background data collection
        collection_thread = threading.Thread(
            target=collect_data_background,
            args=(test_type, session_id, user_id, duration, interval)
        )
        collection_thread.daemon = True
        collection_thread.start()
        
        return jsonify({
            'success': True,
            'session_id': session_id,
            'message': 'Test started successfully'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/testing/stop', methods=['POST'])
@token_required
def stop_test():
    """Stop rehabilitation test"""
    try:
        user_id = request.current_user_id
        data = request.json
        session_id = data.get('session_id')
        
        if not session_id or session_id not in current_sessions:
            return jsonify({'error': 'Invalid session'}), 400
        
        # Stop data collection
        current_sessions[session_id]['is_collecting'] = False
        
        # End training session
        data_handler.end_training_session(session_id)
        
        # Perform analysis
        analysis_results = analyzer.comprehensive_analysis(session_id)
        
        # Get user profile for AI recommendations
        user_profile = get_user_profile_for_ai(user_id)
        
        # Generate AI recommendations
        recommendations = advisor.generate_recommendations(analysis_results, user_profile)
        
        # Clean up session
        session_data = current_sessions.pop(session_id)
        
        return jsonify({
            'success': True,
            'session_data': session_data,
            'analysis_results': analysis_results,
            'recommendations': recommendations,
            'message': 'Test completed successfully'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/testing/realtime/<session_id>', methods=['GET'])
@token_required
def get_realtime_data(session_id):
    """Get real-time test data"""
    try:
        if session_id not in current_sessions:
            return jsonify({'error': 'Session not found'}), 404
        
        conn = sqlite3.connect("rehabtech_pro.db")
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT timestamp, force_value, angle_value 
            FROM sensor_data 
            WHERE session_id = ? 
            ORDER BY timestamp DESC 
            LIMIT 1
        ''', (session_id,))
        
        result = cursor.fetchone()
        
        cursor.execute('''
            SELECT COUNT(*) FROM sensor_data WHERE session_id = ?
        ''', (session_id,))
        
        data_count = cursor.fetchone()[0]
        conn.close()
        
        if result:
            return jsonify({
                'success': True,
                'data': {
                    'timestamp': result[0],
                    'force_value': result[1],
                    'angle_value': result[2],
                    'data_count': data_count,
                    'session_id': session_id
                }
            })
        else:
            return jsonify({
                'success': True,
                'data': {
                    'message': 'No data available yet',
                    'data_count': data_count,
                    'session_id': session_id
                }
            })
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# =============================================================================
# REPORTS ENDPOINTS
# =============================================================================

@app.route('/api/reports/daily', methods=['GET'])
@token_required
def get_daily_report():
    """Get daily report"""
    try:
        user_id = request.current_user_id
        date = request.args.get('date', datetime.now().date().isoformat())
        
        report = advisor.generate_daily_report(user_id, date)
        return jsonify({'success': True, 'report': report})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/reports/weekly', methods=['GET'])
@token_required
def get_weekly_report():
    """Get weekly report"""
    try:
        user_id = request.current_user_id
        weeks = int(request.args.get('weeks', 1))
        
        report = advisor.generate_weekly_summary(user_id, weeks)
        return jsonify({'success': True, 'report': report})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/reports/monthly', methods=['GET'])
@token_required
def get_monthly_report():
    """Get monthly report"""
    try:
        user_id = request.current_user_id
        months = int(request.args.get('months', 1))
        
        report = advisor.generate_monthly_summary(user_id, months)
        return jsonify({'success': True, 'report': report})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/reports/progress', methods=['GET'])
@token_required
def get_progress_report():
    """Get progress comparison report"""
    try:
        user_id = request.current_user_id
        days = int(request.args.get('days', 30))
        
        comparison_data = analyzer.generate_comparison_analysis(user_id, days)
        
        if "error" not in comparison_data:
            user_profile = get_user_profile_for_ai(user_id)
            recommendations = advisor.generate_comparison_recommendations(
                comparison_data, user_profile
            )
            comparison_data['recommendations'] = recommendations
        
        return jsonify({'success': True, 'report': comparison_data})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# =============================================================================
# DATA EXPORT ENDPOINTS
# =============================================================================

@app.route('/api/export/session/<session_id>', methods=['GET'])
@token_required
def export_session_data(session_id):
    """Export session data as CSV"""
    try:
        data = data_handler.get_session_data(session_id)
        
        # Convert to CSV format
        csv_content = "Timestamp,Test Type,Force Value (N),Angle Value (°)\n"
        for item in data:
            csv_content += f"{item['timestamp']},{item['test_type']},{item.get('force_value', '')},{item.get('angle_value', '')}\n"
        
        return csv_content, 200, {
            'Content-Type': 'text/csv',
            'Content-Disposition': f'attachment; filename=rehabtech_session_{session_id}.csv'
        }
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/export/user-history', methods=['GET'])
@token_required
def export_user_history():
    """Export user training history"""
    try:
        user_id = request.current_user_id
        days = int(request.args.get('days', 30))
        
        # Get user training history
        conn = sqlite3.connect("rehabtech_pro.db")
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT ts.session_id, ts.start_time, ts.end_time, ts.duration,
                   sd.timestamp, sd.test_type, sd.force_value, sd.angle_value
            FROM training_sessions ts
            LEFT JOIN sensor_data sd ON ts.session_id = sd.session_id
            WHERE ts.user_id = ? AND ts.start_time >= date('now', '-{} days')
            ORDER BY ts.start_time DESC, sd.timestamp
        '''.format(days), (user_id,))
        
        data = cursor.fetchall()
        conn.close()
        
        # Convert to CSV
        csv_content = "Session ID,Session Start,Session End,Duration (s),Data Timestamp,Test Type,Force (N),Angle (°)\n"
        for row in data:
            csv_content += f"{row[0]},{row[1]},{row[2]},{row[3]},{row[4]},{row[5]},{row[6] or ''},{row[7] or ''}\n"
        
        return csv_content, 200, {
            'Content-Type': 'text/csv',
            'Content-Disposition': f'attachment; filename=rehabtech_history_{user_id}_{days}days.csv'
        }
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# =============================================================================
# SYSTEM ENDPOINTS
# =============================================================================

@app.route('/api/system/status', methods=['GET'])
def get_system_status():
    """Get system status"""
    try:
        # Check database connection
        db_status = 'offline'
        total_users = 0
        total_sessions = 0
        
        if os.path.exists('rehabtech_pro.db'):
            try:
                conn = sqlite3.connect("rehabtech_pro.db")
                cursor = conn.cursor()
                
                cursor.execute('SELECT COUNT(*) FROM users')
                total_users = cursor.fetchone()[0]
                
                cursor.execute('SELECT COUNT(*) FROM training_sessions')
                total_sessions = cursor.fetchone()[0]
                
                conn.close()
                db_status = 'online'
            except Exception as e:
                db_status = f'error: {str(e)}'
        
        return jsonify({
            'success': True,
            'status': {
                'database': db_status,
                'total_users': total_users,
                'total_sessions': total_sessions,
                'active_sessions': len(current_sessions),
                'wifi_sensor': 'connected' if data_handler.is_connected else 'simulation_mode',
                'sensor_ip': data_handler.sensor_ip if hasattr(data_handler, 'sensor_ip') else 'N/A',
                'ai_service': 'available' if advisor.client else 'simulation_mode',
                'system_time': datetime.now().isoformat(),
                'version': '1.0.0'
            }
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/system/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'version': '1.0.0'
    })

# =============================================================================
# STATIC FILE SERVING
# =============================================================================

@app.route('/')
def index():
    """Serve homepage"""
    return send_from_directory('.', 'index.html')

@app.route('/index-app/')
@app.route('/index-app/<path:filename>')
def serve_index_app(filename='index.html'):
    """Serve index React app files"""
    return send_from_directory('./index', filename)

@app.route('/<path:filename>')
def serve_static(filename):
    """Serve static files"""
    return send_from_directory('.', filename)

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_user_profile_for_ai(user_id):
    """Get user profile formatted for AI analysis"""
    try:
        conn = sqlite3.connect("rehabtech_pro.db")
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT full_name, age, sex, weight, rehabilitation_stage, main_problems
            FROM users WHERE id = ?
        ''', (user_id,))
        
        user = cursor.fetchone()
        conn.close()
        
        if user:
            return {
                'name': user[0],
                'age': user[1],
                'sex': 'Male' if user[2] == 1 else 'Female' if user[2] == 2 else 'Unknown',
                'weight': user[3],
                'rehabilitation_stage': user[4],
                'main_problems': user[5]
            }
        
        return {}
        
    except Exception as e:
        print(f"Error getting user profile: {e}")
        return {}

def collect_data_background(test_type, session_id, user_id, duration, interval):
    """Background data collection function"""
    start_time = time.time()
    data_count = 0
    
    print(f"🚀 Starting background data collection: {test_type}, Session: {session_id}")
    
    while (session_id in current_sessions and 
           current_sessions[session_id]['is_collecting'] and 
           (time.time() - start_time) < duration):
        try:
            # Read sensor data
            sensor_data = data_handler.read_sensor_data(test_type)
            
            if sensor_data:
                # Save to database
                data_handler.save_to_database(sensor_data, session_id, user_id)
                data_count += 1
                
                # Update session data count
                if session_id in current_sessions:
                    current_sessions[session_id]['data_count'] = data_count
                
                # Print debug info
                force_str = f"Force: {sensor_data.get('force_value', 'N/A'):.2f}N" if sensor_data.get('force_value') else ""
                angle_str = f"Angle: {sensor_data.get('angle_value', 'N/A'):.2f}°" if sensor_data.get('angle_value') else ""
                print(f"[{data_count}] {force_str} {angle_str} -> Saved")
            
            time.sleep(interval)
            
        except Exception as e:
            print(f"❌ Data collection error: {e}")
            break
    
    # Mark collection as stopped
    if session_id in current_sessions:
        current_sessions[session_id]['is_collecting'] = False
    
    print(f"✅ Data collection completed - Total data points: {data_count}")

# =============================================================================
# APPLICATION STARTUP
# =============================================================================

if __name__ == "__main__":
    print("=" * 80)
    print("🏥 Regenix - ADVANCED REHABILITATION ANALYTICS PLATFORM")
    print("=" * 80)
    
    # Initialize components
    init_components()
    
    print("\n✅ System initialization completed!")
    print("🌐 Web server starting at: http://localhost:5000")
    print("📖 API documentation: http://localhost:5000/api/system/status")
    print("\n📋 Available API Endpoints:")
    print("   🔐 Authentication:")
    print("     - POST /api/auth/register - User registration")
    print("     - POST /api/auth/login - User login")
    print("     - POST /api/auth/logout - User logout")
    print("   👤 User Management:")
    print("     - GET /api/users/profile - Get user profile")
    print("     - PUT /api/users/profile - Update user profile")
    print("     - GET /api/users/stats - Get user statistics")
    print("   🧪 Testing:")
    print("     - POST /api/testing/start - Start rehabilitation test")
    print("     - POST /api/testing/stop - Stop rehabilitation test")
    print("     - GET /api/testing/realtime/<session_id> - Get real-time data")
    print("   📊 Reports:")
    print("     - GET /api/reports/daily - Get daily report")
    print("     - GET /api/reports/weekly - Get weekly report")
    print("     - GET /api/reports/monthly - Get monthly report")
    print("     - GET /api/reports/progress - Get progress report")
    print("   📤 Export:")
    print("     - GET /api/export/session/<session_id> - Export session data")
    print("     - GET /api/export/user-history - Export user history")
    print("\n⚡ Press Ctrl+C to stop the server")
    print("=" * 80)
    
    try:
        # Start Flask application
        app.run(
            host='0.0.0.0',  # Allow external access
            port=5000,
            debug=True,
            use_reloader=False  # Avoid duplicate initialization
        )
    except KeyboardInterrupt:
        print("\n\n🛑 System shutting down safely...")
        if data_handler:
            data_handler.close()
        print("👋 Goodbye!")
    except Exception as e:
        print(f"❌ Startup failed: {e}")