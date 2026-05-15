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
      // 先获取图片信息，打印原始尺寸
      const imageInfo = await new Promise((resolve, reject) => {
        wx.getImageInfo({
          src: imagePath,
          success: resolve,
          fail: reject
        })
      })
      console.log('========== 图片信息 ==========')
      console.log('原始尺寸:', imageInfo.width, 'x', imageInfo.height)
      console.log('==============================')

      // 转换为base64
      const base64 = await this.imageToBase64(imagePath)
      console.log('base64长度:', base64.length)

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
      // 先获取图片信息
      wx.getImageInfo({
        src: imagePath,
        success: (info) => {
          console.log('========== 图片处理流程 ==========')
          console.log('第1步 - 原始图片尺寸:', info.width, 'x', info.height)
          console.log('第1步 - 图片路径:', imagePath)
        },
        fail: (err) => {
          console.error('获取图片信息失败:', err)
        }
      })

      // 读取文件
      wx.getFileSystemManager().readFile({
        filePath: imagePath,
        encoding: 'base64',
        success: (res) => {
          console.log('第2步 - base64长度:', res.data.length)
          console.log('第2步 - 预估图片大小:', Math.round(res.data.length * 0.75 / 1024), 'KB')
          const fullBase64 = 'data:image/jpeg;base64,' + res.data
          console.log('第2步 - 完整base64长度:', fullBase64.length)
          resolve(fullBase64)
        },
        fail: (err) => {
          console.error('读取文件失败:', err)
          reject(err)
        }
      })
    })
  },

  callScanAPI(imageBase64) {
    return new Promise((resolve, reject) => {
      this.setData({ loadingText: '上传中...' })

      console.log('第3步 - 发送到服务器, base64长度:', imageBase64.length)

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
        timeout: 180000,  // 3分钟超时
        success: (res) => {
          console.log('第4步 - 服务器响应状态码:', res.statusCode)
          if (res.data.debug) {
            console.log('第4步 - 服务器收到的尺寸:', res.data.debug.input_size)
            console.log('第4步 - 服务器输出的尺寸:', res.data.debug.output_size)
          }
          if (res.data.image) {
            console.log('第4步 - 返回图片base64长度:', res.data.image.length)
          }
          console.log('===================================')
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
