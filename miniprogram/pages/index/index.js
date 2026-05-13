// pages/index/index.js
const app = getApp()

// 后端服务器地址
const SERVER_URL = 'https://document-scanner-api.onrender.com'

Page({
  data: {
    devicePosition: 'back',
    flashMode: 'auto',
    loading: false,
    loadingText: '处理中...',
    pages: [],
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
    this.setData({
      pages: app.globalData.pages || []
    })
  },

  onShow() {
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
      // 压缩图片
      const compressedPath = await this.compressImage(imagePath)

      // 转换为base64
      const base64 = await this.imageToBase64(compressedPath)

      // 直接调用后端API
      const result = await this.callScanAPI(base64)

      if (result.success) {
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

  // 压缩图片
  compressImage(imagePath) {
    return new Promise((resolve, reject) => {
      wx.compressImage({
        src: imagePath,
        quality: 70,
        success: (res) => resolve(res.tempFilePath),
        fail: () => resolve(imagePath) // 压缩失败就用原图
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

  // 直接调用后端API
  callScanAPI(imageBase64) {
    return new Promise((resolve, reject) => {
      wx.request({
        url: `${SERVER_URL}/api/scan`,
        method: 'POST',
        data: {
          image: imageBase64,
          mode: this.data.filterOptions[this.data.filterIndex].value
        },
        header: {
          'content-type': 'application/json'
        },
        timeout: 60000,
        success: (res) => {
          if (res.statusCode === 200) {
            resolve(res.data)
          } else {
            reject(new Error(`服务器错误: ${res.statusCode}`))
          }
        },
        fail: (err) => {
          console.error('请求失败:', err)
          reject(new Error('网络请求失败，请检查网络连接'))
        }
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
  }
})
