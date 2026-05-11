# -*- coding: utf-8 -*-
"""
摄像头实时扫描模块
实现类似扫描全能王的实时边界检测和拍照扫描
"""

import cv2
import numpy as np
from pathlib import Path

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QComboBox, QMessageBox, QFileDialog, QStackedWidget, QWidget
)
from PyQt5.QtGui import QPixmap, QFont
from PyQt5.QtCore import Qt, QTimer

from scanner import DocumentScanner, cv_imwrite
import sys
import os

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# cv2_to_qpixmap 在 gui.py 中定义，这里重新定义
def cv2_to_qpixmap(cv2_image):
    """将OpenCV图像转换为QPixmap"""
    import cv2
    import numpy as np
    from PyQt5.QtGui import QPixmap, QImage

    if cv2_image is None:
        return QPixmap()

    if len(cv2_image.shape) == 3:
        rgb = cv2.cvtColor(cv2_image, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        bytes_per_line = ch * w
        qimg = QImage(rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
    else:
        h, w = cv2_image.shape
        bytes_per_line = w
        qimg = QImage(cv2_image.data, w, h, bytes_per_line, QImage.Format_Grayscale8)

    return QPixmap.fromImage(qimg)


class CameraScanner(QDialog):
    """摄像头实时扫描窗口"""

    def __init__(self, parent=None):
        super().__init__(parent)

        self.scanner = DocumentScanner()
        self.cap = None
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frame)

        self.current_frame = None
        self.captured_image = None
        self.result_image = None
        self.corners = None

        self.enhance_mode = 'scanner'

        self.init_ui()

    def init_ui(self):
        """初始化界面"""
        self.setWindowTitle("摄像头扫描")
        self.setMinimumSize(800, 700)
        self.resize(900, 800)

        layout = QVBoxLayout(self)

        # 使用堆叠控件切换预览/结果
        self.stack = QStackedWidget()

        # === 预览页面 ===
        preview_page = QWidget()
        preview_layout = QVBoxLayout(preview_page)

        # 预览标签
        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setMinimumSize(640, 480)
        self.preview_label.setStyleSheet("""
            QLabel {
                background-color: #1a1a1a;
                border: 2px solid #333;
                border-radius: 5px;
            }
        """)
        self.preview_label.setText("正在启动摄像头...")
        preview_layout.addWidget(self.preview_label)

        # 状态提示
        self.status_label = QLabel("请将文档放入摄像头视野")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("color: #888; font-size: 14px;")
        preview_layout.addWidget(self.status_label)

        self.stack.addWidget(preview_page)

        # === 结果页面 ===
        result_page = QWidget()
        result_layout = QVBoxLayout(result_page)

        self.result_label = QLabel()
        self.result_label.setAlignment(Qt.AlignCenter)
        self.result_label.setMinimumSize(640, 480)
        self.result_label.setStyleSheet("""
            QLabel {
                background-color: #2a2a2a;
                border: 2px dashed #555;
                border-radius: 5px;
            }
        """)
        result_layout.addWidget(self.result_label)

        self.stack.addWidget(result_page)

        layout.addWidget(self.stack)

        # === 控制区域 ===
        control_widget = QWidget()
        control_layout = QVBoxLayout(control_widget)

        # 增强模式选择
        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel("增强模式:"))

        self.mode_combo = QComboBox()
        self.mode_combo.addItems([
            "scanner - 扫描仪效果",
            "original - 原图",
            "enhance - 增强对比度",
            "bw - 黑白文档",
            "magic_color - 魔法色彩"
        ])
        self.mode_combo.currentIndexChanged.connect(self.on_mode_changed)
        mode_layout.addWidget(self.mode_combo)
        mode_layout.addStretch()

        control_layout.addLayout(mode_layout)

        # 按钮区域
        btn_layout = QHBoxLayout()

        # 预览模式的按钮
        self.btn_capture = QPushButton("📷 拍照")
        self.btn_capture.setMinimumHeight(50)
        self.btn_capture.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-size: 16px;
                font-weight: bold;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        self.btn_capture.clicked.connect(self.capture_photo)

        self.btn_switch_camera = QPushButton("🔄 切换摄像头")
        self.btn_switch_camera.clicked.connect(self.switch_camera)

        self.btn_close = QPushButton("✖ 关闭")
        self.btn_close.clicked.connect(self.close)

        btn_layout.addWidget(self.btn_capture)
        btn_layout.addWidget(self.btn_switch_camera)
        btn_layout.addWidget(self.btn_close)

        control_layout.addLayout(btn_layout)

        # 结果模式的按钮（初始隐藏）
        self.result_btn_layout = QHBoxLayout()

        self.btn_retake = QPushButton("🔄 重拍")
        self.btn_retake.setMinimumHeight(45)
        self.btn_retake.clicked.connect(self.retake_photo)

        self.btn_save = QPushButton("💾 保存")
        self.btn_save.setMinimumHeight(45)
        self.btn_save.setStyleSheet("background-color: #2196F3; color: white;")
        self.btn_save.clicked.connect(self.save_result)

        self.btn_apply = QPushButton("✓ 应用滤镜")
        self.btn_apply.setMinimumHeight(45)
        self.btn_apply.setStyleSheet("background-color: #FF9800; color: white;")
        self.btn_apply.clicked.connect(self.apply_filter)

        self.result_btn_layout.addWidget(self.btn_retake)
        self.result_btn_layout.addWidget(self.btn_apply)
        self.result_btn_layout.addWidget(self.btn_save)

        control_layout.addLayout(self.result_btn_layout)

        # 初始隐藏结果按钮
        for i in range(self.result_btn_layout.count()):
            widget = self.result_btn_layout.itemAt(i).widget()
            if widget:
                widget.hide()

        # 隐藏预览按钮的辅助函数
        self.preview_buttons = [self.btn_capture, self.btn_switch_camera]

        layout.addWidget(control_widget)

    def start_camera(self):
        """启动摄像头"""
        if self.cap is not None:
            self.cap.release()

        self.cap = cv2.VideoCapture(0)

        if not self.cap.isOpened():
            QMessageBox.warning(self, "错误", "无法打开摄像头")
            return False

        # 设置分辨率
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

        self.timer.start(33)  # ~30fps
        return True

    def update_frame(self):
        """更新预览帧"""
        if self.cap is None or not self.cap.isOpened():
            return

        ret, frame = self.cap.read()
        if not ret:
            return

        # 水平翻转（镜像效果）
        frame = cv2.flip(frame, 1)

        self.current_frame = frame.copy()

        # 检测文档边界
        corners = self.scanner.detect_document(frame)

        # 在预览上绘制边界
        display = frame.copy()
        if corners is not None:
            corners_int = corners.astype(np.int32)
            # 绘制半透明填充
            overlay = display.copy()
            cv2.fillPoly(overlay, [corners_int], (0, 255, 0))
            cv2.addWeighted(overlay, 0.2, display, 0.8, 0, display)
            # 绘制边界线
            cv2.polylines(display, [corners_int], True, (0, 255, 0), 3)
            # 绘制角点
            for pt in corners_int:
                cv2.circle(display, tuple(pt), 8, (0, 0, 255), -1)
                cv2.circle(display, tuple(pt), 10, (255, 255, 255), 2)

            self.status_label.setText("✓ 已检测到文档边界")
            self.status_label.setStyleSheet("color: #4CAF50; font-size: 14px; font-weight: bold;")
        else:
            self.status_label.setText("请将文档放入摄像头视野")
            self.status_label.setStyleSheet("color: #888; font-size: 14px;")

        # 显示预览
        pixmap = cv2_to_qpixmap(display)
        scaled = pixmap.scaled(
            self.preview_label.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )
        self.preview_label.setPixmap(scaled)

    def capture_photo(self):
        """拍照"""
        if self.current_frame is None:
            QMessageBox.warning(self, "提示", "没有可用的画面")
            return

        # 停止预览
        self.timer.stop()

        self.captured_image = self.current_frame.copy()

        # 检测并处理
        self.corners = self.scanner.detect_document(self.captured_image)

        # 应用扫描
        self.process_and_display()

        # 切换到结果页面
        self.stack.setCurrentIndex(1)

        # 切换按钮显示
        self.toggle_buttons(show_result=True)

    def process_and_display(self):
        """处理并显示结果"""
        if self.captured_image is None:
            return

        if self.corners is not None:
            # 裁剪并增强
            result = self.scanner.scan(self.captured_image, self.enhance_mode)
            self.result_image = result.scanned
        else:
            # 未检测到边界，只应用滤镜
            self.result_image = self.scanner.enhance_document(
                self.captured_image, self.enhance_mode
            )

        # 显示结果
        pixmap = cv2_to_qpixmap(self.result_image)
        scaled = pixmap.scaled(
            self.result_label.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )
        self.result_label.setPixmap(scaled)

    def on_mode_changed(self):
        """增强模式改变"""
        mode_text = self.mode_combo.currentText()
        self.enhance_mode = mode_text.split(" - ")[0]

        # 如果已有结果，重新应用滤镜
        if self.result_image is not None and self.stack.currentIndex() == 1:
            self.process_and_display()

    def apply_filter(self):
        """重新应用当前滤镜"""
        if self.captured_image is not None:
            self.process_and_display()

    def retake_photo(self):
        """重拍"""
        self.captured_image = None
        self.result_image = None
        self.corners = None

        # 切换到预览页面
        self.stack.setCurrentIndex(0)

        # 切换按钮显示
        self.toggle_buttons(show_result=False)

        # 重新启动预览
        if self.cap is not None and self.cap.isOpened():
            self.timer.start(33)

    def toggle_buttons(self, show_result: bool):
        """切换按钮显示"""
        for btn in self.preview_buttons:
            btn.setVisible(not show_result)

        for i in range(self.result_btn_layout.count()):
            widget = self.result_btn_layout.itemAt(i).widget()
            if widget:
                widget.setVisible(show_result)

    def save_result(self):
        """保存结果"""
        if self.result_image is None:
            QMessageBox.warning(self, "提示", "没有可保存的结果")
            return

        default_name = "scanned_photo.png"
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "保存结果",
            default_name,
            "PNG图片 (*.png);;JPEG图片 (*.jpg);;所有文件 (*)"
        )

        if save_path:
            cv_imwrite(save_path, self.result_image)
            QMessageBox.information(self, "成功", f"文件已保存到:\n{save_path}")

    def switch_camera(self):
        """切换摄像头"""
        # 简单实现：释放当前摄像头，尝试打开下一个
        if self.cap is not None:
            self.cap.release()

        # 尝试下一个摄像头索引
        for i in range(1, 5):
            self.cap = cv2.VideoCapture(i)
            if self.cap.isOpened():
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
                return

        # 如果没有其他摄像头，重新打开默认
        self.start_camera()

    def closeEvent(self, event):
        """关闭事件"""
        self.timer.stop()
        if self.cap is not None:
            self.cap.release()
        event.accept()

    def showEvent(self, event):
        """显示事件 - 启动摄像头"""
        super().showEvent(event)
        self.start_camera()
