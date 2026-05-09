# -*- coding: utf-8 -*-
"""
文档扫描器 GUI 界面
使用 PyQt5 实现
"""

import sys
import os
from pathlib import Path

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFileDialog, QComboBox, QGroupBox,
    QScrollArea, QStatusBar, QMessageBox, QSlider, QCheckBox
)
from PyQt5.QtGui import QPixmap, QImage, QFont
from PyQt5.QtCore import Qt, QSize, QTimer

import cv2
import numpy as np

from scanner import DocumentScanner, DocumentResult, cv_imread, cv_imwrite


def cv2_to_qpixmap(cv2_image: np.ndarray) -> QPixmap:
    """将OpenCV图像转换为QPixmap"""
    if cv2_image is None:
        return QPixmap()

    # BGR转RGB
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


class ImageLabel(QLabel):
    """可缩放的图片标签 - 自动适应窗口大小"""

    def __init__(self, title: str = ""):
        super().__init__()
        self.title = title
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(200, 200)
        self.setStyleSheet("""
            QLabel {
                background-color: #2a2a2a;
                border: 2px dashed #555;
                border-radius: 5px;
                color: #888;
            }
        """)
        self.setText(f"{title}\n\n点击下方按钮加载图片")
        self._pixmap = None
        self._title = title

    def setPixmap(self, pixmap: QPixmap):
        self._pixmap = pixmap
        self._update_pixmap()

    def _update_pixmap(self):
        """根据窗口大小缩放图片"""
        if self._pixmap is None or self._pixmap.isNull():
            return

        # 获取label的可用大小
        label_size = self.size()

        # 保持纵横比缩放
        scaled_pixmap = self._pixmap.scaled(
            label_size.width() - 10,
            label_size.height() - 10,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )
        super().setPixmap(scaled_pixmap)

    def resizeEvent(self, event):
        """窗口大小改变时重新缩放图片"""
        super().resizeEvent(event)
        if self._pixmap is not None:
            self._update_pixmap()

    def clear(self):
        self._pixmap = None
        super().clear()
        self.setText(f"{self._title}\n\n点击下方按钮加载图片")


