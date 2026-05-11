# -*- coding: utf-8 -*-
"""
文档扫描器命令行版本
支持单张图片和批量处理
"""

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np

from scanner import DocumentScanner, cv_imread, cv_imwrite


def process_single(scanner: DocumentScanner, input_path: str, output_path: str,
                   enhance_mode: str, show: bool = False):
    """处理单张图片"""
    # 读取图片 (支持中文路径)
    image = cv_imread(input_path)
    if image is None:
        print(f"错误: 无法加载图片 {input_path}")
        return False

    # 扫描
    result = scanner.scan(image, enhance_mode)

    # 保存 (支持中文路径)
    cv_imwrite(output_path, result.scanned)

    status = "检测到文档" if result.corners is not None else "未检测到文档边界"
    print(f"✓ {Path(input_path).name} -> {Path(output_path).name} ({status})")

    # 显示结果
    if show:
        # 显示检测过程
        display = image.copy()
        if result.corners is not None:
            cv2.drawContours(display, [result.corners], -1, (0, 255, 0), 3)
            for i, pt in enumerate(result.corners):
                cv2.circle(display, tuple(pt), 10, (0, 0, 255), -1)

        cv2.imshow("Original + Detection", display)
        cv2.imshow("Scanned Result", result.scanned)
        print("按任意键继续...")
        cv2.waitKey(0)
        cv2.destroyAllWindows()

    return True


def main():
    parser = argparse.ArgumentParser(
        description="文档扫描器 - 类似扫描全能王，自动检测文档边缘并矫正裁剪",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 单张图片处理
  python cli.py input.jpg -o output.jpg

  # 指定增强模式
  python cli.py input.jpg -o output.jpg -m bw

  # 批量处理文件夹
  python cli.py ./images -o ./output --batch

  # 处理并显示结果
  python cli.py input.jpg -o output.jpg --show

增强模式:
  scanner      - 扫描仪效果 (默认，模拟真实扫描仪)
  original     - 保持原图
  enhance      - 增强对比度
  bw           - 黑白文档
  magic_color  - 魔法色彩
        """
    )

    parser.add_argument("input", help="输入图片路径或文件夹路径")
    parser.add_argument("-o", "--output", required=True, help="输出图片路径或文件夹路径")
    parser.add_argument("-m", "--mode", default="scanner",
                       choices=["scanner", "original", "enhance", "bw", "magic_color"],
                       help="增强模式 (默认: scanner)")
    parser.add_argument("--batch", action="store_true",
                       help="批量处理模式 (输入输出都应为文件夹)")
    parser.add_argument("--show", action="store_true",
                       help="处理完成后显示结果")
    parser.add_argument("--canny", type=int, default=50,
                       help="Canny边缘检测阈值 (默认: 50)")
    parser.add_argument("--blur", type=int, default=5,
                       help="高斯模糊核大小 (默认: 5)")

    args = parser.parse_args()

    # 初始化扫描器
    scanner = DocumentScanner(
        canny_threshold1=args.canny,
        canny_threshold2=args.canny + 150,
        blur_kernel=args.blur
    )

    input_path = Path(args.input)
    output_path = Path(args.output)

    if args.batch:
        # 批量处理
        if not input_path.is_dir():
            print(f"错误: 批量模式需要输入文件夹路径")
            sys.exit(1)

        # 创建输出文件夹
        output_path.mkdir(parents=True, exist_ok=True)

        # 获取所有图片
        image_extensions = {'.png', '.jpg', '.jpeg', '.bmp', '.tif', '.tiff'}
        image_files = []
        for ext in image_extensions:
            image_files.extend(input_path.glob(f'*{ext}'))
            image_files.extend(input_path.glob(f'*{ext.upper()}'))

        if not image_files:
            print(f"错误: 文件夹中没有找到图片文件")
            sys.exit(1)

        print(f"找到 {len(image_files)} 张图片，开始处理...")
        print("-" * 50)

        success_count = 0
        for img_path in image_files:
            out_path = output_path / f"scanned_{img_path.name}"
            if process_single(scanner, str(img_path), str(out_path), args.mode):
                success_count += 1

        print("-" * 50)
        print(f"完成! 成功处理 {success_count}/{len(image_files)} 张图片")

    else:
        # 单张图片处理
        if not input_path.is_file():
            print(f"错误: 找不到文件 {input_path}")
            sys.exit(1)

        process_single(scanner, str(input_path), str(output_path), args.mode, args.show)


if __name__ == "__main__":
    main()
