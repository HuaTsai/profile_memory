#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import subprocess
import time
import requests
import notify2
from datetime import datetime
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, 
                             QLabel, QSystemTrayIcon, QMenu, QAction)
from PyQt5.QtCore import Qt, QTimer, pyqtSlot
from PyQt5.QtGui import QFont, QIcon, QColor, QPainter


class MemoryMonitorClient(QWidget):
    def __init__(self):
        super().__init__()
        notify2.init("Server Memory Monitor")
        self.setWindowTitle('Server Memory Monitor')
        
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        desktop = QApplication.desktop().availableGeometry()
        self.setGeometry(desktop.width() - 350, 30, 340, 600)
        
        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(10, 10, 10, 10)
        
        # 標題標籤
        self.time_label = QLabel("Time: --")
        self.time_label.setFont(QFont('Arial', 11, QFont.Bold))
        self.time_label.setStyleSheet("color: white;")
        self.layout.addWidget(self.time_label)
        
        # 狀態標籤
        self.status_label = QLabel("Status: Initializing...")
        self.status_label.setFont(QFont('Arial', 10))
        self.status_label.setStyleSheet("color: yellow;")
        self.layout.addWidget(self.status_label)
        
        # 總記憶體標籤
        self.total_mem_label = QLabel("Total Memory: --")
        self.total_mem_label.setFont(QFont('Arial', 10, QFont.Bold))
        self.total_mem_label.setStyleSheet("color: cyan;")
        self.layout.addWidget(self.total_mem_label)
        
        self.setLayout(self.layout)
        
        self.create_tray_icon()

        # API 設定
        self.api_base_url = "http://localhost:60001"
        self.ssh_tunnel_process = None
        self.container_labels = {}
        
        # 定時器
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_memory_usage)
        
        # 啟動 SSH tunnel 和初始化
        self.setup_ssh_tunnel()
        self.check_health()
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QColor(30, 30, 30, 200))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(self.rect(), 10, 10)
    
    def create_tray_icon(self):
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QIcon.fromTheme("dialog-information"))
        self.tray_icon.setVisible(True)
        self.tray_icon.setToolTip("Server Memory Monitor")

        tray_menu = QMenu(self)
        
        refresh_action = QAction("Refresh Now", self)
        refresh_action.triggered.connect(self.update_memory_usage)
        tray_menu.addAction(refresh_action)
        
        tray_menu.addSeparator()
        
        quit_action = QAction("Exit", self)
        quit_action.triggered.connect(self.cleanup_and_quit)
        tray_menu.addAction(quit_action)
        
        self.tray_icon.setContextMenu(tray_menu)
    
    def setup_ssh_tunnel(self):
        """建立 SSH tunnel"""
        try:
            # 檢查是否已經有 SSH tunnel 在運行
            check_cmd = ["pgrep", "-f", "ssh.*60001:localhost:60001.*basicai"]
            result = subprocess.run(check_cmd, capture_output=True, text=True)
            
            if result.returncode == 0 and result.stdout.strip():
                print(f"SSH tunnel already running (PID: {result.stdout.strip()})")
                self.status_label.setText("Status: SSH tunnel already active")
                self.status_label.setStyleSheet("color: lightgreen;")
                return
            
            # 建立新的 SSH tunnel
            print("Starting SSH tunnel...")
            self.ssh_tunnel_process = subprocess.Popen(
                ["ssh", "-L", "60001:localhost:60001", "basicai", "-N"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            # 等待一下讓 tunnel 建立
            time.sleep(2)
            
            if self.ssh_tunnel_process.poll() is None:
                print("SSH tunnel established successfully")
                self.status_label.setText("Status: SSH tunnel established")
                self.status_label.setStyleSheet("color: lightgreen;")
            else:
                raise Exception("SSH tunnel process terminated unexpectedly")
                
        except Exception as e:
            print(f"Failed to setup SSH tunnel: {e}")
            self.status_label.setText("Status: SSH tunnel failed")
            self.status_label.setStyleSheet("color: red;")
    
    def check_health(self):
        """檢查 API 健康狀態"""
        try:
            response = requests.get(f"{self.api_base_url}/health", timeout=5)
            if response.status_code == 200:
                data = response.json()
                print(f"Health check OK: {data}")
                self.status_label.setText(f"Status: {data.get('status', 'unknown')}")
                self.status_label.setStyleSheet("color: lightgreen;")
                
                # 開始定期更新
                self.update_memory_usage()
                return True
            else:
                raise Exception(f"Health check failed: {response.status_code}")
        except Exception as e:
            print(f"Health check error: {e}")
            self.status_label.setText("Status: API not available")
            self.status_label.setStyleSheet("color: red;")
            
            # 30 秒後重試
            QTimer.singleShot(30_000, self.check_health)
            return False
    
    @pyqtSlot()
    def update_memory_usage(self):
        """從 API 獲取記憶體資料"""
        try:
            # 獲取系統記憶體資訊
            mem_response = requests.get(f"{self.api_base_url}/available-memories", timeout=10)
            # 獲取容器資訊
            container_response = requests.get(f"{self.api_base_url}/memories", timeout=10)
            
            if mem_response.status_code == 200 and container_response.status_code == 200:
                mem_data = mem_response.json()
                container_data = container_response.json()
                
                # 更新系統記憶體顯示
                total_mem = mem_data.get('total_memory', 0)
                used_mem = mem_data.get('used_memory', 0)
                avail_mem = mem_data.get('available_memory', 0)
                self.total_mem_label.setText(
                    f"Total: {total_mem:.2f} GB | Used: {used_mem:.2f} GB | Available: {avail_mem:.2f} GB"
                )
                self.total_mem_label.setStyleSheet("color: cyan;")
                
                # 解析容器資料
                self.parse_memory_data(container_data)
                
                # 更新時間
                self.time_label.setText(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                self.time_label.setStyleSheet("color: white;")
                
                self.status_label.setText("Status: Connected")
                self.status_label.setStyleSheet("color: lightgreen;")
                
                # 1 分鐘後再次更新
                self.timer.setInterval(60 * 1000)
                self.timer.start()
            else:
                raise Exception(f"API returned {mem_response.status_code}/{container_response.status_code}")
                
        except requests.exceptions.Timeout:
            print("Request timeout")
            self.status_label.setText("Status: Request timeout")
            self.status_label.setStyleSheet("color: orange;")
            # 30 秒後重試
            self.timer.setInterval(30_000)
            self.timer.start()
            
        except requests.exceptions.ConnectionError:
            print("Connection error")
            self.status_label.setText("Status: Connection failed")
            self.status_label.setStyleSheet("color: red;")
            # 30 秒後重試
            self.timer.setInterval(30_000)
            self.timer.start()
            
        except Exception as e:
            print(f"Update error: {e}")
            self.status_label.setText("Status: Error")
            self.status_label.setStyleSheet("color: red;")
            # 30 秒後重試
            self.timer.setInterval(30_000)
            self.timer.start()
    
    def parse_memory_data(self, containers_data):
        """解析容器記憶體資料"""
        try:
            # 移除舊的容器標籤（保留前兩個固定標籤）
            for key in list(self.container_labels.keys()):
                widget = self.container_labels[key]
                self.layout.removeWidget(widget)
                widget.deleteLater()
            self.container_labels.clear()
            
            # 按照容器名稱排序
            sorted_containers = sorted(containers_data, key=lambda x: x.get("Name", "").lower())
            
            # 高記憶體容器列表
            high_memory_containers = []
            
            # 處理每個容器
            for container in sorted_containers:
                name = container.get("Name", "unknown")
                mem_usage = container.get("MemUsage", "N/A")
                mem_perc = container.get("MemPerc", "N/A")
                
                # 建立標籤顯示容器資訊
                label_text = f"{name}: {mem_usage} ({mem_perc})"
                label = QLabel(label_text)
                label.setFont(QFont('Arial', 9))
                label.setStyleSheet("color: lightgray; padding: 2px;")
                label.setWordWrap(True)
                
                self.layout.addWidget(label)
                self.container_labels[name] = label
                
                # 檢查高記憶體使用
                try:
                    perc_value = float(mem_perc.replace('%', ''))
                    if perc_value > 80:
                        high_memory_containers.append((name, perc_value))
                        label.setStyleSheet("color: red; padding: 2px;")
                except ValueError:
                    pass
            
            # 如果有容器記憶體使用率超過 80%，發送通知
            if high_memory_containers:
                for name, perc in high_memory_containers:
                    noti = notify2.Notification(
                        "High Memory Warning",
                        f"Container '{name}' is using {perc:.1f}% memory",
                        "dialog-warning"
                    )
                    noti.set_urgency(notify2.URGENCY_CRITICAL)
                    noti.show()
            
            print(f"Updated {len(containers_data)} containers")
            
        except Exception as e:
            print(f"Parse memory data error: {e}")
    
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton:
            self.move(event.globalPos() - self.drag_position)
            event.accept()
    
    def cleanup_and_quit(self):
        """清理資源並退出"""
        print("Cleaning up...")
        
        # 注意：我們不關閉 SSH tunnel，因為它可能是由其他程序建立的
        # 如果需要的話，用戶可以手動關閉
        
        QApplication.quit()


if __name__ == "__main__":
    import signal
    
    def signal_handler(sig, frame):
        print("\nExiting application...")
        QApplication.quit()
    
    signal.signal(signal.SIGINT, signal_handler)
    
    app = QApplication(sys.argv)
    monitor = MemoryMonitorClient()
    monitor.show()
    
    # 讓 Python 能處理 Ctrl+C
    timer = QTimer()
    timer.start(500)
    timer.timeout.connect(lambda: None)
    
    sys.exit(app.exec_())
