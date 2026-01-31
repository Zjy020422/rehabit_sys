import sqlite3
import requests
from datetime import datetime
import numpy as np
import time
import random
import json
import uuid
import re

class EnhancedSensorDataHandler:
    """
    增强型传感器数据处理器 - WiFi通信版本

    使用WiFi HTTP API与传感器通信，替代串口通信

    模式定义：
    MODE_ANGLE = 1  # 只获取角度
    MODE_FORCE = 2  # 只获取拉力
    MODE_ALL = 3    # 获取角度和拉力
    """

    # 模式常量
    MODE_ANGLE = 1
    MODE_FORCE = 2
    MODE_ALL = 3

    def __init__(self, db_path='rehabtech_pro.db', sensor_ip='192.168.4.1', sensor_port=80, sensor_url=None):
        """
        初始化WiFi传感器处理器

        Args:
            db_path: 数据库路径
            sensor_ip: 传感器WiFi IP地址（ESP32 AP模式，连接到ESP32_Server后获取的IP）
            sensor_port: 传感器HTTP端口（默认80）
            sensor_url: 传感器完整URL（如ngrok地址，优先级高于sensor_ip）
        """
        self.db_path = db_path

        # 如果提供了完整URL（如ngrok），使用URL；否则使用IP和端口
        if sensor_url:
            self.sensor_url_base = sensor_url.rstrip('/')
            self.sensor_ip = sensor_url  # 用于显示
            self.sensor_port = None
            print(f"[INFO] 使用公网URL: {sensor_url}")
        else:
            self.sensor_ip = sensor_ip
            self.sensor_port = sensor_port
            self.sensor_url_base = f"http://{sensor_ip}:{sensor_port}"
            print("[INFO] ESP32 WiFi配置:")
            print("       SSID: ESP32_Server")
            print("       密码: 12345678")
            print(f"       IP: {sensor_ip}:{sensor_port}")

        self.is_connected = False
        self.is_running = False
        self.current_mode = self.MODE_ALL  # 默认模式3
        self.timeout = 10  # HTTP请求超时时间（秒），ngrok可能需要更长时间
        self.init_database()

    def init_database(self):
        """Initialize enhanced database schema"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                full_name TEXT NOT NULL,
                age INTEGER,
                sex INTEGER,  -- 1=Male, 2=Female
                weight REAL,
                role TEXT NOT NULL DEFAULT 'patient',  -- patient, therapist, doctor, researcher
                rehabilitation_stage TEXT,  -- Early, Middle, Late
                main_problems TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Enhanced sensor data table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sensor_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                test_type TEXT NOT NULL,  -- 'force test', 'angle test', 'force and angle test'
                force_value REAL,         -- Force in Newtons
                angle_value REAL,         -- Angle in degrees
                session_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                data_quality REAL DEFAULT 1.0,  -- Data quality score 0-1
                calibration_factor REAL DEFAULT 1.0,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (session_id) REFERENCES training_sessions(session_id)
            )
        ''')

        # Enhanced training sessions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS training_sessions (
                session_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                start_time DATETIME NOT NULL,
                end_time DATETIME,
                duration INTEGER,  -- Duration in seconds
                test_types TEXT,   -- JSON array of test types
                status TEXT DEFAULT 'active',  -- active, completed, cancelled
                session_config TEXT,  -- JSON configuration
                notes TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')

        # Analysis results table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS analysis_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                analysis_type TEXT NOT NULL,  -- comprehensive, statistical, trend, clustering
                results TEXT,  -- JSON results
                overall_score REAL,  -- Overall performance score
                grade TEXT,  -- Performance grade A-F
                recommendations TEXT,  -- AI-generated recommendations
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES training_sessions(session_id)
            )
        ''')

        # User preferences table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_preferences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                preference_key TEXT NOT NULL,
                preference_value TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id),
                UNIQUE(user_id, preference_key)
            )
        ''')

        # Training goals table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS training_goals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                goal_type TEXT NOT NULL,  -- force_improvement, angle_improvement, frequency
                target_value REAL NOT NULL,
                current_value REAL DEFAULT 0,
                target_date DATE,
                status TEXT DEFAULT 'active',  -- active, achieved, paused
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')

        conn.commit()
        conn.close()
        print('[OK] Enhanced database schema created successfully')

    def connect_wifi(self):
        """
        连接到WiFi传感器（ESP32），测试连接状态

        Returns:
            bool: 连接成功返回True
        """
        try:
            # 测试连接 - 调用ESP32的/data端点
            response = requests.get(
                f"{self.sensor_url_base}/data",
                timeout=self.timeout
            )

            if response.status_code == 200:
                # 尝试解析返回的JSON数据以验证格式
                data = response.json()
                # leg.ino 返回格式: {"angle": x, "yaw": y, "force": z}
                if 'angle' in data or 'yaw' in data or 'force' in data:
                    self.is_connected = True
                    print(f'[OK] WiFi sensor (ESP32) connected successfully: {self.sensor_ip}:{self.sensor_port}')
                    print(f'[INFO] Received data: angle={data.get("angle")}, yaw={data.get("yaw")}, force={data.get("force")}')
                    return True
                else:
                    print(f'[WARN] WiFi sensor responded but with unexpected data format')
                    print(f'[DEBUG] Received: {data}')
                    return False
            else:
                print(f'[WARN] WiFi sensor responded with status {response.status_code}')
                return False

        except requests.exceptions.RequestException as e:
            print(f"[ERROR] WiFi sensor connection error: {e}")
            print(f"[INFO] 请确认:")
            print(f"       1. 已连接到ESP32_Server WiFi")
            print(f"       2. ESP32的IP地址是否为 {self.sensor_ip}")
            print(f"[INFO] Will use simulation mode")
            self.is_connected = False
            return False
        except json.JSONDecodeError as e:
            print(f"[ERROR] Failed to parse sensor response: {e}")
            self.is_connected = False
            return False

    def set_mode(self, mode):
        """
        设置工作模式（leg.ino不支持模式切换，此函数仅记录本地模式）

        Args:
            mode (int): 1=只角度, 2=只拉力, 3=角度+拉力

        Returns:
            bool: 切换成功返回True
        """
        if mode not in [1, 2, 3]:
            print(f"[ERROR] 无效的模式: {mode}，请使用 1、2 或 3")
            return False

        mode_names = {
            1: "角度模式 (Angle Only)",
            2: "拉力模式 (Force Only)",
            3: "全部模式 (Angle + Force)"
        }

        # leg.ino不支持模式切换API，仅在本地记录模式用于数据过滤
        self.current_mode = mode
        print(f"[OK] 本地模式已设置为: 模式{mode} - {mode_names[mode]}")
        print(f"[INFO] 注意: leg.ino始终返回所有数据，此模式仅用于本地数据过滤")
        return True

    def simulate_sensor_data(self, test_type):
        """Enhanced sensor data simulation with realistic patterns"""
        data = {
            'timestamp': datetime.now().isoformat(),
            'test_type': test_type,
            'data_quality': random.uniform(0.85, 1.0)  # Simulate data quality
        }

        current_time = time.time()

        if test_type in ['force test', 'force and angle test']:
            # Enhanced force simulation with realistic rehabilitation patterns
            base_force = 50  # Base force in Newtons

            # Simulate fatigue effect (decreasing force over time)
            fatigue_factor = max(0.7, 1 - (current_time % 60) / 300)

            # Add periodic muscle contraction pattern
            contraction_pattern = 20 * np.sin(current_time * 0.8) * fatigue_factor

            # Add some controlled noise
            noise = random.gauss(0, 5)

            force_value = max(0, base_force + contraction_pattern + noise)
            data['force_value'] = round(force_value, 2)

        if test_type in ['angle test', 'force and angle test']:
            # Enhanced angle simulation with realistic joint movement
            base_angle = 90  # Base angle in degrees

            # Simulate range of motion exercise
            rom_pattern = 30 * np.sin(current_time * 0.4)

            # Add slight tremor/instability
            tremor = 2 * np.sin(current_time * 3) * random.uniform(0.5, 1.0)

            # Add controlled noise
            noise = random.gauss(0, 1)

            angle_value = max(0, min(180, base_angle + rom_pattern + tremor + noise))
            data['angle_value'] = round(angle_value, 2)

        return data

    def read_sensor_data(self, test_type):
        """
        通过WiFi读取传感器数据（ESP32）

        Args:
            test_type: 测试类型

        Returns:
            dict: 传感器数据
        """
        if self.is_connected:
            try:
                # 通过WiFi HTTP获取ESP32传感器数据
                response = requests.get(
                    f"{self.sensor_url_base}/data",
                    timeout=2  # 较短的超时时间以便实时更新
                )

                if response.status_code == 200:
                    sensor_data = response.json()
                    # ESP32直接返回数据，格式: {"s1": X, "s2": Y, "y": Z, "f": W}
                    data = self.parse_wifi_data(sensor_data, test_type)
                    if data:
                        # 简化日志输出
                        log_parts = []
                        if 'force_value' in data:
                            log_parts.append(f"F:{data['force_value']:.1f}N")
                        if 'angle_value' in data:
                            log_parts.append(f"Y:{data['angle_value']:.1f}°")
                        print(f"[RX] {' | '.join(log_parts)}")
                        return data

            except requests.exceptions.RequestException as e:
                print(f"[ERROR] WiFi data reading error: {e}")
            except json.JSONDecodeError as e:
                print(f"[ERROR] Failed to parse sensor data: {e}")

        # Fallback to simulation
        return self.simulate_sensor_data(test_type)

    def parse_wifi_data(self, sensor_data, test_type):
        """
        解析从WiFi传感器(ESP32)接收的数据

        leg.ino数据格式: {"angle": virtual_angle, "yaw": angleY1, "force": force_N}

        Args:
            sensor_data: 从传感器接收的原始数据（leg.ino格式）
            test_type: 测试类型

        Returns:
            dict: 解析后的数据
        """
        data = {
            'timestamp': datetime.now().isoformat(),
            'test_type': test_type,
            'data_quality': 1.0  # ESP32不提供quality，默认为1.0
        }

        try:
            # 解析拉力数据 (leg.ino的'force'字段)
            if test_type in ['force test', 'force and angle test']:
                force = sensor_data.get('force')
                if force is not None:
                    data['force_value'] = float(force)

            # 解析角度数据 (leg.ino的'yaw'字段 - MPU6050的Y轴角度)
            if test_type in ['angle test', 'force and angle test']:
                # 优先使用yaw（真实MPU6050角度），其次使用angle（虚拟角度）
                yaw = sensor_data.get('yaw')
                angle = sensor_data.get('angle')

                if yaw is not None:
                    data['angle_value'] = float(yaw)
                elif angle is not None:
                    data['angle_value'] = float(angle)

            # 额外保存虚拟角度和真实角度信息
            if 'angle' in sensor_data:
                data['virtual_angle'] = float(sensor_data['angle'])
            if 'yaw' in sensor_data:
                data['yaw_angle'] = float(sensor_data['yaw'])

            # 如果没有解析到任何数据，返回None
            if 'force_value' not in data and 'angle_value' not in data:
                return None

        except Exception as e:
            print(f"[ERROR] WiFi data parsing error: {e}")
            return None

        return data

    def send_command(self, command, servo1=None, servo2=None):
        """
        通过WiFi发送命令到传感器（ESP32 leg.ino）

        Args:
            command: 命令字符串 (例如: 'a11', 'a12', 'b11', 'b12', 'exit')
            servo1: 舵机1角度 (0-200，可选，leg.ino支持0-200度)
            servo2: 舵机2角度 (0-200，可选)

        Returns:
            bool: 成功返回True
        """
        if not self.is_connected:
            print("[WARN] WiFi not connected, command not sent")
            return False

        try:
            # 构建请求数据（leg.ino使用form data格式）
            if command:
                # 发送控制命令 (a11, a12, b11, b12, exit等)
                payload = {'command': command}
            elif servo1 is not None and servo2 is not None:
                # 发送舵机角度控制（leg.ino只使用servo1控制主舵机）
                payload = {
                    'servo1': int(servo1),
                    'servo2': int(servo2)  # servo2保留但leg.ino可能不使用
                }
            else:
                print("[ERROR] Must provide either command or servo angles")
                return False

            response = requests.post(
                f"{self.sensor_url_base}/control",
                data=payload,  # leg.ino使用form data而不是JSON
                timeout=self.timeout
            )

            if response.status_code == 200 and response.text == 'ok':
                if command:
                    print(f"[OK] Command sent successfully: {command}")
                    if command in ['a11', 'a12', 'b11', 'b12']:
                        print(f"[INFO] Training mode activated: {command}")
                    elif command == 'exit':
                        print(f"[INFO] Training mode deactivated")
                else:
                    print(f"[OK] Servo angle set: {servo1}° (range: 0-200)")
                return True
            else:
                print(f"[ERROR] ESP32 responded: {response.text} (status: {response.status_code})")
                return False

        except requests.exceptions.RequestException as e:
            print(f"[ERROR] Failed to send command: {e}")
            return False

    def save_to_database(self, data, session_id, user_id=None):
        """Save sensor data to database with enhanced error handling"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute('''
                INSERT INTO sensor_data
                (test_type, force_value, angle_value, session_id, user_id, data_quality)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                data['test_type'],
                data.get('force_value'),
                data.get('angle_value'),
                session_id,
                user_id,
                data.get('data_quality', 1.0)
            ))
            conn.commit()

        except Exception as e:
            print(f"[ERROR] Database insertion error: {e}")
            conn.rollback()
        finally:
            conn.close()

    def create_training_session(self, user_id, test_types, session_config=None):
        """Create enhanced training session"""
        session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{str(uuid.uuid4())[:8]}"

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute('''
                INSERT INTO training_sessions
                (session_id, user_id, start_time, test_types, session_config, status)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                session_id,
                user_id,
                datetime.now(),
                json.dumps(test_types),
                json.dumps(session_config) if session_config else None,
                'active'
            ))
            conn.commit()
            print(f"[OK] Training session created: {session_id}")

        except Exception as e:
            print(f"[ERROR] Session creation error: {e}")
            conn.rollback()
        finally:
            conn.close()

        return session_id

    def end_training_session(self, session_id, notes=None):
        """End training session with enhanced logging"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            # Get session start time
            cursor.execute(
                'SELECT start_time FROM training_sessions WHERE session_id = ?',
                (session_id,)
            )
            result = cursor.fetchone()

            if result:
                start_time = datetime.fromisoformat(result[0])
                duration = int((datetime.now() - start_time).total_seconds())

                cursor.execute('''
                    UPDATE training_sessions
                    SET end_time = ?, duration = ?, status = ?, notes = ?
                    WHERE session_id = ?
                ''', (datetime.now(), duration, 'completed', notes, session_id))

                conn.commit()
                print(f"[OK] Session {session_id} completed - Duration: {duration}s")
            else:
                print(f"[ERROR] Session {session_id} not found")

        except Exception as e:
            print(f"[ERROR] Session end error: {e}")
            conn.rollback()
        finally:
            conn.close()

    def get_session_data(self, session_id):
        """Get session data with enhanced filtering"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute('''
                SELECT timestamp, test_type, force_value, angle_value, data_quality
                FROM sensor_data
                WHERE session_id = ?
                ORDER BY timestamp
            ''', (session_id,))

            data = cursor.fetchall()

            return [
                {
                    'timestamp': row[0],
                    'test_type': row[1],
                    'force_value': row[2],
                    'angle_value': row[3],
                    'data_quality': row[4]
                }
                for row in data
            ]

        except Exception as e:
            print(f"[ERROR] Error retrieving session data: {e}")
            return []
        finally:
            conn.close()

    def get_user_sessions(self, user_id, limit=50):
        """Get user's training sessions"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute('''
                SELECT session_id, start_time, end_time, duration, test_types, status, notes
                FROM training_sessions
                WHERE user_id = ?
                ORDER BY start_time DESC
                LIMIT ?
            ''', (user_id, limit))

            sessions = cursor.fetchall()

            return [
                {
                    'session_id': row[0],
                    'start_time': row[1],
                    'end_time': row[2],
                    'duration': row[3],
                    'test_types': json.loads(row[4]) if row[4] else [],
                    'status': row[5],
                    'notes': row[6]
                }
                for row in sessions
            ]

        except Exception as e:
            print(f"[ERROR] Error retrieving user sessions: {e}")
            return []
        finally:
            conn.close()

    def start_data_collection(self, test_type, session_id, user_id, duration=60, interval=0.1):
        """
        增强型数据采集 - WiFi通信版本

        Args:
            test_type: 'force test', 'angle test', 或 'force and angle test'
            session_id: 会话ID
            user_id: 用户ID
            duration: 持续时间（秒）
            interval: 采样间隔（秒）
        """
        # 根据 test_type 设置相应的模式
        mode_mapping = {
            'angle test': self.MODE_ANGLE,
            'force test': self.MODE_FORCE,
            'force and angle test': self.MODE_ALL
        }

        target_mode = mode_mapping.get(test_type, self.MODE_ALL)

        # 如果WiFi已连接，切换到目标模式
        if self.is_connected:
            self.set_mode(target_mode)

        self.is_running = True
        start_time = time.time()
        data_count = 0
        error_count = 0
        max_errors = 10

        print(f"[START] Starting {test_type} data collection via WiFi (Mode {target_mode})")
        print(f"[TIME] Duration: {duration}s, Interval: {interval}s")

        while self.is_running and (time.time() - start_time) < duration and error_count < max_errors:
            try:
                data = self.read_sensor_data(test_type)

                if data:
                    self.save_to_database(data, session_id, user_id)
                    data_count += 1

                    # Enhanced logging
                    status_parts = []
                    if data.get('force_value') is not None:
                        status_parts.append(f"Force: {data['force_value']:.2f}N")
                    if data.get('angle_value') is not None:
                        status_parts.append(f"Angle: {data['angle_value']:.2f}°")
                    if data.get('data_quality') is not None:
                        status_parts.append(f"Quality: {data['data_quality']:.2f}")

                    print(f"[{data_count:04d}] {' | '.join(status_parts)}")

                time.sleep(interval)

            except Exception as e:
                error_count += 1
                print(f"[ERROR] Data collection error #{error_count}: {e}")
                time.sleep(interval)  # Continue despite errors

        self.is_running = False

        if error_count >= max_errors:
            print(f"[WARN] Data collection stopped due to excessive errors ({error_count})")
        else:
            print(f"[OK] Data collection completed - {data_count} data points collected")

    def stop_data_collection(self):
        """Stop data collection gracefully"""
        self.is_running = False
        print('🛑 Data collection stop requested')

    def calibrate_sensors(self, test_type, calibration_duration=10):
        """Calibrate sensors for accurate measurements"""
        print(f"🔧 Starting sensor calibration for {test_type}...")

        calibration_data = []
        start_time = time.time()

        while (time.time() - start_time) < calibration_duration:
            data = self.read_sensor_data(test_type)
            if data:
                calibration_data.append(data)
            time.sleep(0.1)

        # Calculate calibration factors
        calibration_factors = {}

        if calibration_data:
            if test_type in ['force test', 'force and angle test']:
                forces = [d.get('force_value', 0) for d in calibration_data if d.get('force_value')]
                if forces:
                    baseline_force = np.mean(forces)
                    calibration_factors['force'] = 1.0 if baseline_force == 0 else 50.0 / baseline_force

            if test_type in ['angle test', 'force and angle test']:
                angles = [d.get('angle_value', 0) for d in calibration_data if d.get('angle_value')]
                if angles:
                    baseline_angle = np.mean(angles)
                    calibration_factors['angle'] = 1.0 if baseline_angle == 0 else 90.0 / baseline_angle

        print(f"[OK] Calibration completed: {calibration_factors}")
        return calibration_factors

    def export_session_data(self, session_id, format='csv'):
        """Export session data in various formats"""
        data = self.get_session_data(session_id)

        if format.lower() == 'csv':
            csv_content = "Timestamp,Test Type,Force Value (N),Angle Value (°),Data Quality\n"
            for item in data:
                csv_content += f"{item['timestamp']},{item['test_type']},{item.get('force_value', '')},{item.get('angle_value', '')},{item.get('data_quality', '')}\n"
            return csv_content

        elif format.lower() == 'json':
            return json.dumps(data, indent=2)

        else:
            raise ValueError(f"Unsupported export format: {format}")

    def get_system_diagnostics(self):
        """Get system diagnostics and health information"""
        diagnostics = {
            'timestamp': datetime.now().isoformat(),
            'database_status': 'unknown',
            'wifi_status': 'disconnected',
            'sensor_ip': self.sensor_ip,
            'sensor_port': self.sensor_port,
            'total_users': 0,
            'total_sessions': 0,
            'total_data_points': 0,
            'active_sessions': 0
        }

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Check database health
            cursor.execute('SELECT COUNT(*) FROM users')
            diagnostics['total_users'] = cursor.fetchone()[0]

            cursor.execute('SELECT COUNT(*) FROM training_sessions')
            diagnostics['total_sessions'] = cursor.fetchone()[0]

            cursor.execute('SELECT COUNT(*) FROM sensor_data')
            diagnostics['total_data_points'] = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM training_sessions WHERE status = 'active'")
            diagnostics['active_sessions'] = cursor.fetchone()[0]

            diagnostics['database_status'] = 'healthy'

            conn.close()

        except Exception as e:
            diagnostics['database_status'] = f'error: {str(e)}'

        # Check WiFi connection
        if self.is_connected:
            diagnostics['wifi_status'] = 'connected'
        else:
            diagnostics['wifi_status'] = 'simulation_mode'

        return diagnostics

    def close(self):
        """Close connections and cleanup"""
        self.is_running = False
        print("[OK] WiFi sensor data handler closed successfully")


# Testing and demonstration
if __name__ == "__main__":
    print("=" * 60)
    print("[TEST] TESTING ENHANCED SENSOR DATA HANDLER (WiFi)")
    print("=" * 60)

    # 使用WiFi传感器（修改为你的传感器IP）
    handler = EnhancedSensorDataHandler(sensor_ip='192.168.1.100', sensor_port=80)

    # Test database initialization
    diagnostics = handler.get_system_diagnostics()
    print(f"\n[INFO] System Diagnostics:")
    for key, value in diagnostics.items():
        print(f"   {key}: {value}")

    # Test WiFi connection
    handler.connect_wifi()

    # Create test session
    session_id = handler.create_training_session(
        user_id="test_user_123",
        test_types=['force test', 'angle test', 'force and angle test'],
        session_config={'duration': 10, 'interval': 0.5}
    )

    print(f"\n[ID] Test session created: {session_id}")

    # Test data collection for different test types
    test_types = ['force test', 'angle test', 'force and angle test']

    for test_type in test_types:
        print(f"\n[TEST] Testing {test_type}...")

        # Add delay between tests
        time.sleep(2)

        handler.start_data_collection(
            test_type=test_type,
            session_id=session_id,
            user_id="test_user_123",
            duration=5,  # Short duration for testing
            interval=0.5
        )

    # End session
    handler.end_training_session(session_id, notes="WiFi test session completed successfully")

    # Test data retrieval
    session_data = handler.get_session_data(session_id)
    print(f"\n[DATA] Retrieved {len(session_data)} data points from session")

    # Test data export
    csv_export = handler.export_session_data(session_id, 'csv')
    print(f"\n[EXPORT] CSV export size: {len(csv_export)} characters")

    # Final diagnostics
    final_diagnostics = handler.get_system_diagnostics()
    print(f"\n[INFO] Final System State:")
    for key, value in final_diagnostics.items():
        print(f"   {key}: {value}")

    # Cleanup
    handler.close()

    print("\n[OK] Enhanced sensor data handler (WiFi) testing completed!")
    print("=" * 60)
