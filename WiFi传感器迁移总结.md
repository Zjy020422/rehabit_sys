# WiFi传感器通信迁移总结

## 修改日期
2025-12-17

## 修改概述
将demo目录中所有涉及传感器通信的代码从**串口通信（Serial）**迁移到**WiFi HTTP通信**。

---

## 文件修改清单

### 1. enhanced_sensor_handler.py（核心传感器处理器）

**修改类型：** 文件替换

**具体操作：**
- 将原串口版本 `enhanced_sensor_handler.py` 重命名为 `enhanced_sensor_handler_serial.py`（作为备份）
- 将WiFi版本 `enhanced_sensor_handler_wifi.py` 重命名为 `enhanced_sensor_handler.py`

**主要变化：**
- ✅ 移除 `serial` 库依赖，改用 `requests` 库
- ✅ 移除 `serial_conn` 属性，改用 `sensor_ip`, `sensor_port`, `is_connected`
- ✅ 移除 `connect_serial()` 方法，改用 `connect_wifi()`
- ✅ 移除 `set_mode()` 中的串口指令发送，改用 HTTP POST请求
- ✅ 移除 `read_sensor_data()` 中的串口读取，改用 HTTP GET请求
- ✅ 新增 `parse_wifi_data()` 方法解析WiFi数据
- ✅ 新增 `send_command()` 方法发送WiFi命令

**WiFi API端点：**
```python
GET  http://{sensor_ip}:{sensor_port}/api/health    # 健康检查
POST http://{sensor_ip}:{sensor_port}/api/mode      # 设置模式
GET  http://{sensor_ip}:{sensor_port}/api/data      # 获取数据
POST http://{sensor_ip}:{sensor_port}/api/command   # 发送命令
```

---

### 2. app.py（Flask后端应用）

**修改类型：** 参数修改

**修改位置：** `init_components()` 函数（第33-45行）

**修改前：**
```python
def init_components():
    global data_handler, analyzer, advisor

    # Initialize enhanced data handler
    data_handler = EnhancedSensorDataHandler()

    # Try to connect serial port
    data_handler.connect_serial()
```

**修改后：**
```python
def init_components():
    global data_handler, analyzer, advisor

    # Initialize enhanced data handler with WiFi
    # 修改为你的传感器WiFi IP地址
    data_handler = EnhancedSensorDataHandler(
        sensor_ip='192.168.1.100',  # WiFi传感器IP地址
        sensor_port=80               # WiFi传感器端口
    )

    # Try to connect WiFi sensor
    data_handler.connect_wifi()
```

**修改位置：** `/api/system/status` 端点（第908-914行）

**修改前：**
```python
'serial_port': 'connected' if data_handler.serial_conn and data_handler.serial_conn.is_open else 'simulation_mode',
```

**修改后：**
```python
'wifi_sensor': 'connected' if data_handler.is_connected else 'simulation_mode',
'sensor_ip': data_handler.sensor_ip if hasattr(data_handler, 'sensor_ip') else 'N/A',
```

**注意事项：**
- app.py中已有WiFi传感器相关的API端点（第342-595行），无需修改
- `/api/sensor/command` - 向WiFi传感器发送命令
- `/api/sensor/data` - 从WiFi传感器获取数据
- `/api/sensor/stream/start` - 开始WiFi传感器数据流
- `/api/sensor/stream/stop` - 停止WiFi传感器数据流

---

### 3. computer send.py（测试数据发送工具）

**修改类型：** 完全重写

**修改前：** 使用串口通信
```python
import serial.tools.list_ports
serialFd = serial.Serial(serialName, 115200, timeout=60)
serialFd.write(str(x).encode('utf-8'))
```

**修改后：** 使用WiFi HTTP通信
```python
import requests

SENSOR_IP = "192.168.1.100"
SENSOR_PORT = 80
SENSOR_URL = f"http://{SENSOR_IP}:{SENSOR_PORT}/api/data"

test_data = {
    "force": round(random.uniform(10, 100), 2),
    "angle": round(random.uniform(0, 180), 2),
    "timestamp": time.time(),
    "quality": random.uniform(0.85, 1.0)
}

response = requests.post(SENSOR_URL, json=test_data, timeout=5)
```

