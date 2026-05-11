# -*- coding: utf-8 -*-
"""
文档扫描器高级功能
包含手动角点选择、PDF导出等功能
"""

import cv2
import numpy as np
from typing import List, Optional, Tuple
from pathlib import Path


class ManualCornerSelector:
    """
    手动选择文档角点的交互式工具
    当自动检测失败时使用
    """

    def __init__(self):
        self.points = []
        self.original_image = None
        self.display_image = None
        self.window_name = "选择四个角点 (按ESC取消)"

    def mouse_callback(self, event, x, y, flags, param):
        """鼠标回调函数"""
        if event == cv2.EVENT_LBUTTONDOWN:
            if len(self.points) < 4:
                self.points.append([x, y])

                # 绘制点
                cv2.circle(self.display_image, (x, y), 5, (0, 0, 255), -1)

                # 绘制连接线
                if len(self.points) > 1:
                    cv2.line(self.display_image,
                            tuple(self.points[-2]),
                            tuple(self.points[-1]),
                            (0, 255, 0), 2)

                # 闭合四边形
                if len(self.points) == 4:
                    cv2.line(self.display_image,
                            tuple(self.points[-1]),
                            tuple(self.points[0]),
                            (0, 255, 0), 2)

                cv2.imshow(self.window_name, self.display_image)

                print(f"已选择点 {len(self.points)}: ({x}, {y})")

                if len(self.points) == 4:
                    print("四个角点已选择完毕，按任意键继续...")

    def select_corners(self, image: np.ndarray) -> Optional[np.ndarray]:
        """
        交互式选择文档角点

        Args:
            image: 输入图像

        Returns:
            四个角点的坐标数组 (4, 2)，如果取消返回None
        """
        self.original_image = image.copy()
        self.display_image = image.copy()
        self.points = []

        cv2.namedWindow(self.window_name)
        cv2.setMouseCallback(self.window_name, self.mouse_callback)

        print("=" * 50)
        print("手动选择文档角点模式")
        print("请按顺序点击: 左上 -> 右上 -> 右下 -> 左下")
        print("按 ESC 取消")
        print("=" * 50)

        while True:
            cv2.imshow(self.window_name, self.display_image)
            key = cv2.waitKey(1) & 0xFF

            if key == 27:  # ESC
                cv2.destroyWindow(self.window_name)
                print("已取消")
                return None

            if len(self.points) == 4 and key != 255:
                break

        cv2.destroyWindow(self.window_name)
        return np.array(self.points, dtype=np.float32)


class PDFExporter:
    """
    将扫描结果导出为PDF
    """

    @staticmethod
    def export_images_to_pdf(image_paths: List[str], output_path: str,
                             title: str = "Scanned Document"):
        """
        将多张图片合并为一个PDF文件

        需要安装: pip install Pillow

        Args:
            image_paths: 图片路径列表
            output_path: 输出PDF路径
            title: PDF标题
        """
        try:
            from PIL import Image
        except ImportError:
            print("错误: 需要安装 Pillow 库")
            print("请运行: pip install Pillow")
            return False

        if not image_paths:
            print("错误: 没有图片需要导出")
            return False

        # 打开所有图片
        images = []
        for img_path in image_paths:
            try:
                img = Image.open(img_path)
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                images.append(img)
            except Exception as e:
                print(f"警告: 无法加载 {img_path}: {e}")

        if not images:
            print("错误: 没有成功加载任何图片")
            return False

        # 保存为PDF
        first_image = images[0]
        other_images = images[1:] if len(images) > 1 else []

        first_image.save(
            output_path,
            "PDF",
            resolution=100.0,
            title=title,
            save_all=True,
            append_images=other_images
        )

        print(f"✓ PDF已保存: {output_path}")
        print(f"  包含 {len(images)} 页")
        return True


class BatchProcessor:
    """
    批量处理器
    """

    def __init__(self, scanner):
        self.scanner = scanner
        self.processed_files = []

    def process_directory(self, input_dir: str, output_dir: str,
                         enhance_mode: str = 'enhance') -> List[str]:
        """
        批量处理目录下的所有图片

        Args:
            input_dir: 输入目录
            output_dir: 输出目录
            enhance_mode: 增强模式

        Returns:
            处理成功的文件路径列表
        """
        input_path = Path(input_dir)
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # 支持的图片格式
        extensions = {'.png', '.jpg', '.jpeg', '.bmp', '.tif', '.tiff'}

        image_files = []
        for ext in extensions:
            image_files.extend(input_path.glob(f'*{ext}'))
            image_files.extend(input_path.glob(f'*{ext.upper()}'))

        self.processed_files = []

        for img_file in image_files:
            image = cv2.imread(str(img_file))
            if image is None:
                print(f"警告: 无法加载 {img_file.name}")
                continue

            result = self.scanner.scan(image, enhance_mode)

            output_file = output_path / f"scanned_{img_file.name}"
            cv2.imwrite(str(output_file), result.scanned)
            self.processed_files.append(str(output_file))

            status = "✓" if result.corners is not None else "△"
            print(f"{status} {img_file.name}")

        return self.processed_files

    def export_to_pdf(self, pdf_path: str, title: str = "Scanned Document") -> bool:
        """
        将处理结果导出为PDF

        Args:
            pdf_path: PDF输出路径
            title: 文档标题

        Returns:
            是否成功
        """
        return PDFExporter.export_images_to_pdf(
            self.processed_files, pdf_path, title
        )


class AutoEnhancer:
    """
    自动图像增强器
    根据图像特征自动选择最佳增强方案
    """

    @staticmethod
    def analyze_image_quality(image: np.ndarray) -> dict:
        """
        分析图像质量

        Returns:
            包含质量指标的字典
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # 亮度
        brightness = np.mean(gray)

        # 对比度 (标准差)
        contrast = np.std(gray)

        # 模糊度 (拉普拉斯方差)
        laplacian = cv2.Laplacian(gray, cv2.CV_64F)
        blur_score = laplacian.var()

        # 噪声估计
        denoised = cv2.medianBlur(gray, 5)
        noise = np.mean(np.abs(gray.astype(float) - denoised.astype(float)))

        return {
            'brightness': brightness,
            'contrast': contrast,
            'blur_score': blur_score,
            'noise_level': noise
        }

    @staticmethod
    def auto_enhance(image: np.ndarray) -> np.ndarray:
        """
        根据图像特征自动增强

        Args:
            image: 输入图像

        Returns:
            增强后的图像
        """
        quality = AutoEnhancer.analyze_image_quality(image)
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # 根据亮度调整
        if quality['brightness'] < 80:
            # 图像过暗，提高亮度
            image = cv2.convertScaleAbs(image, alpha=1.2, beta=30)
        elif quality['brightness'] > 180:
            # 图像过亮，降低亮度
            image = cv2.convertScaleAbs(image, alpha=0.9, beta=-20)

        # 根据对比度调整
        if quality['contrast'] < 40:
            # 对比度低，使用CLAHE增强
            lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
            l = clahe.apply(l)
            lab = cv2.merge([l, a, b])
            image = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)

        # 根据噪声水平降噪
        if quality['noise_level'] > 10:
            image = cv2.fastNlMeansDenoisingColored(image, None, 10, 10, 7, 21)

        return image


# 使用示例
if __name__ == "__main__":
    print("文档扫描器高级功能模块")
    print("=" * 50)
    print("包含:")
    print("  - ManualCornerSelector: 手动角点选择")
    print("  - PDFExporter: PDF导出")
    print("  - BatchProcessor: 批量处理器")
    print("  - AutoEnhancer: 自动图像增强")
