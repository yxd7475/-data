# 文档扫描器

类似扫描全能王的文档扫描程序，通过视觉算法自动检测文档边缘、矫正透视变形并裁剪。

## 功能特点

- ✅ 自动检测文档边界
- ✅ 四点透视变换矫正
- ✅ 多种增强模式（增强对比度、黑白文档、魔法色彩）
- ✅ 图形界面和命令行两种使用方式
- ✅ 批量处理支持
- ✅ PDF导出功能
- ✅ 手动角点选择（当自动检测失败时）

## 安装

```bash
pip install -r requirements.txt
```

## 使用方法

### 1. 图形界面

```bash
cd src
python gui.py
```

界面操作：
1. 点击"加载图片"选择要扫描的文档图片
2. 程序会自动检测文档边界
3. 选择增强模式查看效果
4. 点击"保存结果"导出

### 2. 命令行

单张图片：
```bash
python cli.py input.jpg -o output.jpg
```

批量处理：
```bash
python cli.py ./images -o ./output --batch
```

指定增强模式：
```bash
python cli.py input.jpg -o output.jpg -m bw      # 黑白文档
python cli.py input.jpg -o output.jpg -m magic   # 魔法色彩
```

### 3. 高级功能

手动选择角点：
```python
from advanced import ManualCornerSelector
import cv2

image = cv2.imread("document.jpg")
selector = ManualCornerSelector()
corners = selector.select_corners(image)
```

导出PDF：
```python
from advanced import PDFExporter

PDFExporter.export_images_to_pdf(
    ["scan1.jpg", "scan2.jpg"],
    "document.pdf"
)
```

## 算法原理

1. **图像预处理**：缩放、灰度化、高斯模糊
2. **边缘检测**：Canny算法检测图像边缘
3. **轮廓查找**：找到最大的四边形轮廓
4. **透视变换**：将倾斜的文档矫正为正视图
5. **图像增强**：CLAHE对比度增强、二值化等

## 增强模式说明

| 模式 | 效果 |
|------|------|
| original | 保持原图不变 |
| enhance | 增强对比度，适合普通文档 |
| bw | 黑白文档，适合文字识别 |
| magic_color | 魔法色彩，保持色彩增强对比度 |

## 目录结构

```
扫描/
├── src/
│   ├── scanner.py    # 核心扫描算法
│   ├── gui.py        # 图形界面
│   ├── cli.py        # 命令行工具
│   └── advanced.py   # 高级功能
├── images/           # 测试图片目录
├── output/           # 输出目录
├── requirements.txt  # 依赖列表
└── README.md         # 说明文档
```

## 参数调整

如果检测效果不理想，可以调整以下参数：

- **边缘检测灵敏度**：调整Canny阈值，值越小越敏感
- **模糊程度**：调整高斯模糊核大小，减少噪点影响

## 常见问题

**Q: 检测不到文档边界？**
A: 确保图片中文档与背景有明显对比，可以尝试调整参数或使用手动选择功能。

**Q: 矫正后图片变形？**
A: 确保四个角点按正确顺序选择：左上、右上、右下、左下。

**Q: 如何提高文字识别效果？**
A: 使用黑白模式(bw)可以增强文字对比度。