**新增功能：**
- ✅ 自动检测WiFi连接状态
- ✅ 连续错误监控（超过10次提示）
- ✅ 详细的错误提示和诊断信息
- ✅ 发送统计（成功次数、错误次数）

---

### 4. training.html（训练页面）

**状态：** ✅ 已经使用WiFi通信，无需修改

**WiFi通信实现：**（第953-986行）
```javascript
// 发送命令到Flask后端API，后端转发到WiFi传感器
function sendToSensor(feedbackCode) {
    fetch('http://localhost:5000/api/sensor/command', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            command: feedbackCode,
            mode: trainingState.mode,
            force: trainingState.force,
            angle: trainingState.angle
        })
    })
}
```

**WiFi数据轮询：**（第1107-1133行）
```javascript
// 每200ms轮询一次WiFi传感器数据
function startWiFiSensorPolling() {
    window.sensorPollingInterval = setInterval(async () => {
        const response = await fetch('http://localhost:5000/api/sensor/data');
        const result = await response.json();
        if (result.success && result.data) {
            receiveSensorData(result.data);
        }
    }, 200);
}
```

---

### 5. testing.html（测试页面）

**状态：** ✅ 已经使用WiFi通信，无需修改

**WiFi通信实现：** 通过Flask后端API
- 使用 `/api/testing/start` 启动测试
- 使用 `/api/testing/stop` 停止测试
- 使用 `/api/testing/realtime/{session_id}` 获取实时数据

所有通信都是通过HTTP协议，没有直接的串口依赖。

---

## 配置参数说明

### WiFi传感器配置

**需要在以下文件中设置WiFi传感器IP地址：**

1. **app.py**（第39行）
```python
sensor_ip='192.168.1.100',  # 修改为你的WiFi传感器IP
```

2. **computer send.py**（第15行）
```python
SENSOR_IP = "192.168.1.100"  # 修改为你的WiFi传感器IP
```

3. **enhanced_sensor_handler.py**（第721行，测试代码）
```python
handler = EnhancedSensorDataHandler(sensor_ip='192.168.1.100', sensor_port=80)
```

---

## 通信协议对比

### 串口通信（旧）
| 特性 | 实现方式 |
|------|----------|
| 连接方式 | USB串口（COM端口） |
| 数据格式 | 文本字符串（如 "A:45.67 F:75.50"） |
| 通信库 | `pyserial` |
| 速度 | 115200 波特率 |
| 范围 | 有线连接，受线缆长度限制 |
| 可靠性 | 依赖USB连接稳定性 |

### WiFi通信（新）
| 特性 | 实现方式 |
|------|----------|
| 连接方式 | WiFi网络（HTTP协议） |
| 数据格式 | JSON（如 `{"force": 75.5, "angle": 45.67}`） |
| 通信库 | `requests` |
| 速度 | 取决于WiFi速度（通常更快） |
| 范围 | 无线连接，WiFi覆盖范围内 |
| 可靠性 | 依赖WiFi网络稳定性 |

---

## 迁移优势

### ✅ 优点

1. **无线自由**
   - 摆脱USB线缆束缚
   - 传感器可远程放置
   - 更灵活的使用场景

2. **更好的扩展性**
   - 可同时连接多个WiFi传感器
   - 便于分布式部署
   - 支持远程访问

3. **标准化协议**
   - 使用HTTP/JSON标准协议
   - 更容易与其他系统集成
   - 跨平台兼容性更好

4. **更强的可维护性**
   - 网络调试工具丰富
   - 日志和监控更方便
   - 易于升级和维护

### ⚠️ 注意事项

1. **网络依赖**
   - 需要稳定的WiFi网络
   - 传感器和服务器需在同一网络

2. **延迟**
   - WiFi可能比串口有更高的延迟
   - 需要优化轮询间隔

3. **安全性**
   - 需要考虑WiFi网络安全
   - 建议使用加密和身份验证

4. **配置复杂度**
   - 需要配置IP地址
   - 需要确保网络连通性

---

## 测试验证步骤

### 1. 配置WiFi传感器IP
```bash
# 修改以下文件中的IP地址为你的传感器IP
- app.py (第39行)
- computer send.py (第15行)
```

