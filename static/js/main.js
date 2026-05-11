/**
 * 文档扫描器 - JavaScript 优化版
 *
 * 优化点:
 * 1. 使用 const/let 替代 var
 * 2. 使用箭头函数避免 this 绑定问题
 * 3. 缓存 DOM 元素避免重复查询
 * 4. 使用模板字符串
 * 5. 使用数组方法替代 for 循环
 * 6. 提前返回减少嵌套
 * 7. 使用 DocumentFragment 批量 DOM 操作
 */

class DocumentScanner {
    constructor() {
        // 缓存所有 DOM 元素
        this.elements = {
            video: document.getElementById('video'),
            overlay: document.getElementById('overlay'),
            guideText: document.getElementById('guide-text'),
            resultImage: document.getElementById('result-image'),
            loading: document.getElementById('loading'),
            scanMode: document.getElementById('scan-mode'),
            resultMode: document.getElementById('result-mode'),
            enhanceModeSelect: document.getElementById('enhance-mode'),
            fileInput: document.getElementById('file-input'),
            pageCount: document.getElementById('page-count'),
            countNum: document.getElementById('count-num'),
            pagesPreview: document.getElementById('pages-preview'),
            pdfOrder: document.getElementById('pdf-order'),
            pdfPageCount: document.getElementById('pdf-page-count'),
            btnCapture: document.getElementById('btn-capture'),
            btnSwitch: document.getElementById('btn-switch'),
            btnGallery: document.getElementById('btn-gallery'),
            btnContinue: document.getElementById('btn-continue'),
            btnRetake: document.getElementById('btn-retake'),
            btnDownload: document.getElementById('btn-download'),
            btnExportPdf: document.getElementById('btn-export-pdf')
        };

        // 状态
        this.stream = null;
        this.facingMode = 'environment';
        this.capturedImage = null;
        this.croppedImage = null;
        this.pages = [];
        this.currentPageIndex = -1;

        // 复用 canvas 避免重复创建
        this.captureCanvas = document.createElement('canvas');
        this.captureCtx = this.captureCanvas.getContext('2d');

        this.init();
    }

    async init() {
        this.bindEvents();
        await this.startCamera();
    }

    bindEvents() {
        const { elements } = this;

        // 使用箭头函数绑定事件
        elements.btnCapture.onclick = () => this.capture();
        elements.btnSwitch.onclick = () => this.switchCam();
        elements.btnGallery.onclick = () => elements.fileInput.click();
        elements.fileInput.onchange = (e) => {
            if (e.target.files[0]) this.loadFile(e.target.files[0]);
        };
        elements.btnContinue.onclick = () => this.continueCapture();
        elements.btnRetake.onclick = () => this.retake();
        elements.btnDownload.onclick = () => this.download();
        elements.btnExportPdf.onclick = () => this.exportPDF();
        elements.enhanceModeSelect.onchange = () => {
            if (this.croppedImage) this.applyFilter();
        };
        elements.pdfOrder.onchange = () => this.updatePagesPreview();
    }

    async startCamera() {
        const { video, guideText } = this.elements;

        console.log('启动摄像头...');

        try {
            // 停止现有流
            if (this.stream) {
                this.stream.getTracks().forEach(track => track.stop());
            }

            // 获取新流
            this.stream = await navigator.mediaDevices.getUserMedia({
                video: {
                    facingMode: this.facingMode,
                    width: { ideal: 4096 },
                    height: { ideal: 2160 }
                }
            });

            video.srcObject = this.stream;

            // 等待视频元数据加载
            await new Promise((resolve, reject) => {
                const timeout = setTimeout(() => reject(new Error('视频加载超时')), 10000);

                video.onloadedmetadata = () => {
                    clearTimeout(timeout);
                    resolve();
                };
                video.onerror = () => {
                    clearTimeout(timeout);
                    reject(new Error('视频加载失败'));
                };
            });

            await video.play();

            // 等待视频帧数据准备好
            await this.waitForVideoReady(video);

            console.log(`摄像头启动成功, 尺寸: ${video.videoWidth}x${video.videoHeight}`);
            guideText.textContent = '点击拍照按钮扫描文档';

        } catch (error) {
            console.error('摄像头错误:', error);
            this.showError(`无法打开摄像头: ${error.message}`);
        }
    }

