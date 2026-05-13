# -*- coding: utf-8 -*-
"""
文档扫描器 Web 应用
支持手机浏览器访问摄像头实时扫描
生产环境版本 - 用于部署到 Render
"""

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import cv2
import numpy as np
import base64
import io
import os
import sys

# 添加 src 目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from scanner import DocumentScanner

app = Flask(__name__)
CORS(app)

scanner = DocumentScanner()

# 配置上传文件夹
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)


def base64_to_image(base64_str):
    """将 Base64 字符串转换为 OpenCV 图像"""
    try:
        if not base64_str:
            print("错误: base64字符串为空")
            return None

        # 移除 data:image/jpeg;base64, 前缀
        if ',' in base64_str:
            base64_str = base64_str.split(',')[1]

        # 移除可能的空白字符
        base64_str = base64_str.strip()

        # 解码
        img_data = base64.b64decode(base64_str)

        if len(img_data) == 0:
            print("错误: 解码后的图像数据为空")
            return None

        nparr = np.frombuffer(img_data, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if image is None:
            print("错误: cv2.imdecode 返回 None")

        return image
    except Exception as e:
        print(f"base64_to_image 错误: {e}")
        return None


def image_to_base64(image, format='png'):
    """将 OpenCV 图像转换为 Base64 字符串"""
    # 限制最大尺寸以提高传输速度
    h, w = image.shape[:2]
    max_size = 2000
    if max(h, w) > max_size:
        scale = max_size / max(h, w)
        image = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)

    # PNG 质量
    _, buffer = cv2.imencode(f'.{format}', image, [cv2.IMWRITE_PNG_COMPRESSION, 3])
    base64_str = base64.b64encode(buffer).decode('utf-8')
    return f'data:image/{format};base64,{base64_str}'


@app.route('/')
def index():
    """主页"""
    return jsonify({
        'name': '文档扫描器 API',
        'version': '1.0.0',
        'endpoints': [
            '/api/scan - 扫描文档',
            '/api/enhance - 增强文档',
            '/api/export-pdf - 导出PDF'
        ]
    })


@app.route('/api/detect', methods=['POST'])
def detect_document():
    """检测文档边界"""
    data = request.json
    image_base64 = data.get('image')

    if not image_base64:
        return jsonify({'error': 'No image provided'}), 400

    try:
        image = base64_to_image(image_base64)
        if image is None:
            return jsonify({'error': 'Invalid image'}), 400

        # 检测边界
        corners = scanner.detect_document(image)

        if corners is not None:
            return jsonify({
                'detected': True,
                'corners': corners.tolist()
            })
        else:
            return jsonify({
                'detected': False,
                'corners': None
            })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/scan', methods=['POST'])
def scan_document():
    """扫描文档（检测边界 + 裁剪 + 增强滤镜）"""
    try:
        data = request.get_json(force=True)
        image_base64 = data.get('image')
        enhance_mode = data.get('mode', 'scanner')

        if not image_base64:
            return jsonify({'error': 'No image provided'}), 400

        image = base64_to_image(image_base64)
        if image is None:
            return jsonify({'error': 'Failed to decode image'}), 400

        # 检测边界
        corners = scanner.detect_document(image)

        if corners is not None:
            # 裁剪
            cropped = scanner.four_point_transform(image, corners)
            # 应用滤镜
            enhanced = scanner.enhance_document(cropped, enhance_mode)

            # 返回裁剪后的原图和滤镜结果
            cropped_base64 = image_to_base64(cropped)
            result_base64 = image_to_base64(enhanced)

            return jsonify({
                'success': True,
                'image': result_base64,
                'cropped': cropped_base64,
                'detected': True
            })
        else:
            # 未检测到边界，只应用滤镜
            enhanced = scanner.enhance_document(image, enhance_mode)
            result_base64 = image_to_base64(enhanced)

            return jsonify({
                'success': True,
                'image': result_base64,
                'cropped': result_base64,
                'detected': False
            })

    except Exception as e:
        print(f"扫描错误: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/enhance', methods=['POST'])
def enhance_document():
    """只应用滤镜增强（不裁剪）"""
    data = request.json
    image_base64 = data.get('image')
    enhance_mode = data.get('mode', 'scanner')

    if not image_base64:
        return jsonify({'error': 'No image provided'}), 400

    try:
        image = base64_to_image(image_base64)
        if image is None:
            return jsonify({'error': 'Invalid image'}), 400

        # 应用增强
        enhanced = scanner.enhance_document(image, enhance_mode)
        result_base64 = image_to_base64(enhanced)

        return jsonify({
            'success': True,
            'image': result_base64
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/save', methods=['POST'])
def save_document():
    """保存扫描结果"""
    data = request.json
    image_base64 = data.get('image')
    filename = data.get('filename', 'scanned.png')

    if not image_base64:
        return jsonify({'error': 'No image provided'}), 400

    try:
        image = base64_to_image(image_base64)
        if image is None:
            return jsonify({'error': 'Invalid image'}), 400

        # 保存文件
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        cv2.imwrite(filepath, image)

        return jsonify({
            'success': True,
            'path': filepath
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/export-pdf', methods=['POST'])
def export_pdf():
    """导出PDF文件"""
    data = request.json
    pages = data.get('pages', [])

    if not pages:
        return jsonify({'error': 'No pages provided'}), 400

    try:
        from PIL import Image
        import img2pdf

        # 将所有页面转换为PIL Image
        images = []
        for i, page_base64 in enumerate(pages):
            # 解码base64图片
            if ',' in page_base64:
                page_base64 = page_base64.split(',')[1]
            img_data = base64.b64decode(page_base64)
            img = Image.open(io.BytesIO(img_data))
            # 转换为RGB模式（PDF需要）
            if img.mode != 'RGB':
                img = img.convert('RGB')
            images.append(img)

        # 将图片保存到临时文件，然后用img2pdf生成PDF
        temp_files = []

        for i, img in enumerate(images):
            temp_path = os.path.join(UPLOAD_FOLDER, f'temp_page_{i}.jpg')
            img.save(temp_path, 'JPEG', quality=95)
            temp_files.append(temp_path)

        # 生成PDF
        pdf_bytes_data = img2pdf.convert(temp_files)

        # 清理临时文件
        for temp_file in temp_files:
            if os.path.exists(temp_file):
                os.remove(temp_file)

        # 返回PDF文件
        return send_file(
            io.BytesIO(pdf_bytes_data),
            mimetype='application/pdf',
            as_attachment=True,
            download_name='scanned_document.pdf'
        )

    except Exception as e:
        print(f"PDF导出错误: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