### 2. 测试WiFi连接
```bash
cd F:\work\2025work\sure\anthony\demo
python "computer send.py"
```

预期输出：
```
============================================================
WiFi传感器测试程序
============================================================
传感器地址: http://192.168.1.100:80/api/data
按 Ctrl+C 停止发送
============================================================

正在测试WiFi连接...
✅ WiFi传感器连接成功: 192.168.1.100:80

开始发送测试数据...

[0001] ✅ 发送成功 -> Force: 45.23N, Angle: 87.65°
[0002] ✅ 发送成功 -> Force: 78.12N, Angle: 134.21°
...
```

### 3. 测试Flask应用
```bash
python app.py
```

预期输出：
```
================================================================================
🏥 Regenix - ADVANCED REHABILITATION ANALYTICS PLATFORM
================================================================================
[OK] Enhanced database schema created successfully
[OK] WiFi sensor connected successfully: 192.168.1.100:80
✅ System initialization completed!
🌐 Web server starting at: http://localhost:5000
```

### 4. 访问系统状态API
```bash
curl http://localhost:5000/api/system/status
```

预期返回：
```json
{
  "success": true,
  "status": {
    "database": "online",
    "total_users": 0,
    "total_sessions": 0,
    "active_sessions": 0,
    "wifi_sensor": "connected",
    "sensor_ip": "192.168.1.100",
    "ai_service": "simulation_mode",
    "system_time": "2025-12-17T15:00:00",
    "version": "1.0.0"
  }
}
```

### 5. 测试Web界面
1. 打开浏览器访问 http://localhost:5000
2. 登录系统
3. 进入 Training 页面，测试传感器数据采集
4. 进入 Testing 页面，进行完整测试

---

## 文件备份说明

### 备份文件
- `enhanced_sensor_handler_serial.py` - 原串口版本（已备份）

### 保留原因
- 如需回退到串口通信，可恢复此文件
- 作为参考对照

### 恢复方法（如果需要回退）
```bash
cd F:\work\2025work\sure\anthony\demo

# 1. 恢复串口版本
mv enhanced_sensor_handler.py enhanced_sensor_handler_wifi.py
mv enhanced_sensor_handler_serial.py enhanced_sensor_handler.py

# 2. 修改app.py init_components()
#    将 sensor_ip/sensor_port 参数改回 port='COM9', baudrate=115200
#    将 connect_wifi() 改回 connect_serial()

# 3. 恢复 computer send.py（需要从备份恢复）
```

---

## 常见问题排查

### 问题1: WiFi传感器连接失败
**症状：**
```
❌ WiFi传感器连接失败: Connection refused
```

**解决方案：**
1. 检查传感器是否开机并连接到WiFi
2. 确认IP地址是否正确
3. 确认电脑和传感器在同一网络
4. 检查防火墙设置
5. 尝试 ping 传感器IP

### 问题2: 数据采集失败
**症状：**
```
[ERROR] WiFi data reading error: Timeout
```

**解决方案：**
1. 检查WiFi网络稳定性
2. 增加超时时间（在代码中修改timeout参数）
3. 检查传感器是否正常工作
4. 查看传感器日志

### 问题3: 模拟模式运行
**症状：**
```
[WARN] WiFi未连接，使用模拟模式
```

**说明：**
- 这是正常的后备机制
- 系统会使用模拟数据继续运行
- 不影响基本功能测试

---

## 后续优化建议

### 1. 性能优化
- [ ] 实现WebSocket实时通信（替代HTTP轮询）
- [ ] 添加数据缓存机制
- [ ] 优化网络请求并发

### 2. 安全性增强
- [ ] 添加传感器身份验证
- [ ] 实现HTTPS加密通信
- [ ] 添加访问控制

### 3. 功能增强
- [ ] 支持多传感器同时连接
- [ ] 添加传感器自动发现功能
- [ ] 实现传感器状态监控

### 4. 用户体验
- [ ] 添加传感器配置界面
- [ ] 显示实时连接状态
- [ ] 优化错误提示

---

## 联系与支持

如有问题或需要帮助，请参考：
- WiFi传感器通信说明.md
- 项目README.md

---

**修改完成时间：** 2025-12-17
**版本：** v2.0 (WiFi)
