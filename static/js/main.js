// 文档扫描器

class DocumentScanner {
    constructor() {
        this.video = document.getElementById('video');
        this.overlay = document.getElementById('overlay');
        this.guideText = document.getElementById('guide-text');
        this.resultImage = document.getElementById('result-image');
        this.loading = document.getElementById('loading');
        this.scanMode = document.getElementById('scan-mode');
        this.resultMode = document.getElementById('result-mode');
        this.enhanceModeSelect = document.getElementById('enhance-mode');
        this.fileInput = document.getElementById('file-input');
        this.pageCount = document.getElementById('page-count');
        this.countNum = document.getElementById('count-num');
        this.pagesPreview = document.getElementById('pages-preview');
        this.pdfOrder = document.getElementById('pdf-order');

        this.stream = null;
        this.facingMode = 'environment';
        this.capturedImage = null;
        this.croppedImage = null;
        this.pages = [];
        this.currentPageIndex = -1;

        this.init();
    }

    async init() {
        this.bindEvents();
        await this.startCamera();
    }

    bindEvents() {
        var self = this;
        document.getElementById('btn-capture').onclick = function() { self.capture(); };
        document.getElementById('btn-switch').onclick = function() { self.switchCam(); };
        document.getElementById('btn-gallery').onclick = function() { self.fileInput.click(); };
        this.fileInput.onchange = function(e) { if(e.target.files[0]) self.loadFile(e.target.files[0]); };
        document.getElementById('btn-continue').onclick = function() { self.continueCapture(); };
        document.getElementById('btn-retake').onclick = function() { self.retake(); };
        document.getElementById('btn-download').onclick = function() { self.download(); };
        document.getElementById('btn-export-pdf').onclick = function() { self.exportPDF(); };
        this.enhanceModeSelect.onchange = function() { if(self.croppedImage) self.applyFilter(); };
        this.pdfOrder.onchange = function() { self.updatePagesPreview(); };
    }

    async startCamera() {
        console.log('启动摄像头...');
        try {
            if (this.stream) {
                this.stream.getTracks().forEach(t => t.stop());
            }

            this.stream = await navigator.mediaDevices.getUserMedia({
                video: { facingMode: this.facingMode, width: { ideal: 4096 }, height: { ideal: 2160 } }
            });

            this.video.srcObject = this.stream;

            // 等待视频元数据加载
            await new Promise((resolve, reject) => {
                this.video.onloadedmetadata = resolve;
                this.video.onerror = reject;
                setTimeout(reject, 10000);
            });

            // 等待视频准备好播放
            await this.video.play();

            // 等待视频帧数据准备好
            await new Promise((resolve, reject) => {
                var checkReady = () => {
                    if (this.video.readyState >= 2 && this.video.videoWidth > 0 && this.video.videoHeight > 0) {
                        console.log('视频已准备好, readyState:', this.video.readyState, '尺寸:', this.video.videoWidth, 'x', this.video.videoHeight);
                        resolve();
                    } else {
                        console.log('等待视频... readyState:', this.video.readyState, '尺寸:', this.video.videoWidth, 'x', this.video.videoHeight);
                        setTimeout(checkReady, 100);
                    }
                };
                checkReady();
                setTimeout(reject, 10000);
            });

            console.log('摄像头启动成功, 尺寸:', this.video.videoWidth, 'x', this.video.videoHeight);
            this.guideText.textContent = '点击拍照按钮扫描文档';
        } catch (e) {
            console.error('摄像头错误:', e);
            alert('无法打开摄像头: ' + e.message);
        }
    }

    async capture() {
        // 检查视频是否准备好
        if (!this.video.videoWidth || !this.video.videoHeight) {
            alert('摄像头未准备好，请稍后再试');
            return;
        }

        console.log('拍照, 视频尺寸:', this.video.videoWidth, 'x', this.video.videoHeight);
        this.showLoading(true);

        try {
            var canvas = document.createElement('canvas');
            canvas.width = this.video.videoWidth;
            canvas.height = this.video.videoHeight;
            var ctx = canvas.getContext('2d');
            ctx.drawImage(this.video, 0, 0);
            this.capturedImage = canvas.toDataURL('image/jpeg', 0.95);

            console.log('图片大小:', this.capturedImage.length);

            if (this.capturedImage.length < 100) {
                throw new Error('图片数据太短，可能捕获失败');
            }

            await this.scan();
        } catch (e) {
            console.error('拍照错误:', e);
            alert('拍照失败: ' + e.message);
        }
        this.showLoading(false);
    }

    async loadFile(file) {
        this.showLoading(true);
        var self = this;
        var reader = new FileReader();
        reader.onload = async function(e) {
            self.capturedImage = e.target.result;
            await self.scan();
            self.showLoading(false);
        };
        reader.readAsDataURL(file);
    }

