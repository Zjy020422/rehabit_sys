# coding:utf-8
"""
WiFi传感器测试程序
通过WiFi HTTP请求向传感器发送测试数据

替代原来的串口通信方式
"""

import random
import time
import requests
import json

# WiFi传感器配置
SENSOR_IP = "192.168.1.100"  # 修改为你的传感器IP地址
SENSOR_PORT = 80
SENSOR_URL = f"http://{SENSOR_IP}:{SENSOR_PORT}/api/data"

print("=" * 60)
print("WiFi传感器测试程序")
print("=" * 60)
print(f"传感器地址: {SENSOR_URL}")
print("按 Ctrl+C 停止发送")
print("=" * 60)

# 测试WiFi连接
try:
    print("\n正在测试WiFi连接...")
    response = requests.get(f"http://{SENSOR_IP}:{SENSOR_PORT}/api/health", timeout=5)
    if response.status_code == 200:
        print(f"✅ WiFi传感器连接成功: {SENSOR_IP}:{SENSOR_PORT}")
    else:
        print(f"⚠️ WiFi传感器响应异常，状态码: {response.status_code}")
        print("提示: 请确认传感器IP地址和端口是否正确")
except requests.exceptions.RequestException as e:
    print(f"❌ WiFi传感器连接失败: {e}")
    print("提示: 请检查以下项目:")
    print("  1. 传感器是否已开机并连接到WiFi")
    print("  2. 电脑和传感器是否在同一网络")
    print("  3. SENSOR_IP 是否设置正确")
    print("\n将继续运行，每次发送时会尝试连接...")

print("\n开始发送测试数据...\n")

# 发送测试数据
send_count = 0
error_count = 0

while True:
    try:
        # 生成随机测试数据
        test_data = {
            "force": round(random.uniform(10, 100), 2),  # 拉力: 10-100N
            "angle": round(random.uniform(0, 180), 2),   # 角度: 0-180度
            "timestamp": time.time(),
            "quality": random.uniform(0.85, 1.0)
        }

        # 通过WiFi HTTP POST发送数据到传感器
        response = requests.post(
            SENSOR_URL,
            json=test_data,
            timeout=5
        )

        if response.status_code == 200:
            send_count += 1
            print(f"[{send_count:04d}] ✅ 发送成功 -> Force: {test_data['force']:.2f}N, Angle: {test_data['angle']:.2f}°")
            error_count = 0  # 重置错误计数
        else:
            error_count += 1
            print(f"[WARN] ⚠️ 发送失败，HTTP状态码: {response.status_code}")

    except requests.exceptions.Timeout:
        error_count += 1
        print(f"[ERROR] ❌ 请求超时 (错误次数: {error_count})")

    except requests.exceptions.ConnectionError:
        error_count += 1
        print(f"[ERROR] ❌ 连接失败，无法连接到传感器 (错误次数: {error_count})")

    except requests.exceptions.RequestException as e:
        error_count += 1
        print(f"[ERROR] ❌ WiFi通信错误: {e} (错误次数: {error_count})")

    except KeyboardInterrupt:
        print("\n\n" + "=" * 60)
        print("程序已停止")
        print(f"总计发送: {send_count} 次")
        print(f"错误次数: {error_count} 次")
        print("=" * 60)
        break

    except Exception as e:
        error_count += 1
        print(f"[ERROR] ❌ 未知错误: {e}")

    # 如果连续错误超过10次，提示用户
    if error_count > 10:
        print("\n" + "=" * 60)
        print("⚠️ 警告: 连续错误超过10次")
        print("建议检查:")
        print("  1. WiFi传感器是否正常运行")
        print("  2. 网络连接是否稳定")
        print("  3. IP地址是否正确")
        print("=" * 60 + "\n")
        error_count = 0  # 重置错误计数

    # 每秒发送一次
    time.sleep(1)
