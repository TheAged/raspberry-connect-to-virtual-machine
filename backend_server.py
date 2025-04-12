#!/usr/bin/env python3
from flask import Flask, Response
import socket
import struct
import threading
import time
import traceback

# --- 設定參數 ---
LISTEN_IP = '0.0.0.0'
LISTEN_PORT = 9999
WEB_PORT = 5000
MAX_CLIENTS = 5

app = Flask(__name__)
latest_frame_jpeg = None
frame_lock = threading.Lock()

def recvall(conn, n):
    """接收指定長度的資料；若連線中斷則回傳 None"""
    data = b""
    while len(data) < n:
        packet = conn.recv(n - len(data))
        if not packet:
            return None
        data += packet
    return data

def socket_server_thread():
    """建立 Socket 伺服器，接收來自 sender 端的影像資料"""
    global latest_frame_jpeg
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((LISTEN_IP, LISTEN_PORT))
    server_socket.listen(MAX_CLIENTS)
    print(f"[INFO] Socket 伺服器正在監聽 {LISTEN_IP}:{LISTEN_PORT}")

    payload_size = struct.calcsize(">L")
    while True:
        conn = None
        addr = None
        try:
            conn, addr = server_socket.accept()
            print(f"[INFO] 接受來自 {addr} 的連線")
            while True:
                # 先接收固定大小的長度資訊
                packed_msg_size = recvall(conn, payload_size)
                if not packed_msg_size:
                    print(f"[WARNING] 客戶端 {addr} 斷線 (接收長度失敗)")
                    break

                msg_size = struct.unpack(">L", packed_msg_size)[0]
                # 再接收具體影像資料
                frame_data = recvall(conn, msg_size)
                if not frame_data:
                    print(f"[WARNING] 客戶端 {addr} 斷線 (接收影像資料失敗)")
                    break

                # 更新最新影像，確保線程安全
                with frame_lock:
                    latest_frame_jpeg = frame_data
        except Exception as e:
            print(f"[ERROR] Socket 執行緒錯誤：{e}")
            traceback.print_exc()
        finally:
            if conn:
                print(f"[INFO] 關閉來自 {addr} 的連線")
                conn.close()
            time.sleep(0.5)

def generate_frames():
    """持續產生 MJPEG 串流幀"""
    while True:
        with frame_lock:
            frame = latest_frame_jpeg
        if frame is None:
            time.sleep(0.1)
            continue
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
        time.sleep(0.03)

@app.route('/')
def index():
    vm_tailscale_ip = "change to your virtual vpn ip"
    # 這裡請替換為您的虛擬機 Tailscale IP
    return f"""
    <html>
    <head><title>樹莓派影像串流 (Tailscale)</title></head>
    <body>
        <h1>來自樹莓派的即時影像 (透過 Tailscale)</h1>
        <p>請確保使用虛擬機的 Tailscale IP 訪問此頁面:
         http://{vm_tailscale_ip}:{WEB_PORT}</p>
        <img src="/video_feed" width="640" height="480">
        <p>伺服器時間: <span id="time"></span></p>
        <script>
            function updateTime() {{
                document.getElementById('time').innerText = new Date().toLocaleTimeString();
            }}
            setInterval(updateTime, 1000);
            updateTime();
        </script>
    </body>
    </html>
    """

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
    # 啟動 Socket 影像接收執行緒
    socket_thread = threading.Thread(target=socket_server_thread, daemon=True)
    socket_thread.start()

    print(f"[INFO] Flask 伺服器啟動中，請透過 http://{LISTEN_IP}:{WEB_PORT} 訪問")
    app.run(host='0.0.0.0', port=WEB_PORT, debug=False, threaded=True)
