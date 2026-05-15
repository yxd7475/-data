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

  switchCamera() {
    this.setData({
      devicePosition: this.data.devicePosition === 'back' ? 'front' : 'back'
    })
  },

  chooseFromAlbum() {
    wx.chooseMedia({
      count: 1,
      mediaType: ['image'],
      sizeType: ['original'],  // 选择原图
      sourceType: ['album'],
      success: (res) => {
        const file = res.tempFiles[0]
        console.log('相册图片尺寸:', file.width, 'x', file.height, '大小:', file.size)
        // 获取更详细的图片信息
        wx.getImageInfo({
          src: file.tempFilePath,
          success: (info) => {
            console.log('相册图片详情:', info.width, 'x', info.height)
          }
        })
        this.processImage(file.tempFilePath)
      }
    })
  },

  takePhoto() {
    const ctx = wx.createCameraContext()
    this.setData({ loading: true, loadingText: '拍照中...' })

    ctx.takePhoto({
      quality: 'high',
      success: (res) => {
        console.log('拍照成功, 图片路径:', res.tempImagePath)
        // 获取图片信息
        wx.getImageInfo({
          src: res.tempImagePath,
          success: (info) => {
            console.log('原图尺寸:', info.width, 'x', info.height)
            // 如果图片太小，提示用户
            if (info.width < 2000) {
              console.warn('图片分辨率较低，可能影响扫描效果')
            }
          }
        })
        this.processImage(res.tempImagePath)
      },
      fail: (err) => {
        console.error('拍照失败:', err)
        wx.showToast({ title: '拍照失败', icon: 'error' })
        this.setData({ loading: false })
      }
    })
  },

  async processImage(imagePath) {
    this.setData({ loadingText: '正在扫描...' })

    try {
      // 不压缩，直接用原图
      const base64 = await this.imageToBase64(imagePath)

      console.log('图片base64长度:', base64.length)

      const result = await this.callScanAPI(base64)

      if (result.success) {
        // 打印调试信息
        if (result.debug) {
          console.log('调试信息:', result.debug)
        }

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

  callScanAPI(imageBase64) {
    return new Promise((resolve, reject) => {
      this.setData({ loadingText: '上传中...' })

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
        timeout: 120000,  // 2分钟超时
        success: (res) => {
          if (res.statusCode === 200) {
            resolve(res.data)
          } else {
            reject(new Error(`服务器错误: ${res.statusCode}`))
          }
        },
        fail: (err) => {
          console.error('请求失败:', err)
          reject(new Error('网络请求失败'))
        }
      })
    })
  },

  onFilterChange(e) {
    this.setData({ filterIndex: e.detail.value })
  },

  goToResult() {
    wx.navigateTo({ url: '/pages/result/result' })
  },

  onCameraError(e) {
    console.error('摄像头错误:', e.detail)
    wx.showModal({
      title: '摄像头错误',
      content: '请检查摄像头权限',
      showCancel: false
    })
  }
})
