// pages/index/index.js
const app = getApp()

Page({
  data: {
    devicePosition: 'back',  // 摄像头方向
    flashMode: 'auto',       // 闪光灯模式
    loading: false,
    loadingText: '处理中...',
    pages: [],               // 已扫描的页面
    filterIndex: 0,
    filterOptions: [
      { value: 'scanner', label: '扫描仪效果' },
      { value: 'original', label: '原图' },
      { value: 'enhance', label: '增强对比度' },
      { value: 'bw', label: '黑白文档' },
      { value: 'magic_color', label: '魔法色彩' }
    ]
  },

  onLoad() {
    // 获取全局数据中的已扫描页面
    this.setData({
      pages: app.globalData.pages || []
    })
  },

  onShow() {
    // 每次显示页面时更新页面数据
    this.setData({
      pages: app.globalData.pages || []
    })
  },

  // 切换摄像头
  switchCamera() {
    this.setData({
      devicePosition: this.data.devicePosition === 'back' ? 'front' : 'back'
    })
  },

  // 从相册选择
  chooseFromAlbum() {
    wx.chooseMedia({
      count: 1,
      mediaType: ['image'],
      sourceType: ['album'],
      success: (res) => {
        const tempFilePath = res.tempFiles[0].tempFilePath
        this.processImage(tempFilePath)
      }
    })
  },

  // 拍照
  takePhoto() {
    const ctx = wx.createCameraContext()

    this.setData({ loading: true, loadingText: '拍照中...' })

    ctx.takePhoto({
      quality: 'high',
      success: (res) => {
        this.processImage(res.tempImagePath)
      },
      fail: (err) => {
        console.error('拍照失败:', err)
        wx.showToast({ title: '拍照失败', icon: 'error' })
        this.setData({ loading: false })
      }
    })
  },

  // 处理图片
  async processImage(imagePath) {
    this.setData({ loadingText: '正在扫描...' })

    try {
      // 获取图片信息
      const imageInfo = await this.getImageInfo(imagePath)

      // 压缩图片
      const compressedPath = await this.compressImage(imagePath)

      // 转换为base64
      const base64 = await this.imageToBase64(compressedPath)

      // 调用云函数处理
      const result = await this.callScanFunction(base64)

      if (result.success) {
        // 保存到全局数据
        const pageData = {
          cropped: result.cropped || result.image,
          enhanced: result.image,
          detected: result.detected
        }

        app.globalData.pages.push(pageData)
        app.globalData.currentPageIndex = app.globalData.pages.length - 1

        this.setData({
          pages: app.globalData.pages,
          loading: false
        })

        // 跳转到结果页
        wx.navigateTo({
          url: '/pages/result/result'
        })
      } else {
        throw new Error(result.error || '扫描失败')
      }
    } catch (error) {
      console.error('处理图片失败:', error)
      wx.showToast({
        title: error.message || '处理失败',
        icon: 'error'
      })
      this.setData({ loading: false })
    }
  },

  // 获取图片信息
  getImageInfo(imagePath) {
    return new Promise((resolve, reject) => {
      wx.getImageInfo({
        src: imagePath,
        success: resolve,
        fail: reject
      })
    })
  },

  // 压缩图片
  compressImage(imagePath) {
    return new Promise((resolve, reject) => {
      wx.compressImage({
        src: imagePath,
        quality: 80,
        success: (res) => resolve(res.tempFilePath),
        fail: reject
      })
    })
  },

  // 图片转base64
  imageToBase64(imagePath) {
    return new Promise((resolve, reject) => {
      wx.getFileSystemManager().readFile({
        filePath: imagePath,
        encoding: 'base64',
        success: (res) => {
          resolve('data:image/jpeg;base64,' + res.data)
        },
        fail: reject
      })
    })
  },

  // 调用云函数
  callScanFunction(imageBase64) {
    return new Promise((resolve, reject) => {
      wx.cloud.callFunction({
        name: 'scan',
        data: {
          action: 'scan',
          data: {
            image: imageBase64,
            mode: this.data.filterOptions[this.data.filterIndex].value
          }
        },
        success: (res) => {
          if (res.errMsg === 'cloud.callFunction:ok') {
            resolve(res.result)
          } else {
            reject(new Error('云函数调用失败'))
          }
        },
        fail: reject
      })
    })
  },

  // 滤镜选择变化
  onFilterChange(e) {
    this.setData({
      filterIndex: e.detail.value
    })
  },

  // 跳转到结果页
  goToResult() {
    wx.navigateTo({
      url: '/pages/result/result'
    })
  },

  // 摄像头错误
  onCameraError(e) {
    console.error('摄像头错误:', e.detail)
    wx.showModal({
      title: '摄像头错误',
      content: '请检查摄像头权限设置',
      showCancel: false
    })
  },

  // 摄像头停止
  onCameraStop() {
    console.log('摄像头已停止')
  }
})
