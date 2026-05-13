# -*- coding: utf-8 -*-
"""
文档扫描器核心模块
实现类似扫描全能王的文档自动检测、矫正、裁剪功能
"""

import cv2
import numpy as np
from typing import Optional, Tuple, List
from dataclasses import dataclass


def cv_imread(file_path: str) -> Optional[np.ndarray]:
    """支持中文路径的图片读取"""
    try:
        img_array = np.fromfile(file_path, dtype=np.uint8)
        img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        return img
    except Exception:
        return None


def cv_imwrite(file_path: str, img: np.ndarray) -> bool:
    """支持中文路径的图片保存"""
    try:
        ext = file_path.rsplit('.', 1)[-1].lower()
        if ext == 'jpg':
            ext = 'jpeg'
        success, img_encoded = cv2.imencode(f'.{ext}', img)
        if success:
            img_encoded.tofile(file_path)
            return True
        return False
    except Exception:
        return False


@dataclass
class DocumentResult:
    """扫描结果数据类"""
    original: np.ndarray
    scanned: np.ndarray
    corners: np.ndarray
    confidence: float


class DocumentScanner:
    """
    文档扫描器 - 类似扫描全能王
    高精度自动检测纸张边界并矫正
    """

    def __init__(self):
        self._original_image = None
        self._ratio = 1.0
        self._canny_threshold1 = 50
        self._canny_threshold2 = 150
        self._blur_kernel = 5

    @property
    def canny_threshold1(self):
        return self._canny_threshold1

    @canny_threshold1.setter
    def canny_threshold1(self, value):
        self._canny_threshold1 = value

    @property
    def canny_threshold2(self):
        return self._canny_threshold2

    @canny_threshold2.setter
    def canny_threshold2(self, value):
        self._canny_threshold2 = value

    @property
    def blur_kernel(self):
        return self._blur_kernel

    @blur_kernel.setter
    def blur_kernel(self, value):
        self._blur_kernel = value

    def detect_document(self, image: np.ndarray) -> Optional[np.ndarray]:
        """
        智能文档检测 - 自适应多策略融合
        核心思路：分析图像特征，选择最适合的检测策略
        """
        h, w = image.shape[:2]
        img_area = h * w

        # 分析图像特征
        analysis = self._analyze_image(image)

        # 根据分析结果选择策略
        candidates = []

        # 策略1：高对比度场景 - 纸张与背景亮度差异大
        if analysis['high_contrast']:
            result = self._detect_high_contrast(image)
            if result is not None:
                score = self._smart_score(result, image, analysis)
                candidates.append((result, score))

        # 策略2：低对比度/复杂背景 - 使用边缘检测
        if analysis['complex_background']:
            result = self._detect_complex_background(image)
            if result is not None:
                score = self._smart_score(result, image, analysis)
                candidates.append((result, score))

        # 策略3：白色纸张场景
        if analysis['white_paper']:
            result = self._detect_white_paper(image)
            if result is not None:
                score = self._smart_score(result, image, analysis)
                candidates.append((result, score))

        # 策略4：边缘清晰场景
        if analysis['clear_edges']:
            result = self._detect_clear_edges(image)
            if result is not None:
                score = self._smart_score(result, image, analysis)
                candidates.append((result, score))

        # 策略5：通用检测（保底）
        result = self._detect_generic(image)
        if result is not None:
            score = self._smart_score(result, image, analysis)
            candidates.append((result, score))

        if not candidates:
            return None

        # 去重并选择最佳
        candidates = self._remove_duplicates(candidates)
        candidates.sort(key=lambda x: x[1], reverse=True)

        return candidates[0][0]

    def _analyze_image(self, image: np.ndarray) -> dict:
        """分析图像特征"""
        h, w = image.shape[:2]
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # 计算亮度分布
        mean_brightness = np.mean(gray)
        std_brightness = np.std(gray)

        # 计算边缘密度
        edges = cv2.Canny(gray, 50, 150)
        edge_density = np.sum(edges > 0) / (h * w)

        # 计算颜色分布
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        saturation = hsv[:, :, 1]
        mean_saturation = np.mean(saturation)

        # 计算亮度直方图
        hist = cv2.calcHist([gray], [0], None, [256], [0, 256]).flatten()
        hist = hist / hist.sum()

        # 分析是否有明显的双峰（纸张 vs 背景）
        # 使用Otsu方法获取阈值
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        white_ratio = np.sum(binary > 0) / (h * w)

        # 计算背景复杂度
        # 使用局部标准差来估计
        small_gray = cv2.resize(gray, (100, 100))
        kernel_size = 21
        local_mean = cv2.blur(small_gray, (kernel_size, kernel_size))
        local_var = cv2.blur((small_gray - local_mean)**2, (kernel_size, kernel_size))
        background_complexity = np.mean(np.sqrt(local_var))

        return {
            'mean_brightness': mean_brightness,
            'std_brightness': std_brightness,
            'edge_density': edge_density,
            'mean_saturation': mean_saturation,
            'white_ratio': white_ratio,
            'background_complexity': background_complexity,
            'high_contrast': std_brightness > 50,
            'complex_background': background_complexity > 30,
            'white_paper': white_ratio > 0.3 and mean_saturation < 50,
            'clear_edges': edge_density > 0.05 and edge_density < 0.3
        }

    def _smart_score(self, corners: np.ndarray, image: np.ndarray, analysis: dict) -> float:
        """智能评分 - 根据图像特征调整权重"""
        h, w = image.shape[:2]

        # 基础评分
        area = cv2.contourArea(corners)
        area_ratio = area / (h * w)

        # 面积评分
        if area_ratio < 0.05:
            area_score = 0
        elif 0.2 <= area_ratio <= 0.8:
            area_score = 1.0
        else:
            area_score = max(0, 1 - abs(area_ratio - 0.5) * 2)

        # 形状评分
        sides = []
        for i in range(4):
            p1 = corners[i]
            p2 = corners[(i + 1) % 4]
            sides.append(np.linalg.norm(p2 - p1))
        sides = np.array(sides)
        side_ratio = min(sides.min() / sides.max(), 1.0) if sides.max() > 0 else 0

        # 角度评分
        angles = []
        for i in range(4):
            p1 = corners[i]
            p2 = corners[(i + 1) % 4]
            p3 = corners[(i + 2) % 4]
            v1 = p1 - p2
            v2 = p3 - p2
            cos_angle = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-6)
            angle = np.abs(np.degrees(np.arccos(np.clip(cos_angle, -1, 1))))
            angles.append(np.abs(angle - 90))
        angle_score = 1 - min(np.mean(angles) / 45, 1)

        # 位置评分 - 纸张应该在图像中心区域
        center = np.mean(corners, axis=0)
        center_dist = np.sqrt((center[0] - w/2)**2 + (center[1] - h/2)**2)
        max_dist = np.sqrt((w/2)**2 + (h/2)**2)
        position_score = 1 - min(center_dist / max_dist, 1)

        # 纸张内容评分 - 检测区域内的纸张特征
        content_score = self._score_paper_content(corners, image, analysis)

        # 综合评分
        total = (area_score * 0.2 +
                 side_ratio * 0.15 +
                 angle_score * 0.15 +
                 position_score * 0.2 +
                 content_score * 0.3)

        return total

    def _score_paper_content(self, corners: np.ndarray, image: np.ndarray, analysis: dict) -> float:
        """评分纸张内容特征"""
        h, w = image.shape[:2]

        # 创建mask
        mask = np.zeros((h, w), dtype=np.uint8)
        cv2.fillPoly(mask, [corners.astype(np.int32)], 255)

        # 提取区域
        region = cv2.bitwise_and(image, image, mask=mask)

        # 计算区域内的特征
        region_pixels = region[mask > 0]
        if len(region_pixels) == 0:
            return 0

        # 亮度均匀性
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        region_gray = gray[mask > 0]
        brightness_std = np.std(region_gray)
        uniformity = 1 / (1 + brightness_std / 50)

        # 平均亮度（纸张通常较亮）
        mean_brightness = np.mean(region_gray)
        brightness_score = min(mean_brightness / 200, 1.0)

        # 饱和度（纸张通常低饱和度）
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        region_sat = hsv[:, :, 1][mask > 0]
        mean_sat = np.mean(region_sat)
        saturation_score = 1 - min(mean_sat / 100, 1.0)

        return uniformity * 0.4 + brightness_score * 0.3 + saturation_score * 0.3

    def _detect_high_contrast(self, image: np.ndarray) -> Optional[np.ndarray]:
        """高对比度场景检测"""
        h, w = image.shape[:2]
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # 多种阈值尝试
        for thresh_method in ['otsu', 'adaptive', 'mean']:
            if thresh_method == 'otsu':
                _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            elif thresh_method == 'adaptive':
                binary = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                               cv2.THRESH_BINARY, 31, 10)
            else:
                mean_val = np.mean(gray)
                _, binary = cv2.threshold(gray, mean_val, 255, cv2.THRESH_BINARY)

            # 形态学操作
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (21, 21))
            cleaned = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
            cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_OPEN, kernel)

            result = self._find_quad_in_mask(cleaned, h, w)
            if result is not None:
                return result

        return None

    def _detect_complex_background(self, image: np.ndarray) -> Optional[np.ndarray]:
        """复杂背景检测"""
        h, w = image.shape[:2]

        # 使用GrabCut
        result = self._grabcut_detect(image)
        if result is not None:
            return result

        # 使用边缘检测
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # 多尺度边缘检测
        for sigma in [0.5, 1.0, 1.5, 2.0]:
            blurred = cv2.GaussianBlur(gray, (0, 0), sigma)
            edges = cv2.Canny(blurred, 30, 100)

            # 膨胀和闭运算
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
            dilated = cv2.dilate(edges, kernel, iterations=3)
            closed = cv2.morphologyEx(dilated, cv2.MORPH_CLOSE, kernel)

            # 反转
            closed = cv2.bitwise_not(closed)

            result = self._find_quad_in_mask(closed, h, w)
            if result is not None:
                return result

        return None

    def _detect_white_paper(self, image: np.ndarray) -> Optional[np.ndarray]:
        """检测白色纸张"""
        h, w = image.shape[:2]

        # HSV颜色空间检测白色
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

        # 白色的HSV范围：高V，低S
        for s_max in [40, 60, 80, 100]:
            for v_min in [150, 180, 200, 220]:
                lower = np.array([0, 0, v_min])
                upper = np.array([180, s_max, 255])
                mask = cv2.inRange(hsv, lower, upper)

                # 形态学操作
                kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (21, 21))
                cleaned = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
                cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_OPEN, kernel)

                result = self._find_quad_in_mask(cleaned, h, w)
                if result is not None:
                    return result

        # LAB空间检测
        lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
        l = lab[:, :, 0]

        for l_min in [160, 180, 200, 220]:
            _, binary = cv2.threshold(l, l_min, 255, cv2.THRESH_BINARY)

            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (21, 21))
            cleaned = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
            cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_OPEN, kernel)

            result = self._find_quad_in_mask(cleaned, h, w)
            if result is not None:
                return result

        return None

    def _detect_clear_edges(self, image: np.ndarray) -> Optional[np.ndarray]:
        """边缘清晰的场景检测"""
        h, w = image.shape[:2]
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # 使用霍夫直线检测
        for canny_low in [20, 40, 60, 80, 100]:
            edges = cv2.Canny(gray, canny_low, canny_low * 3)

            lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=80,
                                    minLineLength=min(h, w) // 4, maxLineGap=30)

            if lines is not None and len(lines) >= 4:
                result = self._lines_to_quad(lines, h, w)
                if result is not None and self._is_valid_quad(result, h, w):
                    return result

        return None

    def _detect_generic(self, image: np.ndarray) -> Optional[np.ndarray]:
        """通用检测方法"""
        h, w = image.shape[:2]

        # 尝试多种预处理
        methods = []

        # 灰度阈值
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        methods.append(('gray', gray))

        # 亮度通道
        lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
        methods.append(('l_channel', lab[:, :, 0]))

        # 饱和度反相
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        inv_sat = 255 - hsv[:, :, 1]
        methods.append(('inv_sat', inv_sat))

        for name, channel in methods:
            # 高斯模糊
            blurred = cv2.GaussianBlur(channel, (11, 11), 0)

            # 多种阈值
            for thresh_type in ['otsu', 'adaptive']:
                if thresh_type == 'otsu':
                    _, binary = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                else:
                    binary = cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                                   cv2.THRESH_BINARY, 31, 10)

                # 形态学
                kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (21, 21))
                cleaned = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
                cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_OPEN, kernel)

                result = self._find_quad_in_mask(cleaned, h, w)
                if result is not None:
                    return result

        return None

    def _find_quad_in_mask(self, mask: np.ndarray, h: int, w: int) -> Optional[np.ndarray]:
        """在mask中寻找四边形"""
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if not contours:
            return None

        contours = sorted(contours, key=cv2.contourArea, reverse=True)

        for contour in contours[:10]:
            area = cv2.contourArea(contour)
            if area < h * w * 0.02:
                continue

            hull = cv2.convexHull(contour)
            peri = cv2.arcLength(hull, True)

            # 尝试多种逼近精度
            for eps in [0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.08]:
                approx = cv2.approxPolyDP(hull, eps * peri, True)
                if len(approx) == 4:
                    corners = approx.reshape(4, 2).astype(np.float32)
                    if self._is_valid_quad(corners, h, w):
                        return corners

            # 最小外接矩形
            rect = cv2.minAreaRect(hull)
            box = cv2.boxPoints(rect)
            corners = box.astype(np.float32)
            if self._is_valid_quad(corners, h, w):
                return corners

        return None

    def _grabcut_detect(self, image: np.ndarray) -> Optional[np.ndarray]:
        """GrabCut检测"""
        h, w = image.shape[:2]

        # 缩小加速
        scale = 1.0
        if max(h, w) > 400:
            scale = 400 / max(h, w)
            small = cv2.resize(image, None, fx=scale, fy=scale)
        else:
            small = image

        sh, sw = small.shape[:2]

        try:
            # 使用矩形初始化
            margin = min(sh, sw) // 8
            rect = (margin, margin, sw - 2*margin, sh - 2*margin)

            mask = np.zeros((sh, sw), np.uint8)
            bgd_model = np.zeros((1, 65), np.float64)
            fgd_model = np.zeros((1, 65), np.float64)

            cv2.grabCut(small, mask, rect, bgd_model, fgd_model, 5, cv2.GC_INIT_WITH_RECT)

            # 提取前景
            fg_mask = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 255, 0).astype(np.uint8)

            # 形态学
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
            fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_CLOSE, kernel)
            fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, kernel)

            result = self._find_quad_in_mask(fg_mask, sh, sw)
            if result is not None:
                return result / scale

        except Exception:
            pass

        return None

    def _lines_to_quad(self, lines: np.ndarray, h: int, w: int) -> Optional[np.ndarray]:
        """从直线构建四边形"""
        horizontal = []
        vertical = []

        for line in lines:
            x1, y1, x2, y2 = line[0]
            angle = np.abs(np.arctan2(y2 - y1, x2 - x1) * 180 / np.pi)
            length = np.sqrt((x2 - x1)**2 + (y2 - y1)**2)

            if angle < 15 or angle > 165:
                horizontal.append((y1, y2, x1, x2, length))
            elif 75 < angle < 105:
                vertical.append((x1, x2, y1, y2, length))

        if len(horizontal) < 2 or len(vertical) < 2:
            return None

        # 聚类
        horizontal.sort(key=lambda x: (x[0] + x[1]) / 2)
        h_clusters = []
        for line in horizontal:
            y = (line[0] + line[1]) / 2
            if not h_clusters or abs((h_clusters[-1][0] + h_clusters[-1][1]) / 2 - y) > 40:
                h_clusters.append(line)
            else:
                last = h_clusters[-1]
                h_clusters[-1] = ((last[0] + line[0]) / 2, (last[1] + line[1]) / 2,
                                  min(last[2], line[2]), max(last[3], line[3]), max(last[4], line[4]))

        vertical.sort(key=lambda x: (x[0] + x[1]) / 2)
        v_clusters = []
        for line in vertical:
            x = (line[0] + line[1]) / 2
            if not v_clusters or abs((v_clusters[-1][0] + v_clusters[-1][1]) / 2 - x) > 40:
                v_clusters.append(line)
            else:
                last = v_clusters[-1]
                v_clusters[-1] = ((last[0] + line[0]) / 2, (last[1] + line[1]) / 2,
                                  min(last[2], line[2]), max(last[3], line[3]), max(last[4], line[4]))

        if len(h_clusters) < 2 or len(v_clusters) < 2:
            return None

        h_clusters.sort(key=lambda x: -x[4])
        v_clusters.sort(key=lambda x: -x[4])

        best = None
        best_score = 0

        for i in range(min(4, len(h_clusters))):
            for j in range(i+1, min(5, len(h_clusters))):
                for k in range(min(4, len(v_clusters))):
                    for l in range(k+1, min(5, len(v_clusters))):
                        top = h_clusters[i]
                        bottom = h_clusters[j]
                        left = v_clusters[k]
                        right = v_clusters[l]

                        if (top[0] + top[1]) / 2 > (bottom[0] + bottom[1]) / 2:
                            top, bottom = bottom, top
                        if (left[0] + left[1]) / 2 > (right[0] + right[1]) / 2:
                            left, right = right, left

                        top_y = (top[0] + top[1]) / 2
                        bottom_y = (bottom[0] + bottom[1]) / 2
                        left_x = (left[0] + left[1]) / 2
                        right_x = (right[0] + right[1]) / 2

                        corners = np.array([
                            [left_x, top_y], [right_x, top_y],
                            [right_x, bottom_y], [left_x, bottom_y]
                        ], dtype=np.float32)

                        if self._is_valid_quad(corners, h, w):
                            score = (top[4] + bottom[4] + left[4] + right[4]) / (w + h)
                            if score > best_score:
                                best_score = score
                                best = corners

        return best

    def _remove_duplicates(self, candidates: list) -> list:
        """去除重复的候选"""
        if len(candidates) <= 1:
            return candidates

        unique = []
        for corners, score in candidates:
            is_duplicate = False
            for existing_corners, _ in unique:
                # 检查中心点距离
                c1 = np.mean(corners, axis=0)
                c2 = np.mean(existing_corners, axis=0)
                dist = np.linalg.norm(c1 - c2)

                # 检查面积差异
                a1 = cv2.contourArea(corners)
                a2 = cv2.contourArea(existing_corners)

                if dist < 30 and abs(a1 - a2) / max(a1, a2) < 0.2:
                    is_duplicate = True
                    break

            if not is_duplicate:
                unique.append((corners, score))

        return unique

    def _detect_by_contour(self, image: np.ndarray, scale_factor: float = 1.0) -> Optional[np.ndarray]:
        """基于轮廓检测"""
        h, w = image.shape[:2]

        # 缩小加速
        if scale_factor < 1.0:
            small = cv2.resize(image, None, fx=scale_factor, fy=scale_factor)
        else:
            small = image

        sh, sw = small.shape[:2]
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)

        # 高斯模糊
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)

        # 自适应阈值
        binary = cv2.adaptiveThreshold(
            blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 21, 10
        )

        # 形态学操作
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
        cleaned = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
        cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_OPEN, kernel)

        # 反转
        cleaned = cv2.bitwise_not(cleaned)

        # 找轮廓
        contours, _ = cv2.findContours(cleaned, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if not contours:
            return None

        # 按面积排序
        contours = sorted(contours, key=cv2.contourArea, reverse=True)

        for contour in contours[:15]:
            area = cv2.contourArea(contour)
            if area < sh * sw * 0.03:  # 降低最小面积阈值
                continue

            # 凸包
            hull = cv2.convexHull(contour)
            peri = cv2.arcLength(hull, True)

            # 尝试多边形逼近
            for eps in [0.02, 0.03, 0.04, 0.05, 0.06]:
                approx = cv2.approxPolyDP(hull, eps * peri, True)
                if len(approx) == 4:
                    corners = approx.reshape(4, 2).astype(np.float32) / scale_factor
                    if self._is_valid_quad(corners, h, w):
                        return corners

            # 如果不是四边形，用最小外接矩形
            rect = cv2.minAreaRect(hull)
            box = cv2.boxPoints(rect)
            corners = box.astype(np.float32) / scale_factor
            if self._is_valid_quad(corners, h, w):
                return corners

        return None

    def _detect_by_threshold(self, image: np.ndarray, thresh_type: str = 'otsu') -> Optional[np.ndarray]:
        """基于亮度阈值检测"""
        h, w = image.shape[:2]

        # 缩小加速
        scale = 1.0
        if max(h, w) > 600:
            scale = 600 / max(h, w)
            small = cv2.resize(image, None, fx=scale, fy=scale)
        else:
            small = image

        sh, sw = small.shape[:2]
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)

        # 高斯模糊
        blurred = cv2.GaussianBlur(gray, (11, 11), 0)

        if thresh_type == 'otsu':
            _, binary = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        elif thresh_type == 'adaptive':
            binary = cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                           cv2.THRESH_BINARY, 31, 15)
        else:  # color - 基于颜色检测白色区域
            hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
            # 检测高亮度、低饱和度的白色区域
            lower_white = np.array([0, 0, 180])
            upper_white = np.array([180, 60, 255])
            binary = cv2.inRange(hsv, lower_white, upper_white)

        # 形态学操作
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (21, 21))
        cleaned = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
        cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_OPEN, kernel)

        # 找轮廓
        contours, _ = cv2.findContours(cleaned, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if not contours:
            return None

        contours = sorted(contours, key=cv2.contourArea, reverse=True)

        for contour in contours[:10]:
            area = cv2.contourArea(contour)
            if area < sh * sw * 0.03:  # 降低最小面积
                continue

            hull = cv2.convexHull(contour)
            peri = cv2.arcLength(hull, True)

            for eps in [0.02, 0.03, 0.04, 0.05, 0.06]:
                approx = cv2.approxPolyDP(hull, eps * peri, True)
                if len(approx) == 4:
                    corners = approx.reshape(4, 2).astype(np.float32) / scale
                    if self._is_valid_quad(corners, h, w):
                        return corners

            rect = cv2.minAreaRect(hull)
            box = cv2.boxPoints(rect)
            corners = box.astype(np.float32) / scale
            if self._is_valid_quad(corners, h, w):
                return corners

        return None

    def _detect_by_canny(self, image: np.ndarray, canny_low: int = 50) -> Optional[np.ndarray]:
        """基于Canny边缘检测"""
        h, w = image.shape[:2]

        # 缩小加速
        scale = 1.0
        if max(h, w) > 600:
            scale = 600 / max(h, w)
            small = cv2.resize(image, None, fx=scale, fy=scale)
        else:
            small = image

        sh, sw = small.shape[:2]
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)

        # 高斯模糊
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)

        # Canny边缘检测
        edges = cv2.Canny(blurred, canny_low, canny_low * 3)

        # 膨胀连接
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (9, 9))
        dilated = cv2.dilate(edges, kernel, iterations=2)
        closed = cv2.morphologyEx(dilated, cv2.MORPH_CLOSE, kernel)

        # 找轮廓
        contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if not contours:
            return None

        contours = sorted(contours, key=cv2.contourArea, reverse=True)

        for contour in contours[:15]:
            area = cv2.contourArea(contour)
            if area < sh * sw * 0.03:
                continue

            hull = cv2.convexHull(contour)
            peri = cv2.arcLength(hull, True)

            for eps in [0.02, 0.03, 0.04, 0.05, 0.06]:
                approx = cv2.approxPolyDP(hull, eps * peri, True)
                if len(approx) == 4:
                    corners = approx.reshape(4, 2).astype(np.float32) / scale
                    if self._is_valid_quad(corners, h, w):
                        return corners

            rect = cv2.minAreaRect(hull)
            box = cv2.boxPoints(rect)
            corners = box.astype(np.float32) / scale
            if self._is_valid_quad(corners, h, w):
                return corners

        return None

    def _detect_by_color(self, image: np.ndarray) -> Optional[np.ndarray]:
        """基于颜色分割检测纸张"""
        h, w = image.shape[:2]

        # 缩小加速
        scale = 1.0
        if max(h, w) > 600:
            scale = 600 / max(h, w)
            small = cv2.resize(image, None, fx=scale, fy=scale)
        else:
            small = image

        sh, sw = small.shape[:2]

        # 转换到LAB空间
        lab = cv2.cvtColor(small, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)

        # 纸张通常是高亮度
        _, l_binary = cv2.threshold(l, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # 形态学操作
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (21, 21))
        cleaned = cv2.morphologyEx(l_binary, cv2.MORPH_CLOSE, kernel)
        cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_OPEN, kernel)

        # 找轮廓
        contours, _ = cv2.findContours(cleaned, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if not contours:
            return None

        contours = sorted(contours, key=cv2.contourArea, reverse=True)

        for contour in contours[:10]:
            area = cv2.contourArea(contour)
            if area < sh * sw * 0.03:
                continue

            hull = cv2.convexHull(contour)
            peri = cv2.arcLength(hull, True)

            for eps in [0.02, 0.03, 0.04, 0.05, 0.06]:
                approx = cv2.approxPolyDP(hull, eps * peri, True)
                if len(approx) == 4:
                    corners = approx.reshape(4, 2).astype(np.float32) / scale
                    if self._is_valid_quad(corners, h, w):
                        return corners

            rect = cv2.minAreaRect(hull)
            box = cv2.boxPoints(rect)
            corners = box.astype(np.float32) / scale
            if self._is_valid_quad(corners, h, w):
                return corners

        return None

    def _detect_by_hough_lines(self, image: np.ndarray) -> Optional[np.ndarray]:
        """基于霍夫直线检测"""
        h, w = image.shape[:2]
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # 边缘检测
        edges = cv2.Canny(gray, 50, 150)

        # 霍夫直线
        lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=80,
                                minLineLength=min(h, w) // 4, maxLineGap=30)

        if lines is None or len(lines) < 4:
            return None

        # 分类直线
        horizontal = []
        vertical = []

        for line in lines:
            x1, y1, x2, y2 = line[0]
            angle = np.abs(np.arctan2(y2 - y1, x2 - x1) * 180 / np.pi)
            length = np.sqrt((x2 - x1)**2 + (y2 - y1)**2)

            if angle < 15 or angle > 165:  # 水平
                horizontal.append((y1, y2, x1, x2, length))
            elif 75 < angle < 105:  # 垂直
                vertical.append((x1, x2, y1, y2, length))

        if len(horizontal) < 2 or len(vertical) < 2:
            return None

        # 聚类水平线
        horizontal.sort(key=lambda x: (x[0] + x[1]) / 2)
        h_clusters = []
        for line in horizontal:
            y = (line[0] + line[1]) / 2
            if not h_clusters or abs((h_clusters[-1][0] + h_clusters[-1][1]) / 2 - y) > 40:
                h_clusters.append(line)
            else:
                last = h_clusters[-1]
                h_clusters[-1] = (
                    (last[0] + line[0]) / 2,
                    (last[1] + line[1]) / 2,
                    min(last[2], line[2]),
                    max(last[3], line[3]),
                    max(last[4], line[4])
                )

        # 聚类垂直线
        vertical.sort(key=lambda x: (x[0] + x[1]) / 2)
        v_clusters = []
        for line in vertical:
            x = (line[0] + line[1]) / 2
            if not v_clusters or abs((v_clusters[-1][0] + v_clusters[-1][1]) / 2 - x) > 40:
                v_clusters.append(line)
            else:
                last = v_clusters[-1]
                v_clusters[-1] = (
                    (last[0] + line[0]) / 2,
                    (last[1] + line[1]) / 2,
                    min(last[2], line[2]),
                    max(last[3], line[3]),
                    max(last[4], line[4])
                )

        if len(h_clusters) < 2 or len(v_clusters) < 2:
            return None

        # 按长度排序取最长的
        h_clusters.sort(key=lambda x: -x[4])
        v_clusters.sort(key=lambda x: -x[4])

        best_rect = None
        best_score = 0

        # 尝试多条线的组合
        for i, top_line in enumerate(h_clusters[:4]):
            for j, bottom_line in enumerate(h_clusters[:4]):
                if i >= j:
                    continue
                for k, left_line in enumerate(v_clusters[:4]):
                    for l, right_line in enumerate(v_clusters[:4]):
                        if k >= l:
                            continue

                        # 确保上下、左右顺序正确
                        if (top_line[0] + top_line[1]) / 2 > (bottom_line[0] + bottom_line[1]) / 2:
                            top_line, bottom_line = bottom_line, top_line
                        if (left_line[0] + left_line[1]) / 2 > (right_line[0] + right_line[1]) / 2:
                            left_line, right_line = right_line, left_line

                        # 计算四个角点
                        top_y = (top_line[0] + top_line[1]) / 2
                        bottom_y = (bottom_line[0] + bottom_line[1]) / 2
                        left_x = (left_line[0] + left_line[1]) / 2
                        right_x = (right_line[0] + right_line[1]) / 2

                        corners = np.array([
                            [left_x, top_y],
                            [right_x, top_y],
                            [right_x, bottom_y],
                            [left_x, bottom_y]
                        ], dtype=np.float32)

                        if self._is_valid_quad(corners, h, w):
                            score = self._score_quad(corners, image, h, w)
                            if score > best_score:
                                best_score = score
                                best_rect = corners

        return best_rect

    def _score_quad(self, corners: np.ndarray, image: np.ndarray, h: int, w: int) -> float:
        """评估四边形得分"""
        # 1. 面积得分
        area = cv2.contourArea(corners)
        area_ratio = area / (h * w)
        if area_ratio < 0.05 or area_ratio > 0.98:  # 放宽范围
            area_score = 0
        elif 0.2 <= area_ratio <= 0.9:
            area_score = 1.0
        else:
            area_score = 0.5

        # 2. 形状规则性得分
        sides = []
        for i in range(4):
            p1 = corners[i]
            p2 = corners[(i + 1) % 4]
            sides.append(np.linalg.norm(p2 - p1))

        sides = np.array(sides)

        # 边长比例
        side_ratio = min(sides.min() / sides.max(), 1.0)

        # 角度
        angles = []
        for i in range(4):
            p1 = corners[i]
            p2 = corners[(i + 1) % 4]
            p3 = corners[(i + 2) % 4]
            v1 = p1 - p2
            v2 = p3 - p2
            cos_angle = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-6)
            angle = np.abs(np.degrees(np.arccos(np.clip(cos_angle, -1, 1))))
            angles.append(np.abs(angle - 90))

        angle_score = 1 - min(np.mean(angles) / 45, 1)

        # 3. 凸性得分
        convex_score = 1.0 if cv2.isContourConvex(corners.astype(np.int32)) else 0.5

        # 综合得分
        total_score = area_score * 0.4 + side_ratio * 0.3 + angle_score * 0.2 + convex_score * 0.1

        return total_score

    def _detect_with_region_split(self, image: np.ndarray) -> Optional[np.ndarray]:
        """
        检测水平分界线，将图片分割成多个区域后分别检测
        仅用于处理多个独立物体（如纸张和衣服上下排列）的情况
        """
        h, w = image.shape[:2]

        # 先尝试整体检测，如果成功则不需要分割
        whole_result = self._detect_by_brightness_full(image)
        if whole_result is not None:
            area_ratio = cv2.contourArea(whole_result) / (h * w)
            if area_ratio > 0.2:  # 找到了较大的完整区域
                return whole_result

        # 整体检测失败，尝试分割检测
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # 检测边缘 - 使用可配置参数
        edges = cv2.Canny(gray, self._canny_threshold1, self._canny_threshold2)

        # 霍夫直线检测
        lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=80,
                                minLineLength=min(h, w) // 4, maxLineGap=30)

        if lines is None:
            return None

        # 找出显著的水平分界线（排除图片顶部和底部边缘）
        h_dividers = []

        for line in lines:
            x1, y1, x2, y2 = line[0]
            length = np.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
            angle = np.abs(np.arctan2(y2 - y1, x2 - x1) * 180 / np.pi)

            if angle < 15 or angle > 165:  # 水平线
                y_pos = (y1 + y2) / 2
                x_min, x_max = min(x1, x2), max(x1, x2)
                # 只选择在图片中间区域的分割线（排除顶部和底部）
                if h * 0.3 < y_pos < h * 0.7 and length > w * 0.4:
                    h_dividers.append((y_pos, x_min, x_max, length))

        if not h_dividers:
            return None

        # 聚类水平分割线
        h_dividers.sort(key=lambda x: x[0])
        clustered_h = []
        for y, x_min, x_max, length in h_dividers:
            if not clustered_h:
                clustered_h.append([y, x_min, x_max])
            elif abs(clustered_h[-1][0] - y) > 50:
                clustered_h.append([y, x_min, x_max])
            else:
                clustered_h[-1][0] = (clustered_h[-1][0] + y) / 2
                clustered_h[-1][1] = min(clustered_h[-1][1], x_min)
                clustered_h[-1][2] = max(clustered_h[-1][2], x_max)

        if not clustered_h:
            return None

        # 使用分割线检测
        best_divider = clustered_h[0]
        divider_y = best_divider[0]

        candidates = []

        # 上半部分
        result_top = self._detect_in_region(image, 0, w, 0, int(divider_y))
        if result_top is not None:
            score = self._evaluate_candidate(result_top, image, 1.0)
            area_ratio = cv2.contourArea(result_top) / (h * w)
            if area_ratio > 0.1:  # 确保面积足够大
                candidates.append((result_top, score))

        # 下半部分
        result_bottom = self._detect_in_region(image, 0, w, int(divider_y), h)
        if result_bottom is not None:
            score = self._evaluate_candidate(result_bottom, image, 1.0)
            area_ratio = cv2.contourArea(result_bottom) / (h * w)
            if area_ratio > 0.1:
                candidates.append((result_bottom, score))

        if not candidates:
            return None

        # 选择面积最大的候选（更可能是完整文档）
        candidates.sort(key=lambda x: cv2.contourArea(x[0]), reverse=True)
        return candidates[0][0]

    def _detect_by_brightness_full(self, image: np.ndarray) -> Optional[np.ndarray]:
        """基于亮度检测完整的白色区域（不分割）"""
        h, w = image.shape[:2]

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        blur_size = self._blur_kernel * 2 + 1  # 确保是奇数
        blurred = cv2.GaussianBlur(gray, (blur_size, blur_size), 0)
        _, binary = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
        cleaned = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
        cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_OPEN, kernel)

        contours, _ = cv2.findContours(cleaned, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if not contours:
            return None

        contours = sorted(contours, key=cv2.contourArea, reverse=True)

        for contour in contours[:5]:
            area = cv2.contourArea(contour)
            if area < h * w * 0.1:
                continue

            hull = cv2.convexHull(contour)
            peri = cv2.arcLength(hull, True)
            found_quad = None

            for eps in [0.02, 0.03, 0.04, 0.05]:
                approx = cv2.approxPolyDP(hull, eps * peri, True)
                if len(approx) == 4:
                    corners = approx.reshape(4, 2).astype(np.float32)
                    if self._is_valid_quad(corners, h, w):
                        found_quad = corners
                        break

            if found_quad is None:
                rect = cv2.minAreaRect(hull)
                box = cv2.boxPoints(rect)
                corners = box.astype(np.float32)
                if self._is_valid_quad(corners, h, w):
                    found_quad = corners

            if found_quad is not None:
                return found_quad

        return None

    def _detect_in_region(self, image: np.ndarray, x1: float, x2: float, y1: float, y2: float) -> Optional[np.ndarray]:
        """
        在指定区域内检测文档
        """
        h, w = image.shape[:2]

        # 确保坐标是整数
        x1, x2, y1, y2 = int(x1), int(x2), int(y1), int(y2)

        # 裁剪区域
        region = image[y1:y2, x1:x2]
        if region.size == 0:
            return None

        rh, rw = region.shape[:2]

        # 在区域内检测
        gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
        blur_size = self._blur_kernel * 2 + 1  # 确保是奇数
        blurred = cv2.GaussianBlur(gray, (blur_size, blur_size), 0)
        _, binary = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
        cleaned = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
        cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_OPEN, kernel)

        contours, _ = cv2.findContours(cleaned, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if not contours:
            return None

        contours = sorted(contours, key=cv2.contourArea, reverse=True)

        best_quad = None
        best_area = 0

        for contour in contours[:5]:
            area = cv2.contourArea(contour)
            if area < rh * rw * 0.1:  # 太小
                continue

            # 检查是否覆盖了整个区域
            x, y, bw, bh = cv2.boundingRect(contour)
            coverage = area / (rh * rw)

            if coverage > 0.8:  # 覆盖了大部分区域，直接使用区域边界
                # 收缩边界以排除边缘异物
                margin = 10
                corners = np.array([
                    [x1 + margin, y1 + margin],
                    [x2 - margin, y1 + margin],
                    [x2 - margin, y2 - margin],
                    [x1 + margin, y2 - margin]
                ], dtype=np.float32)

                if self._is_valid_quad(corners, h, w):
                    return corners

            hull = cv2.convexHull(contour)
            peri = cv2.arcLength(hull, True)

            found_quad = None
            for eps in [0.02, 0.03, 0.04, 0.05]:
                approx = cv2.approxPolyDP(hull, eps * peri, True)
                if len(approx) == 4:
                    corners = approx.reshape(4, 2).astype(np.float32)
                    found_quad = corners
                    break

            if found_quad is None:
                rect = cv2.minAreaRect(hull)
                box = cv2.boxPoints(rect)
                found_quad = box.astype(np.float32)

            # 转换回原图坐标
            found_quad[:, 0] += x1
            found_quad[:, 1] += y1

            if self._is_valid_quad(found_quad, h, w) and area > best_area:
                best_quad = found_quad
                best_area = area

        return best_quad

    def _detect_by_brightness(self, image: np.ndarray) -> Optional[np.ndarray]:
        """基于亮度检测白色区域"""
        h, w = image.shape[:2]

        # 缩小图片加速处理
        max_size = 600
        if max(h, w) > max_size:
            scale = max_size / max(h, w)
            small = cv2.resize(image, None, fx=scale, fy=scale)
        else:
            small = image
            scale = 1.0

        sh, sw = small.shape[:2]
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        blur_size = self._blur_kernel * 2 + 1  # 确保是奇数
        blurred = cv2.GaussianBlur(gray, (blur_size, blur_size), 0)
        _, binary = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (11, 11))
        cleaned = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
        cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_OPEN, kernel)

        contours, _ = cv2.findContours(cleaned, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        candidates = []
        if contours:
            contours = sorted(contours, key=cv2.contourArea, reverse=True)
            for contour in contours[:10]:
                area = cv2.contourArea(contour)
                if area < sh * sw * 0.05:
                    continue

                hull = cv2.convexHull(contour)
                peri = cv2.arcLength(hull, True)
                found_quad = None

                for eps in [0.02, 0.03, 0.04, 0.05]:
                    approx = cv2.approxPolyDP(hull, eps * peri, True)
                    if len(approx) == 4:
                        corners = approx.reshape(4, 2).astype(np.float32) / scale
                        if self._is_valid_quad(corners, h, w):
                            found_quad = corners
                            break

                if found_quad is None:
                    rect = cv2.minAreaRect(hull)
                    box = cv2.boxPoints(rect)
                    corners = box.astype(np.float32) / scale
                    if self._is_valid_quad(corners, h, w):
                        found_quad = corners

                if found_quad is not None:
                    score = self._evaluate_candidate(found_quad, image, 1.0 / scale)
                    candidates.append((found_quad, score))

        if candidates:
            candidates.sort(key=lambda x: x[1], reverse=True)
            return candidates[0][0]
        return None

    def _detect_by_straight_edges(self, image: np.ndarray) -> Optional[np.ndarray]:
        """
        基于直线边缘检测文档
        纸张有清晰的四条直线边缘，衣服边缘不规则
        """
        h, w = image.shape[:2]
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # 边缘检测 - 使用可配置参数
        edges = cv2.Canny(gray, self._canny_threshold1, self._canny_threshold2)

        # 霍夫直线检测 - 检测长直线
        lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=80,
                                minLineLength=min(h, w) // 4, maxLineGap=20)

        if lines is None or len(lines) < 4:
            return None

        # 分类并聚类直线
        horizontal_clusters = []  # (y位置, 最大长度, 线段列表)
        vertical_clusters = []    # (x位置, 最大长度, 线段列表)

        for line in lines:
            x1, y1, x2, y2 = line[0]
            length = np.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
            angle = np.abs(np.arctan2(y2 - y1, x2 - x1) * 180 / np.pi)

            if angle < 15 or angle > 165:  # 水平线
                y_pos = (y1 + y2) / 2
                x_min, x_max = min(x1, x2), max(x1, x2)
                # 尝试合并到现有聚类
                merged = False
                for i, (cy, cmax_len, cx_min, cx_max) in enumerate(horizontal_clusters):
                    if abs(cy - y_pos) < 30:  # 同一行
                        horizontal_clusters[i] = (
                            (cy + y_pos) / 2,
                            max(cmax_len, length),
                            min(cx_min, x_min),
                            max(cx_max, x_max)
                        )
                        merged = True
                        break
                if not merged:
                    horizontal_clusters.append((y_pos, length, x_min, x_max))

            elif 75 < angle < 105:  # 垂直线
                x_pos = (x1 + x2) / 2
                y_min, y_max = min(y1, y2), max(y1, y2)
                merged = False
                for i, (cx, cmax_len, cy_min, cy_max) in enumerate(vertical_clusters):
                    if abs(cx - x_pos) < 30:
                        vertical_clusters[i] = (
                            (cx + x_pos) / 2,
                            max(cmax_len, length),
                            min(cy_min, y_min),
                            max(cy_max, y_max)
                        )
                        merged = True
                        break
                if not merged:
                    vertical_clusters.append((x_pos, length, y_min, y_max))

        # 过滤掉图片边界线
        horizontal_clusters = [c for c in horizontal_clusters
                               if c[1] < w * 0.95 or not (c[0] < 30 or c[0] > h - 30)]
        vertical_clusters = [c for c in vertical_clusters
                             if c[1] < h * 0.95 or not (c[0] < 30 or c[0] > w - 30)]

        # 按长度排序
        horizontal_clusters.sort(key=lambda x: -x[1])
        vertical_clusters.sort(key=lambda x: -x[1])

        if len(horizontal_clusters) < 2 or len(vertical_clusters) < 2:
            return None

        # 尝试找到最佳的矩形组合
        best_rect = None
        best_score = 0

        # 尝试前几条水平线和垂直线的组合
        for h_idx1, (y1, _, _, _) in enumerate(horizontal_clusters[:5]):
            for h_idx2, (y2, _, _, _) in enumerate(horizontal_clusters[:5]):
                if h_idx1 >= h_idx2:
                    continue
                top_y, bottom_y = min(y1, y2), max(y1, y2)
                height = bottom_y - top_y
                if height < h * 0.1:  # 太矮
                    continue

                for v_idx1, (x1, _, _, _) in enumerate(vertical_clusters[:5]):
                    for v_idx2, (x2, _, _, _) in enumerate(vertical_clusters[:5]):
                        if v_idx1 >= v_idx2:
                            continue
                        left_x, right_x = min(x1, x2), max(x1, x2)
                        width = right_x - left_x
                        if width < w * 0.1:  # 太窄
                            continue

                        # 构建四边形
                        corners = np.array([
                            [left_x, top_y],
                            [right_x, top_y],
                            [right_x, bottom_y],
                            [left_x, bottom_y]
                        ], dtype=np.float32)

                        if not self._is_valid_quad(corners, h, w):
                            continue

                        # 评估这个矩形
                        score = self._evaluate_candidate(corners, image, 1.0)

                        # 额外加分：边缘检测得分
                        edge_score = self._straight_edge_score(corners, horizontal_clusters, vertical_clusters)
                        score = score * 0.7 + edge_score * 0.3

                        if score > best_score:
                            best_score = score
                            best_rect = corners

        return best_rect

    def _straight_edge_score(self, corners: np.ndarray,
                             h_clusters: list, v_clusters: list) -> float:
        """
        评估四边形边缘与检测到的直线的匹配程度
        """
        h, w = corners.max(axis=0) - corners.min(axis=0)
        h = int(h)
        w = int(w)

        # 四条边的位置
        top_y = min(corners[0, 1], corners[1, 1])
        bottom_y = max(corners[2, 1], corners[3, 1])
        left_x = min(corners[0, 0], corners[3, 0])
        right_x = max(corners[1, 0], corners[2, 0])

        score = 0
        img_h, img_w = corners.max(axis=0) + corners.min(axis=0)  # 粗略估计

        # 检查是否有匹配的水平线
        for y_pos, length, _, _ in h_clusters:
            if abs(y_pos - top_y) < 30 or abs(y_pos - bottom_y) < 30:
                score += 0.25 * min(1, length / w)

        # 检查是否有匹配的垂直线
        for x_pos, length, _, _ in v_clusters:
            if abs(x_pos - left_x) < 30 or abs(x_pos - right_x) < 30:
                score += 0.25 * min(1, length / h)

        return min(1, score)

    def _detect_by_edges(self, image: np.ndarray) -> Optional[np.ndarray]:
        """基于边缘检测的方法"""
        h, w = image.shape[:2]

        # 缩小图片加速处理
        max_size = 600
        if max(h, w) > max_size:
            scale = max_size / max(h, w)
            small = cv2.resize(image, None, fx=scale, fy=scale)
        else:
            small = image
            scale = 1.0

        sh, sw = small.shape[:2]
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        blur_size = self._blur_kernel * 2 + 1  # 确保是奇数
        blurred = cv2.GaussianBlur(gray, (blur_size, blur_size), 0)

        edges = cv2.Canny(blurred, self._canny_threshold1, self._canny_threshold2)
        kernel2 = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        dilated = cv2.dilate(edges, kernel2, iterations=2)
        closed = cv2.morphologyEx(dilated, cv2.MORPH_CLOSE, kernel2)

        contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        candidates = []
        if contours:
            contours = sorted(contours, key=cv2.contourArea, reverse=True)
            for contour in contours[:10]:
                area = cv2.contourArea(contour)
                if area < sh * sw * 0.05:
                    continue

                hull = cv2.convexHull(contour)
                peri = cv2.arcLength(hull, True)
                found_quad = None

                for eps in [0.02, 0.03, 0.04, 0.05]:
                    approx = cv2.approxPolyDP(hull, eps * peri, True)
                    if len(approx) == 4:
                        corners = approx.reshape(4, 2).astype(np.float32) / scale
                        if self._is_valid_quad(corners, h, w):
                            found_quad = corners
                            break

                if found_quad is None:
                    rect = cv2.minAreaRect(hull)
                    box = cv2.boxPoints(rect)
                    corners = box.astype(np.float32) / scale
                    if self._is_valid_quad(corners, h, w):
                        found_quad = corners

                if found_quad is not None:
                    score = self._evaluate_candidate(found_quad, image, 1.0 / scale)
                    candidates.append((found_quad, score))

        if candidates:
            candidates.sort(key=lambda x: x[1], reverse=True)
            return candidates[0][0]
        return None

    def _evaluate_candidate(self, corners: np.ndarray, original_image: np.ndarray,
                           scale: float) -> float:
        """
        评估候选四边形是否为真正的文档
        综合考虑：形状规则性、纹理均匀性、边缘清晰度
        """
        h, w = original_image.shape[:2]

        # 1. 形状规则性得分 (0-1)
        shape_score = self._shape_regularity_score(corners)

        # 2. 纹理均匀性得分 (0-1) - 纸张比衣服更均匀
        texture_score = self._texture_uniformity_score(corners, original_image)

        # 3. 边缘清晰度得分 (0-1) - 文档边缘更清晰
        edge_score = self._edge_clarity_score(corners, original_image, scale)

        # 4. 面积合理性得分
        area = cv2.contourArea(corners)
        area_ratio = area / (h * w)
        area_score = 1.0 if 0.1 <= area_ratio <= 0.9 else 0.5

        # 加权综合得分
        # 纹理均匀性和形状规则性是区分纸张和衣服的关键
        total_score = (
            shape_score * 0.30 +      # 形状规则性
            texture_score * 0.40 +    # 纹理均匀性（最重要）
            edge_score * 0.15 +       # 边缘清晰度
            area_score * 0.15         # 面积合理性
        )

        return total_score

    def _shape_regularity_score(self, corners: np.ndarray) -> float:
        """
        计算形状规则性得分
        文档通常是近似矩形，四边接近等长，角度接近90度
        """
        # 计算四条边长度
        sides = []
        for i in range(4):
            p1 = corners[i]
            p2 = corners[(i + 1) % 4]
            sides.append(np.linalg.norm(p2 - p1))

        sides = np.array(sides)

        # 边长比例得分 - 理想情况是对边相等
        side_ratios = [
            min(sides[0], sides[2]) / max(sides[0], sides[2]),  # 上下边
            min(sides[1], sides[3]) / max(sides[1], sides[3])   # 左右边
        ]
        side_score = np.mean(side_ratios)

        # 角度得分 - 理想情况是90度
        angles = []
        for i in range(4):
            p1 = corners[i]
            p2 = corners[(i + 1) % 4]
            p3 = corners[(i + 2) % 4]

            v1 = p1 - p2
            v2 = p3 - p2

            cos_angle = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-6)
            angle = np.degrees(np.arccos(np.clip(cos_angle, -1, 1)))
            angles.append(abs(angle - 90))

        angle_score = 1 - min(np.mean(angles) / 45, 1)  # 平均偏差45度得0分

        # 长宽比得分 - 文档通常不会太极端
        aspect_ratio = max(sides) / min(sides)
        aspect_score = 1 if aspect_ratio < 3 else max(0, 1 - (aspect_ratio - 3) / 5)

        return side_score * 0.4 + angle_score * 0.4 + aspect_score * 0.2

    def _texture_uniformity_score(self, corners: np.ndarray, image: np.ndarray) -> float:
        """
        计算纹理均匀性得分
        纸张表面平滑均匀，衣服有褶皱和纹理
        """
        # 提取四边形区域
        rect = self.order_points(corners.astype(np.float32))

        # 计算区域大小
        width = int(max(
            np.linalg.norm(rect[1] - rect[0]),
            np.linalg.norm(rect[2] - rect[3])
        ))
        height = int(max(
            np.linalg.norm(rect[3] - rect[0]),
            np.linalg.norm(rect[2] - rect[1])
        ))

        if width < 50 or height < 50:
            return 0.5

        # 透视变换提取区域
        dst = np.array([
            [0, 0],
            [width - 1, 0],
            [width - 1, height - 1],
            [0, height - 1]
        ], dtype=np.float32)

        M = cv2.getPerspectiveTransform(rect, dst)
        warped = cv2.warpPerspective(image, M, (width, height))

        # 转灰度
        gray = cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY)

        # 方法1: 局部标准差的变化 - 纸张应该很均匀
        block_size = max(16, min(width, height) // 10)
        if block_size % 2 == 0:
            block_size += 1

        # 计算局部均值和方差
        mean_val = cv2.blur(gray, (block_size, block_size))
        diff = gray.astype(np.float32) - mean_val.astype(np.float32)
        local_var = cv2.blur(diff ** 2, (block_size, block_size))
        local_std = np.sqrt(local_var)

        # 纸张：局部标准差小且均匀；衣服：局部标准差变化大
        std_of_std = np.std(local_std)
        mean_std = np.mean(local_std)

        # 标准差的标准差越小越好（均匀）
        uniformity = 1 / (1 + std_of_std / 20)

        # 方法2: 拉普拉斯响应 - 纸张平滑，衣服有纹理
        laplacian = cv2.Laplacian(gray, cv2.CV_64F)
        laplacian_var = laplacian.var()

        # 纸张的拉普拉斯方差较小（平滑）
        smoothness = 1 / (1 + laplacian_var / 500)

        # 方法3: 边缘密度 - 纸张内部边缘少，衣服褶皱多
        edges = cv2.Canny(gray, self._canny_threshold1, self._canny_threshold2)
        edge_density = np.sum(edges > 0) / (width * height)

        # 边缘密度越低越好
        edge_score = max(0, 1 - edge_density * 10)

        # 综合得分
        score = uniformity * 0.5 + smoothness * 0.3 + edge_score * 0.2

        return score

    def _edge_clarity_score(self, corners: np.ndarray, image: np.ndarray, scale: float) -> float:
        """
        计算边缘清晰度得分
        文档边缘清晰锐利，衣服边缘模糊不规则
        """
        # 沿着四条边采样边缘强度
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # 使用Sobel计算梯度
        grad_x = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
        grad_y = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
        gradient_mag = np.sqrt(grad_x ** 2 + grad_y ** 2)

        edge_strengths = []

        for i in range(4):
            p1 = corners[i].astype(int)
            p2 = corners[(i + 1) % 4].astype(int)

            # 沿边采样
            length = int(np.linalg.norm(p2 - p1))
            if length < 10:
                continue

            samples = max(10, length // 5)
            strengths = []

            for t in np.linspace(0, 1, samples):
                pt = p1 + t * (p2 - p1)
                px, py = int(pt[0]), int(pt[1])

                if 0 <= px < gray.shape[1] and 0 <= py < gray.shape[0]:
                    # 取边界附近的梯度
                    margin = 3
                    y_start = max(0, py - margin)
                    y_end = min(gray.shape[0], py + margin + 1)
                    x_start = max(0, px - margin)
                    x_end = min(gray.shape[1], px + margin + 1)

                    local_grad = gradient_mag[y_start:y_end, x_start:x_end]
                    strengths.append(np.max(local_grad))

            if strengths:
                edge_strengths.append(np.mean(strengths))

        if not edge_strengths:
            return 0.5

        # 边缘强度越强越清晰
        mean_strength = np.mean(edge_strengths)
        clarity_score = min(1, mean_strength / 50)

        # 边缘强度的一致性 - 文档边缘均匀
        consistency = 1 - min(1, np.std(edge_strengths) / (mean_strength + 1e-6))

        return clarity_score * 0.7 + consistency * 0.3

    def _is_valid_quad(self, corners: np.ndarray, h: int, w: int) -> bool:
        """验证四边形是否合理 - 放宽条件"""
        area = cv2.contourArea(corners)
        if area < h * w * 0.02 or area > h * w * 0.99:  # 放宽范围
            return False

        # 检查是否为凸四边形（允许轻微非凸）
        try:
            if not cv2.isContourConvex(corners.astype(np.int32)):
                # 检查凸性缺陷程度
                hull = cv2.convexHull(corners.astype(np.int32))
                hull_area = cv2.contourArea(hull)
                if hull_area > 0:
                    convexity = area / hull_area
                    if convexity < 0.85:  # 凸性不够
                        return False
        except:
            return False

        sides = []
        for i in range(4):
            p1 = corners[i]
            p2 = corners[(i + 1) % 4]
            sides.append(np.linalg.norm(p2 - p1))

        sides = np.array(sides)
        min_side = np.min(sides)
        max_side = np.max(sides)

        if min_side / max_side < 0.03:  # 放宽边长比例
            return False

        # 检查角点是否在图像范围内
        for corner in corners:
            if corner[0] < -w * 0.1 or corner[0] > w * 1.1:
                return False
            if corner[1] < -h * 0.1 or corner[1] > h * 1.1:
                return False

        return True

    def _evaluate_corners(self, corners: np.ndarray, image_area: float) -> float:
        """评估检测到的四边形质量"""
        if corners is None or len(corners) != 4:
            return 0

        area = cv2.contourArea(corners)
        area_ratio = area / image_area

        if area_ratio < 0.05 or area_ratio > 0.99:
            return 0

        sides = []
        for i in range(4):
            p1 = corners[i]
            p2 = corners[(i + 1) % 4]
            sides.append(np.linalg.norm(p2 - p1))

        sides = np.array(sides)
        side_ratio = np.min(sides) / np.max(sides)

        angles = []
        for i in range(4):
            p1 = corners[i]
            p2 = corners[(i + 1) % 4]
            p3 = corners[(i + 2) % 4]

            v1 = p1 - p2
            v2 = p3 - p2

            cos_angle = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-6)
            angle = np.degrees(np.arccos(np.clip(cos_angle, -1, 1)))
            angles.append(abs(angle - 90))

        angle_score = 1 - np.mean(angles) / 90

        score = area_ratio * 0.4 + side_ratio * 0.3 + angle_score * 0.3
        return score

    def order_points(self, pts: np.ndarray) -> np.ndarray:
        """按左上、右上、右下、左下排序"""
        rect = np.zeros((4, 2), dtype=np.float32)

        s = pts.sum(axis=1)
        rect[0] = pts[np.argmin(s)]
        rect[2] = pts[np.argmax(s)]

        diff = np.diff(pts, axis=1)
        rect[1] = pts[np.argmin(diff)]
        rect[3] = pts[np.argmax(diff)]

        return rect

    def four_point_transform(self, image: np.ndarray, pts: np.ndarray) -> np.ndarray:
        """透视变换矫正文档 - 输出标准A4比例"""
        rect = self.order_points(pts.astype(np.float32))

        # 收缩边界，确保不包含边界外的异物
        center = np.mean(rect, axis=0)
        shrink_ratio = 0.02  # 收缩2%
        shrunk_rect = center + (rect - center) * (1 - shrink_ratio)

        (tl, tr, br, bl) = shrunk_rect

        # 计算原始宽高
        widthA = np.linalg.norm(br - bl)
        widthB = np.linalg.norm(tr - tl)
        orig_width = max(widthA, widthB)

        heightA = np.linalg.norm(tr - br)
        heightB = np.linalg.norm(tl - bl)
        orig_height = max(heightA, heightB)

        # 3. 裁成标准A4比例 (210mm x 297mm = 1:1.414)
        a4_ratio = 210 / 297  # 宽/高 = 0.707
        orig_ratio = orig_width / orig_height

        if orig_ratio > a4_ratio:
            # 原图更宽，以宽度为基准调整高度
            target_width = orig_width
            target_height = orig_width / a4_ratio
        else:
            # 原图更高，以高度为基准调整宽度
            target_height = orig_height
            target_width = orig_height * a4_ratio

        maxWidth = int(target_width)
        maxHeight = int(target_height)

        dst = np.array([
            [0, 0],
            [maxWidth - 1, 0],
            [maxWidth - 1, maxHeight - 1],
            [0, maxHeight - 1]
        ], dtype=np.float32)

        M = cv2.getPerspectiveTransform(shrunk_rect, dst)

        # 创建白色背景
        warped = cv2.warpPerspective(
            image, M, (maxWidth, maxHeight),
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=(255, 255, 255)
        )

        return warped

    def enhance_document(self, image: np.ndarray, mode: str = 'scanner') -> np.ndarray:
        """文档增强处理"""
        if mode == 'original':
            return image

        if mode == 'bw':
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            result = cv2.adaptiveThreshold(
                gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY, 21, 10
            )
            return cv2.cvtColor(result, cv2.COLOR_GRAY2BGR)

        if mode == 'enhance':
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
            enhanced = clahe.apply(gray)
            return cv2.cvtColor(enhanced, cv2.COLOR_GRAY2BGR)

        if mode == 'magic_color':
            lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
            l = clahe.apply(l)
            lab = cv2.merge([l, a, b])
            return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)

        if mode == 'scanner':
            # 扫描仪效果 - 高清版
            h, w = image.shape[:2]

            # 1. 光照归一化去阴影（保留更多细节）
            kernel_size = max(101, min(h, w) // 4)  # 减小核大小保留更多细节
            if kernel_size % 2 == 0:
                kernel_size += 1

            b, g, r = cv2.split(image)
            def norm_ch(ch):
                bg = cv2.GaussianBlur(ch, (kernel_size, kernel_size), 0)
                # 保留更多原始细节
                normalized = np.clip(ch.astype(np.float32) * 230.0 / np.maximum(bg, 1), 0, 255).astype(np.uint8)
                # 与原图混合，保留细节
                return cv2.addWeighted(ch, 0.3, normalized, 0.7, 0)

            normalized = cv2.merge([norm_ch(b), norm_ch(g), norm_ch(r)])

            # 2. 用原图检测彩色区域（印章等）
            hsv_orig = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
            sat_orig = hsv_orig[:, :, 1]
            hue_orig = hsv_orig[:, :, 0]

            # 红色印章检测（更宽松）
            is_red = ((hue_orig < 20) | (hue_orig > 160)) & (sat_orig > 25)
            # 其他鲜艳彩色（更宽松）
            is_colorful = sat_orig > 50

            is_color = is_red | is_colorful

            # 3. 自适应增强而非完全二值化
            gray = cv2.cvtColor(normalized, cv2.COLOR_BGR2GRAY)

            # 使用CLAHE增强对比度，保留灰度层次
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            enhanced_gray = clahe.apply(gray)

            # 转回彩色
            result = cv2.cvtColor(enhanced_gray, cv2.COLOR_GRAY2BGR)

            # 4. 轻微提亮背景
            # 检测背景（较亮区域）
            _, binary_bg = cv2.threshold(enhanced_gray, 200, 255, cv2.THRESH_BINARY)
            # 背景区域提亮
            result[binary_bg == 255] = np.clip(result[binary_bg == 255].astype(np.float32) * 1.1, 0, 255).astype(np.uint8)

            # 5. 高质量锐化
            kernel_sharpen = np.array([
                [0, -1, 0],
                [-1, 5, -1],
                [0, -1, 0]
            ], dtype=np.float32)
            sharpened = cv2.filter2D(result, -1, kernel_sharpen)
            result = cv2.addWeighted(result, 0.7, sharpened, 0.3, 0)

            # 6. 彩色区域单独处理
            if np.any(is_color):
                color_result = image.copy()
                lab = cv2.cvtColor(color_result, cv2.COLOR_BGR2LAB)
                l_ch, a_ch, b_ch = cv2.split(lab)

                # 增强饱和度
                a_enhanced = np.clip(a_ch.astype(np.float32) * 1.15, 0, 255).astype(np.uint8)
                b_enhanced = np.clip(b_ch.astype(np.float32) * 1.15, 0, 255).astype(np.uint8)
                l_enhanced = clahe.apply(l_ch)

                lab_enhanced = cv2.merge([l_enhanced, a_enhanced, b_enhanced])
                color_enhanced = cv2.cvtColor(lab_enhanced, cv2.COLOR_LAB2BGR)

                # 锐化彩色区域
                sharpened_color = cv2.filter2D(color_enhanced, -1, kernel_sharpen)
                color_enhanced = cv2.addWeighted(color_enhanced, 0.7, sharpened_color, 0.3, 0)

                # 恢复彩色区域
                result[is_color] = color_enhanced[is_color]

            # 7. 最终对比度增强
            lab_final = cv2.cvtColor(result, cv2.COLOR_BGR2LAB)
            l_final = lab_final[:, :, 0]
            l_final = cv2.convertScaleAbs(l_final, alpha=1.1, beta=5)
            lab_final[:, :, 0] = l_final
            result = cv2.cvtColor(lab_final, cv2.COLOR_LAB2BGR)

            return result

        return image

    def scan(self, image: np.ndarray, enhance_mode: str = 'scanner') -> DocumentResult:
        """执行完整扫描流程"""
        corners = self.detect_document(image)

        if corners is None:
            return DocumentResult(
                original=image,
                scanned=self.enhance_document(image, enhance_mode),
                corners=None,
                confidence=0.0
            )

        scanned = self.four_point_transform(image, corners)
        enhanced = self.enhance_document(scanned, enhance_mode)

        return DocumentResult(
            original=image,
            scanned=enhanced,
            corners=corners.astype(np.int32),
            confidence=1.0
        )

    def detect_with_debug(self, image: np.ndarray, enhance_mode: str = 'scanner') -> Tuple[DocumentResult, List]:
        """带调试信息的检测"""
        stages = []

        stages.append(('Original', image.copy()))

        corners = self.detect_document(image)

        display = image.copy()
        if corners is not None:
            corners_int = corners.astype(np.int32)
            cv2.drawContours(display, [corners_int], -1, (0, 255, 0), 3)
            for i, pt in enumerate(corners_int):
                cv2.circle(display, tuple(pt), 15, (0, 0, 255), -1)
                cv2.putText(display, str(i), tuple(pt - 20),
                           cv2.FONT_HERSHEY_SIMPLEX, 1.5, (255, 0, 0), 3)

        stages.append(('Detected', display))

        result = self.scan(image, enhance_mode)

        # 始终显示扫描结果
        stages.append(('Scanned', result.scanned))

        return result, stages
