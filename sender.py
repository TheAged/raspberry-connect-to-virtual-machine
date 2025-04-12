#!/usr/bin/env python3
import cv2
import socket
import struct
import time

# --- 設定參數 ---
SERVER_IP = 'change to your vpn ip'         # 虛擬機 Tailscale IP
SERVER_PORT = 9999                 # 伺服器連接埠
RECONNECT_DELAY = 5                # 連線失敗重試延遲 (秒)
JPEG_QUALITY = 70                  # JPEG 壓縮品質 (0~100)
RESIZE_WIDTH = 640                 # 調整影像寬度 (0 表示不調整)

def connect_to_server():
    """持續嘗試連接至後端伺服器"""
    while True:
        try:
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            print(f"[INFO] 正在嘗試連接到 {SERVER_IP}:{SERVER_PORT} ...")
            client_socket.connect((SERVER_IP, SERVER_PORT))
            print("[INFO] 成功連接到伺服器！")
            return client_socket
        except socket.error as e:
            print(f"[ERROR] 連線失敗：{e}，{RECONNECT_DELAY} 秒後重試...")
            time.sleep(RECONNECT_DELAY)

def resize_frame(frame, target_width):
    """依目標寬度調整影像尺寸，同時保持原始長寬比"""
    if target_width > 0 and frame.shape[1] > target_width:
        # 以長寬比調整高度：new_height = 原高度 * (target_width / 原寬度)
        ratio = target_width / float(frame.shape[1])
        new_height = int(frame.shape[0] * ratio)
        return cv2.resize(frame, (target_width, new_height))
    return frame

def main():
    client_socket = None
    vid = None
    while True:  # 主循環：包含連線與攝影機初始化失敗時的重試機制
        try:
            # 確保 Socket 連線有效
            if client_socket is None or client_socket.fileno() == -1:
                if client_socket:
                    client_socket.close()
                client_socket = connect_to_server()

            # 確保攝影機已正確打開
            if vid is None or not vid.isOpened():
                print("[INFO] 正在打開攝影機...")
                vid = cv2.VideoCapture(0)
                if not vid.isOpened():
                    print("[ERROR] 無法開啟攝影機，請檢查連接與權限。")
                    time.sleep(RECONNECT_DELAY)
                    continue
                print("[INFO] 攝影機成功開啟。")

            # 讀取攝影機畫面
            ret, frame = vid.read()
            if not ret:
                print("[WARNING] 無法讀取影像幀，可能攝影機斷線。")
                vid.release()
                vid = None
                time.sleep(1)
                continue

            # 若設定了調整寬度則進行尺寸調整
            frame = resize_frame(frame, RESIZE_WIDTH)

            # 將影像編碼為 JPEG
            encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY]
            result, frame_encoded = cv2.imencode('.jpg', frame, encode_param)
            if not result:
                print("[ERROR] JPEG 編碼失敗。")
                continue

            # 傳送資料：先傳送 4 個 byte 的資料長度，再傳送 JPEG bytes
            data = frame_encoded.tobytes()
            size = len(data)
            client_socket.sendall(struct.pack(">L", size) + data)

            # 控制畫面傳送速率 (約 30 FPS)
            time.sleep(0.03)

        except (socket.error, ConnectionResetError, BrokenPipeError) as e:
            print(f"[ERROR] Socket 錯誤：{e}，嘗試重新連線...")
            if client_socket:
                client_socket.close()
            client_socket = None
            if vid and vid.isOpened():
                vid.release()
                vid = None
            time.sleep(RECONNECT_DELAY / 2)

        except KeyboardInterrupt:
            print("[INFO] 收到中斷訊號，正在關閉...")
            break

        except Exception as e:
            print(f"[ERROR] 未預期的錯誤：{e}")
            if client_socket:
                client_socket.close()
            client_socket = None
            if vid and vid.isOpened():
                vid.release()
                vid = None
            time.sleep(RECONNECT_DELAY)

    # 清理資源
    print("[INFO] 清理資源中...")
    if vid and vid.isOpened():
        vid.release()
        print("[INFO] 攝影機已釋放。")
    if client_socket:
        client_socket.close()
        print("[INFO] Socket 連線已關閉。")
    cv2.destroyAllWindows()
    print("[INFO] 程式結束。")

if __name__ == '__main__':
    main()
