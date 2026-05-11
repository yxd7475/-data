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

        this.stream = null;
        this.facingMode = 'environment';
        this.capturedImage = null;
        this.croppedImage = null;

        this.init();
    }

    async init() {
        this.bindEvents();
        await this.startCamera();
    }

    bindEvents() {
        document.getElementById('btn-capture').onclick = () => this.capture();
        document.getElementById('btn-switch').onclick = () => this.switchCam();
        document.getElementById('btn-gallery').onclick = () => this.fileInput.click();
        this.fileInput.onchange = (e) => e.target.files[0] && this.loadFile(e.target.files[0]);
        document.getElementById('btn-retake').onclick = () => this.retake();
        document.getElementById('btn-download').onclick = () => this.download();
        document.getElementById('btn-apply').onclick = () => this.applyFilter();
        this.enhanceModeSelect.onchange = () => this.croppedImage && this.applyFilter();
    }

    async startCamera() {
        try {
            this.stream = await navigator.mediaDevices.getUserMedia({
                video: { facingMode: this.facingMode, width: { ideal: 4096 }, height: { ideal: 2160 } }
            });
            this.video.srcObject = this.stream;
            await this.video.play();
            this.guideText.textContent = '点击拍照按钮扫描文档';
        } catch (e) {
            alert('无法打开摄像头: ' + e.message);
        }
    }

    async capture() {
        this.showLoading(true);

        const canvas = document.createElement('canvas');
        canvas.width = this.video.videoWidth;
        canvas.height = this.video.videoHeight;
        canvas.getContext('2d').drawImage(this.video, 0, 0);
        this.capturedImage = canvas.toDataURL('image/png');

        await this.scan();
        this.showLoading(false);
    }

    async loadFile(file) {
        this.showLoading(true);
        const reader = new FileReader();
        reader.onload = async (e) => {
            this.capturedImage = e.target.result;
            await this.scan();
            this.showLoading(false);
        };
        reader.readAsDataURL(file);
    }

    async scan() {
        const resp = await fetch('/api/scan', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ image: this.capturedImage, mode: this.enhanceModeSelect.value })
        });
        const data = await resp.json();
        if (data.success) {
            this.croppedImage = data.cropped || data.image;
            this.resultImage.src = data.image;
            this.showResult(true);
        } else {
            alert('扫描失败: ' + data.error);
        }
    }

    async applyFilter() {
        if (!this.croppedImage) return;
        this.showLoading(true);
        const resp = await fetch('/api/enhance', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ image: this.croppedImage, mode: this.enhanceModeSelect.value })
        });
        const data = await resp.json();
        if (data.success) this.resultImage.src = data.image;
        this.showLoading(false);
    }

    download() {
        const a = document.createElement('a');
        a.download = 'scanned.png';
        a.href = this.resultImage.src;
        a.click();
    }

    retake() {
        this.capturedImage = null;
        this.croppedImage = null;
        this.showResult(false);
    }

    async switchCam() {
        if (this.stream) {
            this.stream.getTracks().forEach(t => t.stop());
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

document.addEventListener('DOMContentLoaded', () => {
    new DocumentScanner();
});
