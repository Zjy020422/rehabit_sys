import sqlite3
import serial
from datetime import datetime
import numpy as np
import time
import random
import json
import uuid
import re

class EnhancedSensorDataHandler:
    """
    增强型传感器数据处理器 - 支持单角度三模式系统

    模式定义：
    MODE_ANGLE = 1  # 只获取角度
    MODE_FORCE = 2  # 只获取拉力
    MODE_ALL = 3    # 获取角度和拉力
    """

    # 模式常量
    MODE_ANGLE = 1
    MODE_FORCE = 2
    MODE_ALL = 3

    def __init__(self, db_path='rehabtech_pro.db', port='COM9', baudrate=115200):
        self.db_path = db_path
        self.port = port
        self.baudrate = baudrate
        self.serial_conn = None
        self.is_running = False
        self.current_mode = self.MODE_ALL  # 默认模式3
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

    def connect_serial(self):
        """Connect to serial port (COM9 Receiver)"""
        try:
            if self.port:
                self.serial_conn = serial.Serial(self.port, baudrate=self.baudrate, timeout=1)
                print(f'[OK] Serial port connected successfully: {self.port}')
                time.sleep(2)  # 等待连接稳定
                return True
            else:
                print('[WARN] Serial port not specified, using simulation mode')
                return False
        except Exception as e:
            print(f"[ERROR] Serial port connection error: {e}")
            return False

    def set_mode(self, mode):
        """
        设置工作模式并发送指令到Receiver

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

        try:
            if self.serial_conn and self.serial_conn.is_open:
                # 1. 第一次清空缓冲区
                self.serial_conn.reset_input_buffer()
                self.serial_conn.reset_output_buffer()

                # 2. 等待任何在途数据到达（ESP-NOW + 串口传输延迟）
                time.sleep(0.5)

                # 3. 第二次清空缓冲区（清除等待期间到达的数据）
                self.serial_conn.reset_input_buffer()
                self.serial_conn.reset_output_buffer()
                time.sleep(0.1)

                # 4. 发送模式切换指令到Receiver
                command = f"MODE:{mode}\n"
                self.serial_conn.write(command.encode('utf-8'))
                self.serial_conn.flush()

                # 5. 等待并读取确认消息
                time.sleep(0.5)
                confirmation_received = False
                timeout = time.time() + 2.0  # 2秒超时

                while time.time() < timeout:
                    if self.serial_conn.in_waiting > 0:
                        line = self.serial_conn.readline().decode('utf-8', errors='ignore').strip()
                        if f"MODE:{mode}" in line:
                            confirmation_received = True
                            break
                    time.sleep(0.1)

                # 6. 清空剩余的确认消息
                time.sleep(0.3)
                while self.serial_conn.in_waiting > 0:
                    self.serial_conn.readline()

                self.current_mode = mode
                print(f"[OK] 模式已切换到: 模式{mode} - {mode_names[mode]}")

                if not confirmation_received:
                    print(f"[WARN] 未收到确认消息，但已发送指令")

                return True
            else:
                print("[ERROR] 串口未连接，无法切换模式")
                return False

        except Exception as e:
            print(f"[ERROR] 切换模式失败: {e}")
            return False

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
        """Read data from sensors with error handling"""
        if self.serial_conn and self.serial_conn.is_open:
            try:
                line = self.serial_conn.readline().decode('utf-8').strip()
                print(f"[RX] Serial data received: {line}")
                if line:
                    data = self.parse_serial_data(line, test_type)
                    return data
            except Exception as e:
                print(f"[ERROR] Serial data reading error: {e}")
        
        # Fallback to simulation
        return self.simulate_sensor_data(test_type)
    
    def parse_serial_data(self, line, test_type):
        """
        解析串口数据 - 支持新的单角度格式

        数据格式：
        - 模式1: A:45.67
        - 模式2: F:75.50
        - 模式3: A:45.67 F:75.50
        """
        data = {
            'timestamp': datetime.now().isoformat(),
            'test_type': test_type,
            'data_quality': 1.0
        }

        try:
            # 跳过状态消息
            if "Receiver" in line or "Command" in line or "MODE" in line:
                return None

            # 解析角度数据 (A:xx.xx)
            angle_match = re.search(r'A:([\d.]+)', line)
            if angle_match and test_type in ['angle test', 'force and angle test']:
                data['angle_value'] = float(angle_match.group(1))

            # 解析拉力数据 (F:xx.xx)
            force_match = re.search(r'F:([\d.]+)', line)
            if force_match and test_type in ['force test', 'force and angle test']:
                data['force_value'] = float(force_match.group(1))

            # 如果没有解析到任何数据，返回None
            if 'force_value' not in data and 'angle_value' not in data:
                return None

        except Exception as e:
            print(f"[ERROR] Serial data parsing error: {e}")
            return None

        return data

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
        增强型数据采集 - 支持三种模式自动切换

        Args:
            test_type: 'force test', 'angle test', 或 'force and angle test'
        """
        # 根据 test_type 设置相应的模式
        mode_mapping = {
            'angle test': self.MODE_ANGLE,
            'force test': self.MODE_FORCE,
            'force and angle test': self.MODE_ALL
        }

        target_mode = mode_mapping.get(test_type, self.MODE_ALL)

        # 如果串口已连接，切换到目标模式
        if self.serial_conn and self.serial_conn.is_open:
            self.set_mode(target_mode)

        self.is_running = True
        start_time = time.time()
        data_count = 0
        error_count = 0
        max_errors = 10

        print(f"[START] Starting {test_type} data collection (Mode {target_mode})")
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
            'serial_status': 'disconnected',
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
        
        # Check serial connection
        if self.serial_conn and self.serial_conn.is_open:
            diagnostics['serial_status'] = 'connected'
        else:
            diagnostics['serial_status'] = 'simulation_mode'
        
        return diagnostics

    def close(self):
        """Close connections and cleanup"""
        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.close()
            print("[CLOSE] Serial connection closed")
        
        self.is_running = False
        print("[OK] Sensor data handler closed successfully")


# Testing and demonstration
if __name__ == "__main__":
    print("=" * 60)
    print("[TEST] TESTING ENHANCED SENSOR DATA HANDLER")
    print("=" * 60)

    handler = EnhancedSensorDataHandler()

    # Test database initialization
    diagnostics = handler.get_system_diagnostics()
    print(f"\n[INFO] System Diagnostics:")
    for key, value in diagnostics.items():
        print(f"   {key}: {value}")

    # Test sensor connection
    handler.connect_serial()

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

        # Add delay between tests to ensure previous mode change completes
        # and buffers clear to prevent command queue buildup
        time.sleep(2)

        handler.start_data_collection(
            test_type=test_type,
            session_id=session_id,
            user_id="test_user_123",
            duration=5,  # Short duration for testing
            interval=0.5
        )
    
    # End session
    handler.end_training_session(session_id, notes="Test session completed successfully")

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
    
    print("\n[OK] Enhanced sensor data handler testing completed!")
    print("=" * 60)