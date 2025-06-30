#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import json
import subprocess
import notify2
from datetime import datetime
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, 
                             QLabel, QSystemTrayIcon, QMenu, QAction)
from PyQt5.QtCore import Qt, QTimer, pyqtSlot
from PyQt5.QtGui import QFont, QIcon, QColor, QPainter

class MemoryMonitor(QWidget):
    def __init__(self):
        super().__init__()
        notify2.init("Server Memory Monitor")
        self.setWindowTitle('Server Memory Monitor')
        
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        desktop = QApplication.desktop().availableGeometry()
        self.setGeometry(desktop.width() - 250, 30, 240, 160)
        
        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(10, 10, 10, 10)
        
        self.time_label = QLabel("Time: --")
        self.time_label.setFont(QFont('Arial', 10))
        self.time_label.setStyleSheet("color: white;")
        self.layout.addWidget(self.time_label)
        
        self.total_mem_label = QLabel("Total Memory: -- GB")
        self.total_mem_label.setFont(QFont('Arial', 10))
        self.total_mem_label.setStyleSheet("color: white;")
        self.layout.addWidget(self.total_mem_label)
        
        self.used_mem_label = QLabel("Used: -- GB")
        self.used_mem_label.setFont(QFont('Arial', 10))
        self.used_mem_label.setStyleSheet("color: white;")
        self.layout.addWidget(self.used_mem_label)
        
        self.avail_mem_label = QLabel("Available: -- GB")
        self.avail_mem_label.setFont(QFont('Arial', 10))
        self.avail_mem_label.setStyleSheet("color: white;")
        self.layout.addWidget(self.avail_mem_label)
        
        self.docker_label = QLabel("Docker Containers: -- ")
        self.docker_label.setFont(QFont('Arial', 10))
        self.docker_label.setStyleSheet("color: white;")
        self.layout.addWidget(self.docker_label)
        
        self.setLayout(self.layout)
        
        self.create_tray_icon()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_memory_usage)

        self.file_path = "/tmp/memory_usage.json"
        self.update_memory_usage()
    
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
        
        quit_action = QAction("Exit", self)
        quit_action.triggered.connect(QApplication.quit)
        tray_menu.addAction(quit_action)
        
        self.tray_icon.setContextMenu(tray_menu)
    
    @pyqtSlot()
    def update_memory_usage(self):
        try:
            server_name = "basicai"
            remote_path = "~/memory_usage.json"

            print("run rsync command...")
            cmd = ["rsync", "--timeout=10", "-avz", f"{server_name}:{remote_path}", self.file_path]
            subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            self.parse_memory_data()

            self.timer.setInterval(10 * 60 * 1000)  # 10 minutes
            self.timer.start()
            
        except subprocess.CalledProcessError as e:
            print(f"rsync failed: {e}")
            self.time_label.setText(f"Update failed: {datetime.now().strftime('%H:%M:%S')}")
            self.time_label.setStyleSheet("color: red;")

            self.timer.setInterval(30_000)  # Retry after 30 seconds
            self.timer.start()
        except Exception as e:
            print(f"Error: {e}")
            self.time_label.setText(f"Error: {datetime.now().strftime('%H:%M:%S')}")
            self.time_label.setStyleSheet("color: red;")

            self.timer.setInterval(30_000)  # Retry after 30 seconds
            self.timer.start()
    
    def parse_memory_data(self):
        try:
            with open(self.file_path, 'r') as f:
                data = json.load(f)
            
            self.time_label.setText(f"Time: {data.get('time', '--')}")
            self.time_label.setStyleSheet("color: white;")
            
            self.total_mem_label.setText(f"Total Memory: {data.get('total_memory', '--')} GB")
            self.used_mem_label.setText(f"Used: {data.get('used_memory', '--')} GB")
            self.avail_mem_label.setText(f"Available: {data.get('available_memory', '--')} GB")

            if data.get('available_memory', 0) < data.get('total_memory', 0) * 0.1:
                noti = notify2.Notification("Low Memory Warning",
                                        "Available memory is below 10% of total memory", "dialog-warning")
                noti.set_urgency(notify2.URGENCY_CRITICAL)
                noti.show()

            docker_info = ""
            for key, value in data.items():
                if key not in ['time', 'total_memory', 'available_memory', 'used_memory', 'dataset-datadayschedulemessagejob', 'annotation-hourschedulejob', 'user-dayschedulemessagejob']:
                    docker_info += f"{key}: {value} GB\n"
            
            if docker_info:
                self.docker_label.setText("Docker Containers:")
                for i, line in enumerate(docker_info.strip().split('\n')):
                    if i >= len(self.layout) - 5:
                        label = QLabel(line)
                        label.setFont(QFont('Arial', 10))
                        label.setStyleSheet("color: white;")
                        self.layout.addWidget(label)
                    else:
                        widget = self.layout.itemAt(i + 5).widget()
                        if isinstance(widget, QLabel):
                            widget.setText(line)
            else:
                self.docker_label.setText("Docker Containers: None")
            
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


if __name__ == "__main__":
    import signal
    
    def signal_handler(sig, frame):
        print("\nExiting application...")
        QApplication.quit()
    
    signal.signal(signal.SIGINT, signal_handler)
    
    app = QApplication(sys.argv)
    monitor = MemoryMonitor()
    monitor.show()
    
    timer = QTimer()
    timer.start(500)
    timer.timeout.connect(lambda: None)
    
    sys.exit(app.exec_())