    async scan() {
        console.log('发送扫描请求, 图片大小:', this.capturedImage ? this.capturedImage.length : 0);
        try {
            var resp = await fetch('/api/scan', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ image: this.capturedImage, mode: this.enhanceModeSelect.value })
            });
            var data = await resp.json();
            console.log('扫描响应:', data);
            if (data.success) {
                this.croppedImage = data.cropped || data.image;
                this.pages.push({
                    cropped: this.croppedImage,
                    enhanced: data.image
                });
                this.currentPageIndex = this.pages.length - 1;
                this.resultImage.src = data.image;
                this.updatePageCount();
                this.updatePagesPreview();
                this.showResult(true);
            } else {
                alert('扫描失败: ' + data.error);
            }
        } catch (e) {
            console.error('扫描请求错误:', e);
            alert('扫描请求失败: ' + e.message);
        }
    }

    updatePageCount() {
        if (this.pages.length > 0) {
            this.pageCount.style.display = 'block';
            this.countNum.textContent = this.pages.length;
        } else {
            this.pageCount.style.display = 'none';
        }
        // 更新PDF导出按钮的页数显示
        var pdfPageCount = document.getElementById('pdf-page-count');
        if (pdfPageCount) {
            pdfPageCount.textContent = this.pages.length;
        }
    }

    updatePagesPreview() {
        this.pagesPreview.innerHTML = '';

        // 获取排序后的索引数组
        var indices = [];
        for (var i = 0; i < this.pages.length; i++) {
            indices.push(i);
        }

        // 根据排序选项调整顺序
        if (this.pdfOrder && this.pdfOrder.value === 'desc') {
            indices.reverse();
        }

        // 显示缩略图，显示的页码是PDF中的实际页码
        for (var p = 0; p < indices.length; p++) {
            (function(pdfPageNum, originalIndex, self) {
                var thumb = document.createElement('div');
                thumb.className = 'page-thumb' + (originalIndex === self.currentPageIndex ? ' active' : '');
                thumb.innerHTML = '<img src="' + self.pages[originalIndex].enhanced + '" alt="第' + (pdfPageNum + 1) + '页">' +
                    '<span class="page-num">P' + (pdfPageNum + 1) + '</span>';
                thumb.onclick = function() {
                    self.selectPage(originalIndex);
                };
                self.pagesPreview.appendChild(thumb);
            })(p, indices[p], this);
        }
    }

    selectPage(index) {
        if (index >= 0 && index < this.pages.length) {
            this.currentPageIndex = index;
            var page = this.pages[index];
            this.croppedImage = page.cropped;
            this.resultImage.src = page.enhanced;
            this.updatePagesPreview();
        }
    }

    continueCapture() {
        this.capturedImage = null;
        this.croppedImage = null;
        this.showResult(false);
        this.startCamera();
    }

    async applyFilter() {
        if (!this.croppedImage) return;
        this.showLoading(true);
        var resp = await fetch('/api/enhance', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ image: this.croppedImage, mode: this.enhanceModeSelect.value })
        });
        var data = await resp.json();
        if (data.success) {
            this.resultImage.src = data.image;
            if (this.currentPageIndex >= 0) {
                this.pages[this.currentPageIndex].enhanced = data.image;
                this.updatePagesPreview();
            }
        }
        this.showLoading(false);
    }

    download() {
        var a = document.createElement('a');
        a.download = 'scanned_page_' + (this.currentPageIndex + 1) + '.png';
        a.href = this.resultImage.src;
        a.click();
    }

    retake() {
        if (this.currentPageIndex >= 0) {
            this.pages.splice(this.currentPageIndex, 1);
            if (this.pages.length > 0) {
                this.currentPageIndex = Math.min(this.currentPageIndex, this.pages.length - 1);
                var page = this.pages[this.currentPageIndex];
                this.croppedImage = page.cropped;
                this.resultImage.src = page.enhanced;
                this.updatePageCount();
                this.updatePagesPreview();
            } else {
                this.capturedImage = null;
                this.croppedImage = null;
                this.currentPageIndex = -1;
                this.updatePageCount();
                this.showResult(false);
                this.startCamera();
            }
        }
    }

    async exportPDF() {
        if (this.pages.length === 0) {
            alert('请先扫描文档');
            return;
        }

        this.showLoading(true);

        try {
            var orderedPages = this.pages.slice();
            console.log('原始顺序: 第1页到第' + this.pages.length + '页');

            if (this.pdfOrder && this.pdfOrder.value === 'desc') {
                orderedPages.reverse();
                console.log('降序: 第' + this.pages.length + '页到第1页');
            } else {
                console.log('升序: 第1页到第' + this.pages.length + '页');
            }

            var pagesData = [];
            for (var i = 0; i < orderedPages.length; i++) {
                pagesData.push(orderedPages[i].enhanced);
            }

            var resp = await fetch('/api/export-pdf', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ pages: pagesData })
            });

            if (resp.ok) {
                var blob = await resp.blob();

                // 直接下载PDF
                var url = URL.createObjectURL(blob);
                var a = document.createElement('a');
                a.download = 'scanned_document.pdf';
                a.href = url;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                URL.revokeObjectURL(url);

                // 显示下载成功提示
                alert('PDF已下载！\n\n分享方法：\n1. 打开微信/QQ\n2. 选择发送文件\n3. 在下载目录找到 scanned_document.pdf');
            } else {
                alert('导出PDF失败');
            }
        } catch (e) {
            console.error('导出出错:', e);
            // 分享取消或失败时也尝试下载
            if (e.name !== 'AbortError') {
                alert('导出出错: ' + e.message);
            }
        }

        this.showLoading(false);
    }

    async switchCam() {
        if (this.stream) {
            this.stream.getTracks().forEach(function(t) { t.stop(); });
        }
        this.facingMode = this.facingMode === 'environment' ? 'user' : 'environment';
        await this.startCamera();
    }

    showResult(show) {
        this.scanMode.classList.toggle('active', !show);
        this.resultMode.classList.toggle('active', show);
    }

    showLoading(show) {
        this.loading.classList.toggle('active', show);
    }
}

document.addEventListener('DOMContentLoaded', function() {
    new DocumentScanner();
});