class MainWindow(QMainWindow):
    """主窗口"""

    def __init__(self):
        super().__init__()

        self.scanner = DocumentScanner()
        self.current_image = None
        self.current_result = None
        self.current_file_path = None
        self.cropped_image = None  # 保存裁剪后的图片，用于模式切换

        # 防抖定时器
        self._canny_timer = QTimer()
        self._canny_timer.setSingleShot(True)
        self._canny_timer.timeout.connect(self._apply_canny_change)
        self._blur_timer = QTimer()
        self._blur_timer.setSingleShot(True)
        self._blur_timer.timeout.connect(self._apply_blur_change)

        self.init_ui()

    def init_ui(self):
        """初始化界面"""
        self.setWindowTitle("文档扫描器 - 类似扫描全能王")
        self.setMinimumSize(1600, 900)
        self.resize(1800, 1000)

        # 主控件
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)

        # 左侧 - 原图和检测结果
        left_panel = QVBoxLayout()
        left_panel.setSpacing(10)

        # 原图
        original_group = QGroupBox("原始图片")
        original_layout = QVBoxLayout()
        self.original_label = ImageLabel("原始图片")
        original_layout.addWidget(self.original_label)
        original_group.setLayout(original_layout)
        left_panel.addWidget(original_group, 1)

        # 检测结果
        detected_group = QGroupBox("检测结果 (绿色框为检测到的文档)")
        detected_layout = QVBoxLayout()
        self.detected_label = ImageLabel("检测结果")
        detected_layout.addWidget(self.detected_label)
        detected_group.setLayout(detected_layout)
        left_panel.addWidget(detected_group, 1)

        main_layout.addLayout(left_panel, 2)

        # 中间 - 控制面板
        control_panel = QVBoxLayout()
        control_panel.setSpacing(15)

        # 文件操作
        file_group = QGroupBox("文件操作")
        file_layout = QVBoxLayout()

        btn_load = QPushButton("📷 加载图片")
        btn_load.setMinimumHeight(40)
        btn_load.clicked.connect(self.load_image)
        file_layout.addWidget(btn_load)

        btn_load_folder = QPushButton("📁 批量处理文件夹")
        btn_load_folder.setMinimumHeight(40)
        btn_load_folder.clicked.connect(self.load_folder)
        file_layout.addWidget(btn_load_folder)

        btn_save = QPushButton("💾 保存结果")
        btn_save.setMinimumHeight(40)
        btn_save.clicked.connect(self.save_result)
        file_layout.addWidget(btn_save)

        file_group.setLayout(file_layout)
        control_panel.addWidget(file_group)

        # 扫描控制
        scan_group = QGroupBox("扫描控制")
        scan_layout = QVBoxLayout()

        # 增强模式
        mode_label = QLabel("增强模式:")
        scan_layout.addWidget(mode_label)

        self.mode_combo = QComboBox()
        self.mode_combo.addItems([
            "scanner - 扫描仪效果",
            "original - 原图",
            "enhance - 增强对比度",
            "bw - 黑白文档",
            "magic_color - 魔法色彩"
        ])
        self.mode_combo.setCurrentIndex(0)
        self.mode_combo.currentIndexChanged.connect(self.update_enhance_mode)
        scan_layout.addWidget(self.mode_combo)

        # 自动检测开关
        self.auto_detect = QCheckBox("自动检测文档边缘")
        self.auto_detect.setChecked(True)
        scan_layout.addWidget(self.auto_detect)

        btn_scan = QPushButton("🔍 开始扫描")
        btn_scan.setMinimumHeight(50)
        btn_scan.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        btn_scan.clicked.connect(self.scan_document)
        scan_layout.addWidget(btn_scan)

        scan_group.setLayout(scan_layout)
        control_panel.addWidget(scan_group)

        # 参数调整
        param_group = QGroupBox("参数调整")
        param_layout = QVBoxLayout()

        # Canny 阈值
        param_layout.addWidget(QLabel("边缘检测灵敏度:"))
        self.canny_slider = QSlider(Qt.Horizontal)
        self.canny_slider.setRange(10, 100)
        self.canny_slider.setValue(50)
        self.canny_slider.valueChanged.connect(self.update_canny_threshold)
        param_layout.addWidget(self.canny_slider)

        # 高斯模糊核
        param_layout.addWidget(QLabel("模糊程度:"))
        self.blur_slider = QSlider(Qt.Horizontal)
        self.blur_slider.setRange(3, 15)
        self.blur_slider.setValue(5)
        self.blur_slider.setSingleStep(2)
        self.blur_slider.valueChanged.connect(self.update_blur_kernel)
        param_layout.addWidget(self.blur_slider)

        param_group.setLayout(param_layout)
        control_panel.addWidget(param_group)

        # 调试模式
        debug_group = QGroupBox("调试")
        debug_layout = QVBoxLayout()

        btn_debug = QPushButton("🔧 显示处理过程")
        btn_debug.clicked.connect(self.show_debug)
        debug_layout.addWidget(btn_debug)

        debug_group.setLayout(debug_layout)
        control_panel.addWidget(debug_group)

        control_panel.addStretch()

        main_layout.addLayout(control_panel)

        # 右侧 - 扫描结果
        right_panel = QVBoxLayout()
        right_panel.setSpacing(10)

        # 扫描结果
        result_group = QGroupBox("扫描结果")
        result_layout = QVBoxLayout()
        self.result_label = ImageLabel("扫描结果")
        result_layout.addWidget(self.result_label)
        result_group.setLayout(result_layout)
        right_panel.addWidget(result_group, 1)

        main_layout.addLayout(right_panel, 2)

        # 状态栏
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.statusBar.showMessage("就绪 - 请加载图片开始扫描")

    def load_image(self):
        """加载单张图片"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择图片",
            "",
            "图片文件 (*.png *.jpg *.jpeg *.bmp *.tif *.tiff);;所有文件 (*)"
        )

        if file_path:
            self.load_image_from_path(file_path)

    def load_image_from_path(self, file_path: str):
        """从路径加载图片"""
        self.current_file_path = file_path

        # 读取图片 (支持中文路径)
        image = cv_imread(file_path)
        if image is None:
            QMessageBox.warning(self, "错误", f"无法加载图片: {file_path}")
            return

        self.current_image = image
        self.cropped_image = None  # 清空裁剪图片

        # 显示原图
        self.original_label.setPixmap(cv2_to_qpixmap(image))

        # 清空其他显示
        self.detected_label.clear()
        self.result_label.clear()

        self.statusBar.showMessage(f"已加载: {Path(file_path).name}")

        # 自动扫描
        if self.auto_detect.isChecked():
            self.scan_document()

    def load_folder(self):
        """批量处理文件夹"""
        folder_path = QFileDialog.getExistingDirectory(self, "选择文件夹")
        if not folder_path:
            return

        # 获取所有图片
        image_extensions = {'.png', '.jpg', '.jpeg', '.bmp', '.tif', '.tiff'}
        image_files = []
        for ext in image_extensions:
            image_files.extend(Path(folder_path).glob(f'*{ext}'))
            image_files.extend(Path(folder_path).glob(f'*{ext.upper()}'))

        if not image_files:
            QMessageBox.information(self, "提示", "文件夹中没有找到图片文件")
            return

        # 创建输出文件夹
        output_folder = Path(folder_path) / "scanned"
        output_folder.mkdir(exist_ok=True)

        # 批量处理
        enhance_mode = self.get_current_enhance_mode()
        success_count = 0

        for i, img_path in enumerate(image_files):
            image = cv_imread(str(img_path))
            if image is None:
                continue

            result = self.scanner.scan(image, enhance_mode)

            # 保存结果 (支持中文路径)
            output_path = output_folder / f"scanned_{img_path.name}"
            cv_imwrite(str(output_path), result.scanned)
            success_count += 1

            self.statusBar.showMessage(f"处理中: {i+1}/{len(image_files)} - {img_path.name}")

        QMessageBox.information(
            self, "完成",
            f"批量处理完成!\n成功处理: {success_count}/{len(image_files)}\n输出目录: {output_folder}"
        )
        self.statusBar.showMessage("批量处理完成")

    def get_current_enhance_mode(self) -> str:
        """获取当前增强模式"""
        mode_text = self.mode_combo.currentText()
        return mode_text.split(" - ")[0]

    def update_enhance_mode(self):
        """更新增强模式 - 实时切换效果"""
        if self.cropped_image is not None:
            # 直接对裁剪后的图片应用新的增强效果
            enhance_mode = self.get_current_enhance_mode()
            enhanced = self.scanner.enhance_document(self.cropped_image, enhance_mode)
            self.result_label.setPixmap(cv2_to_qpixmap(enhanced))
            self.statusBar.showMessage(f"已切换增强模式: {enhance_mode}")

    def update_canny_threshold(self, value):
        """更新Canny阈值 - 带防抖"""
        self._canny_value = value
        self._canny_timer.start(200)  # 200ms后执行

    def _apply_canny_change(self):
        """实际应用Canny阈值变化"""
        self.scanner.canny_threshold1 = self._canny_value
        self.scanner.canny_threshold2 = self._canny_value + 100
        if self.current_image is not None:
            self.scan_document()

    def update_blur_kernel(self, value):
        """更新模糊核大小 - 带防抖"""
        self._blur_value = value
        self._blur_timer.start(200)  # 200ms后执行

    def _apply_blur_change(self):
        """实际应用模糊核变化"""
        value = self._blur_value if self._blur_value % 2 == 1 else self._blur_value + 1
        self.scanner.blur_kernel = value
        if self.current_image is not None:
            self.scan_document()

    def scan_document(self):
        """执行扫描"""
        if self.current_image is None:
            QMessageBox.warning(self, "提示", "请先加载图片")
            return

        enhance_mode = self.get_current_enhance_mode()

        # 执行扫描
        result, stages = self.scanner.detect_with_debug(self.current_image, enhance_mode)
        self.current_result = result

        # 保存裁剪后的图片（用于模式切换）
        if result.corners is not None:
            self.cropped_image = self.scanner.four_point_transform(self.current_image, result.corners)
        else:
            self.cropped_image = self.current_image.copy()

        # 显示检测过程
        for name, img in stages:
            if name == "Detected":
                self.detected_label.setPixmap(cv2_to_qpixmap(img))
            elif name == "Scanned":
                self.result_label.setPixmap(cv2_to_qpixmap(img))

        if result.corners is not None:
            self.statusBar.showMessage(
                f"扫描完成 - 检测到文档区域，增强模式: {enhance_mode}"
            )
        else:
            self.statusBar.showMessage("未检测到文档边界，已返回原图")

    def save_result(self):
        """保存结果"""
        if self.current_result is None:
            QMessageBox.warning(self, "提示", "没有可保存的结果")
            return

        default_name = "scanned_result.png"
        if self.current_file_path:
            default_name = f"scanned_{Path(self.current_file_path).name}"

        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "保存结果",
            default_name,
            "PNG图片 (*.png);;JPEG图片 (*.jpg);;所有文件 (*)"
        )

        if save_path:
            cv_imwrite(save_path, self.current_result.scanned)
            self.statusBar.showMessage(f"已保存: {save_path}")
            QMessageBox.information(self, "成功", f"文件已保存到:\n{save_path}")

    def show_debug(self):
        """显示调试窗口"""
        if self.current_image is None:
            QMessageBox.warning(self, "提示", "请先加载图片")
            return

        result, stages = self.scanner.detect_with_debug(self.current_image)

        # 创建调试窗口
        debug_window = QWidget()
        debug_window.setWindowTitle("调试 - 处理过程")
        debug_window.setMinimumSize(1400, 500)

        layout = QHBoxLayout(debug_window)

        for name, img in stages:
            group = QGroupBox(name)
            group_layout = QVBoxLayout()
            label = ImageLabel(name)
            label.setPixmap(cv2_to_qpixmap(img))
            group_layout.addWidget(label)
            group.setLayout(group_layout)
            layout.addWidget(group)

        debug_window.show()


def main():
    """主函数"""
    app = QApplication(sys.argv)

    # 设置应用样式
    app.setStyle('Fusion')

    # 设置字体
    font = QFont("Microsoft YaHei", 9)
    app.setFont(font)

    window = MainWindow()
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
