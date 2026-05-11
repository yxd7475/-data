# -*- coding: utf-8 -*-
"""
文档扫描器 Web 应用
支持手机浏览器访问摄像头实时扫描
"""

from flask import Flask, render_template, request, jsonify, send_file
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

        print(f"base64字符串长度: {len(base64_str)}")
        print(f"base64前缀: {base64_str[:50] if len(base64_str) > 50 else base64_str}")

        # 移除 data:image/jpeg;base64, 前缀
        if ',' in base64_str:
            base64_str = base64_str.split(',')[1]

        # 移除可能的空白字符
        base64_str = base64_str.strip()

        # 解码
        img_data = base64.b64decode(base64_str)
        print(f"解码后数据长度: {len(img_data)} bytes")

        if len(img_data) == 0:
            print("错误: 解码后的图像数据为空")
            return None

        nparr = np.frombuffer(img_data, np.uint8)
        print(f"numpy数组大小: {len(nparr)}")

        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if image is None:
            print("错误: cv2.imdecode 返回 None")
        else:
            print(f"图像解码成功: {image.shape}")

        return image
    except Exception as e:
        print(f"base64_to_image 错误: {e}")
        import traceback
        traceback.print_exc()
        return None


def image_to_base64(image, format='png'):
    """将 OpenCV 图像转换为 Base64 字符串"""
    # 使用PNG保持最高质量
    _, buffer = cv2.imencode(f'.{format}', image)
    base64_str = base64.b64encode(buffer).decode('utf-8')
    return f'data:image/{format};base64,{base64_str}'


@app.route('/')
def index():
    """主页"""
    return render_template('index.html')


@app.route('/api/detect', methods=['POST'])
def detect_document():
    """检测文档边界"""
    print("===== 收到检测请求 =====")
    data = request.json
    image_base64 = data.get('image')
    scale = data.get('scale', 1.0)  # 客户端发送的缩放比例

    if not image_base64:
        print("错误: 没有图像数据")
        return jsonify({'error': 'No image provided'}), 400

    try:
        image = base64_to_image(image_base64)
        if image is None:
            print("检测API: 图像解码失败")
            return jsonify({'error': 'Invalid image'}), 400

        print(f"检测API: 图像尺寸 {image.shape}")

        # 检测边界
        corners = scanner.detect_document(image)

        if corners is not None:
            print(f"检测API: 检测到文档!")
            # 返回边界坐标
            return jsonify({
                'detected': True,
                'corners': corners.tolist()
            })
        else:
            print("检测API: 未检测到文档")
            return jsonify({
                'detected': False,
                'corners': None
            })

    except Exception as e:
        print(f"检测API错误: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/scan', methods=['POST'])
def scan_document():
    """扫描文档（检测边界 + 裁剪 + 增强滤镜）"""
    try:
        data = request.get_json(force=True)
        image_base64 = data.get('image')
        enhance_mode = data.get('mode', 'scanner')

        print(f"收到扫描请求, 图像数据长度: {len(image_base64) if image_base64 else 0}")

        if not image_base64:
            return jsonify({'error': 'No image provided'}), 400

        image = base64_to_image(image_base64)
        if image is None:
            return jsonify({'error': 'Failed to decode image'}), 400

        print(f"收到图像尺寸: {image.shape}")

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

            print("扫描完成 - 已检测边界并裁剪")

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

            print("扫描完成 - 未检测到边界")

            return jsonify({
                'success': True,
                'image': result_base64,
                'cropped': result_base64,  # 没有裁剪，使用原图
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
    print("===== 收到PDF导出请求 =====")
    data = request.json
    pages = data.get('pages', [])

    print(f"收到 {len(pages)} 页")

    if not pages:
        return jsonify({'error': 'No pages provided'}), 400

    try:
        from PIL import Image
        import img2pdf

        # 将所有页面转换为PIL Image
        images = []
        for i, page_base64 in enumerate(pages):
            print(f"处理第 {i+1} 页...")
            # 解码base64图片
            if ',' in page_base64:
                page_base64 = page_base64.split(',')[1]
            img_data = base64.b64decode(page_base64)
            img = Image.open(io.BytesIO(img_data))
            # 转换为RGB模式（PDF需要）
            if img.mode != 'RGB':
                img = img.convert('RGB')
            images.append(img)

        print(f"共处理 {len(images)} 张图片")

        # 将图片保存到临时文件，然后用img2pdf生成PDF
        temp_files = []

        for i, img in enumerate(images):
            temp_path = os.path.join(UPLOAD_FOLDER, f'temp_page_{i}.jpg')
            img.save(temp_path, 'JPEG', quality=95)
            temp_files.append(temp_path)

        print("生成PDF中...")

        # 生成PDF
        pdf_bytes_data = img2pdf.convert(temp_files)

        print(f"PDF生成成功，大小: {len(pdf_bytes_data)} bytes")

        # 清理临时文件
        for temp_file in temp_files:
            if os.path.exists(temp_file):
                os.remove(temp_file)

        print("返回PDF文件")

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
    # 获取本机 IP 地址
    import socket
    hostname = socket.gethostname()
    local_ip = socket.gethostbyname(hostname)

    print("=" * 50)
    print("文档扫描器 Web 应用 (HTTPS)")
    print("=" * 50)
    print(f"本机访问: https://localhost:5000")
    print(f"局域网访问: https://{local_ip}:5000")
    print("=" * 50)
    print("手机请在同一局域网下访问上述 HTTPS 地址")
    print("注意：首次访问可能需要点击'高级'->'继续访问'")
    print("=" * 50)

    # 启动 HTTPS 服务
    ssl_context = ('cert.pem', 'key.pem')
    app.run(host='0.0.0.0', port=5000, debug=True, ssl_context=ssl_context)