    waitForVideoReady(video) {
        return new Promise((resolve, reject) => {
            const timeout = setTimeout(() => reject(new Error('视频就绪超时')), 10000);
            const maxChecks = 100;
            let checks = 0;

            const checkReady = () => {
                checks++;

                if (video.readyState >= 2 && video.videoWidth > 0 && video.videoHeight > 0) {
                    clearTimeout(timeout);
                    console.log(`视频已准备好, readyState: ${video.readyState}`);
                    resolve();
                } else if (checks < maxChecks) {
                    setTimeout(checkReady, 100);
                } else {
                    clearTimeout(timeout);
                    reject(new Error('视频就绪检测超时'));
                }
            };

            checkReady();
        });
    }

    async capture() {
        const { video } = this.elements;

        // 提前检查并返回
        if (!video.videoWidth || !video.videoHeight) {
            this.showError('摄像头未准备好，请稍后再试');
            return;
        }

        console.log(`拍照, 视频尺寸: ${video.videoWidth}x${video.videoHeight}`);
        this.showLoading(true);

        try {
            // 复用 canvas
            this.captureCanvas.width = video.videoWidth;
            this.captureCanvas.height = video.videoHeight;
            this.captureCtx.drawImage(video, 0, 0);

            this.capturedImage = this.captureCanvas.toDataURL('image/jpeg', 0.95);

            const imageSize = this.capturedImage.length;
            console.log(`图片大小: ${imageSize}`);

            if (imageSize < 100) {
                throw new Error('图片数据太短，可能捕获失败');
            }

            await this.scan();

        } catch (error) {
            console.error('拍照错误:', error);
            this.showError(`拍照失败: ${error.message}`);
        } finally {
            this.showLoading(false);
        }
    }

    async loadFile(file) {
        if (!file) return;

        this.showLoading(true);

        try {
            this.capturedImage = await this.readFileAsDataURL(file);
            await this.scan();
        } catch (error) {
            console.error('加载文件错误:', error);
            this.showError(`加载文件失败: ${error.message}`);
        } finally {
            this.showLoading(false);
        }
    }

    readFileAsDataURL(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = (e) => resolve(e.target.result);
            reader.onerror = () => reject(new Error('文件读取失败'));
            reader.readAsDataURL(file);
        });
    }

    async scan() {
        const { enhanceModeSelect, resultImage } = this.elements;

        console.log(`发送扫描请求, 图片大小: ${this.capturedImage?.length || 0}`);

        try {
            const response = await this.postJSON('/api/scan', {
                image: this.capturedImage,
                mode: enhanceModeSelect.value
            });

            if (!response.success) {
                this.showError(`扫描失败: ${response.error}`);
                return;
            }

            // 更新状态
            this.croppedImage = response.cropped || response.image;
            this.pages.push({
                cropped: this.croppedImage,
                enhanced: response.image
            });
            this.currentPageIndex = this.pages.length - 1;

            // 更新 UI
            resultImage.src = response.image;
            this.updatePageCount();
            this.updatePagesPreview();
            this.showResult(true);

        } catch (error) {
            console.error('扫描请求错误:', error);
            this.showError(`扫描请求失败: ${error.message}`);
        }
    }

    async postJSON(url, data) {
        const response = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        return response.json();
    }

    updatePageCount() {
        const { pageCount, countNum, pdfPageCount } = this.elements;
        const pageCountValue = this.pages.length;

        // 更新拍照界面页数
        pageCount.style.display = pageCountValue > 0 ? 'block' : 'none';
        countNum.textContent = pageCountValue;

        // 更新PDF导出按钮页数
        if (pdfPageCount) {
            pdfPageCount.textContent = pageCountValue;
        }
    }

    updatePagesPreview() {
        const { pagesPreview, pdfOrder } = this.elements;
        const pages = this.pages;

        // 提前返回
        if (pages.length === 0) {
            pagesPreview.innerHTML = '';
            return;
        }

        // 创建文档片段批量添加
        const fragment = document.createDocumentFragment();

        // 获取排序后的索引
        const indices = Array.from({ length: pages.length }, (_, i) => i);
        const isDescending = pdfOrder?.value === 'desc';

        if (isDescending) {
            indices.reverse();
        }

        // 构建缩略图
        indices.forEach((originalIndex, displayIndex) => {
            const thumb = document.createElement('div');
            thumb.className = 'page-thumb' + (originalIndex === this.currentPageIndex ? ' active' : '');

            const img = document.createElement('img');
            img.src = pages[originalIndex].enhanced;
            img.alt = `第${displayIndex + 1}页`;

            const pageNum = document.createElement('span');
            pageNum.className = 'page-num';
            pageNum.textContent = `P${displayIndex + 1}`;

            thumb.appendChild(img);
            thumb.appendChild(pageNum);
            thumb.onclick = () => this.selectPage(originalIndex);

            fragment.appendChild(thumb);
        });

        // 一次性更新 DOM
        pagesPreview.innerHTML = '';
        pagesPreview.appendChild(fragment);
    }

    selectPage(index) {
        const { resultImage } = this.elements;
        const page = this.pages[index];

        if (!page) return;

        this.currentPageIndex = index;
        this.croppedImage = page.cropped;
        resultImage.src = page.enhanced;
        this.updatePagesPreview();
    }

    continueCapture() {
        this.capturedImage = null;
        this.croppedImage = null;
        this.showResult(false);
        this.startCamera();
    }

    async applyFilter() {
        if (!this.croppedImage) return;

        const { enhanceModeSelect, resultImage } = this.elements;

        this.showLoading(true);

        try {
            const response = await this.postJSON('/api/enhance', {
                image: this.croppedImage,
                mode: enhanceModeSelect.value
            });

            if (response.success) {
                resultImage.src = response.image;

                // 更新当前页面
                if (this.currentPageIndex >= 0) {
                    this.pages[this.currentPageIndex].enhanced = response.image;
                    this.updatePagesPreview();
                }
            }
        } catch (error) {
            console.error('滤镜应用错误:', error);
            this.showError(`滤镜应用失败: ${error.message}`);
        } finally {
            this.showLoading(false);
        }
    }

    download() {
        const { resultImage } = this.elements;
        const link = document.createElement('a');
        link.download = `scanned_page_${this.currentPageIndex + 1}.png`;
        link.href = resultImage.src;
        link.click();
    }

    retake() {
        if (this.currentPageIndex < 0) return;

        this.pages.splice(this.currentPageIndex, 1);
        this.croppedImage = null;

        if (this.pages.length > 0) {
            // 切换到上一页
            this.currentPageIndex = Math.min(this.currentPageIndex, this.pages.length - 1);
            const page = this.pages[this.currentPageIndex];
            this.croppedImage = page.cropped;
            this.elements.resultImage.src = page.enhanced;
            this.updatePageCount();
            this.updatePagesPreview();
        } else {
            // 没有页面了，返回拍照
            this.capturedImage = null;
            this.currentPageIndex = -1;
            this.updatePageCount();
            this.showResult(false);
            this.startCamera();
        }
    }

    async exportPDF() {
        if (this.pages.length === 0) {
            this.showError('请先扫描文档');
            return;
        }

        const { pdfOrder } = this.elements;
        this.showLoading(true);

        try {
            // 准备页面数据
            const orderedPages = pdfOrder?.value === 'desc'
                ? [...this.pages].reverse()
                : [...this.pages];

            const pagesData = orderedPages.map(page => page.enhanced);

            console.log(`导出PDF: ${pagesData.length}页, ${pdfOrder?.value === 'desc' ? '降序' : '升序'}`);

            const response = await fetch('/api/export-pdf', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ pages: pagesData })
            });

            if (!response.ok) {
                throw new Error('服务器响应错误');
            }

            // 下载文件
            const blob = await response.blob();
            this.downloadBlob(blob, 'scanned_document.pdf');

            this.showSuccess('PDF已下载！\n\n分享方法：\n1. 打开微信/QQ\n2. 选择发送文件\n3. 在下载目录找到 scanned_document.pdf');

        } catch (error) {
            console.error('导出出错:', error);
            this.showError(`导出出错: ${error.message}`);
        } finally {
            this.showLoading(false);
        }
    }

    downloadBlob(blob, filename) {
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');

        link.download = filename;
        link.href = url;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);

        // 延迟释放 URL
        setTimeout(() => URL.revokeObjectURL(url), 1000);
    }

    async switchCam() {
        if (this.stream) {
            this.stream.getTracks().forEach(track => track.stop());
        }

        this.facingMode = this.facingMode === 'environment' ? 'user' : 'environment';
        await this.startCamera();
    }

    showResult(show) {
        const { scanMode, resultMode } = this.elements;
        scanMode.classList.toggle('active', !show);
        resultMode.classList.toggle('active', show);
    }

    showLoading(show) {
        this.elements.loading.classList.toggle('active', show);
    }

    showError(message) {
        alert(message);
    }

    showSuccess(message) {
        alert(message);
    }
}

// 初始化
document.addEventListener('DOMContentLoaded', () => {
    new DocumentScanner();
});
