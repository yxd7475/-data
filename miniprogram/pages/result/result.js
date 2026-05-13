// pages/result/result.js
const app = getApp()

// 后端服务器地址
const SERVER_URL = 'https://document-scanner-api.onrender.com'

Page({
  data: {
    pages: [],
    currentIndex: 0,
    currentImage: '',
    loading: false,
    loadingText: '处理中...',
    filterIndex: 0,
    filterOptions: [
      { value: 'scanner', label: '扫描仪效果' },
      { value: 'original', label: '原图' },
      { value: 'enhance', label: '增强对比度' },
      { value: 'bw', label: '黑白文档' },
      { value: 'magic_color', label: '魔法色彩' }
    ],
    orderIndex: 0,
    orderOptions: [
      { value: 'asc', label: '按拍摄顺序' },
      { value: 'desc', label: '按逆序' }
    ]
  },

  onLoad() {
    this.loadPages()
  },

  onShow() {
    this.loadPages()
  },

  loadPages() {
    const pages = app.globalData.pages || []
    const currentIndex = app.globalData.currentPageIndex || 0

    if (pages.length === 0) {
      wx.showToast({ title: '没有扫描结果', icon: 'none' })
      setTimeout(() => {
        wx.navigateBack()
      }, 1500)
      return
    }

    this.setData({
      pages,
      currentIndex: currentIndex >= 0 && currentIndex < pages.length ? currentIndex : 0
    })

    this.updateCurrentImage()
  },

  updateCurrentImage() {
    const { pages, currentIndex } = this.data
    if (pages[currentIndex]) {
      this.setData({
        currentImage: pages[currentIndex].enhanced
      })
    }
  },

  selectPage(e) {
    const index = e.currentTarget.dataset.index
    this.setData({ currentIndex: index })
    this.updateCurrentImage()
  },

  async onFilterChange(e) {
    const newIndex = e.detail.value
    this.setData({ loading: true, loadingText: '应用滤镜...' })

    try {
      const { pages, currentIndex } = this.data
      const croppedImage = pages[currentIndex].cropped

      const result = await this.callEnhanceAPI(croppedImage, this.data.filterOptions[newIndex].value)

      if (result.success) {
        pages[currentIndex].enhanced = result.image
        app.globalData.pages = pages

        this.setData({
          pages,
          filterIndex: newIndex,
          currentImage: result.image
        })
      }
    } catch (error) {
      console.error('滤镜应用失败:', error)
      wx.showToast({ title: '滤镜应用失败', icon: 'error' })
    } finally {
      this.setData({ loading: false })
    }
  },

  onOrderChange(e) {
    this.setData({ orderIndex: e.detail.value })
  },

  // 调用增强API
  callEnhanceAPI(imageBase64, mode) {
    return new Promise((resolve, reject) => {
      wx.request({
        url: `${SERVER_URL}/api/enhance`,
        method: 'POST',
        data: {
          image: imageBase64,
          mode: mode
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
        fail: reject
      })
    })
  },

  continueCapture() {
    wx.navigateBack()
  },

  retake() {
    const { currentIndex, pages } = this.data

    wx.showModal({
      title: '确认重拍',
      content: '确定要删除当前页面吗？',
      success: (res) => {
        if (res.confirm) {
          pages.splice(currentIndex, 1)
          app.globalData.pages = pages

          if (pages.length > 0) {
            const newIndex = Math.min(currentIndex, pages.length - 1)
            app.globalData.currentPageIndex = newIndex
            this.setData({ currentIndex: newIndex })
            this.loadPages()
          } else {
            app.globalData.currentPageIndex = -1
            wx.navigateBack()
          }
        }
      }
    })
  },

  saveImage() {
    const { currentImage } = this.data
    const fs = wx.getFileSystemManager()
    const filePath = `${wx.env.USER_DATA_PATH}/scan_${Date.now()}.png`
    const base64Data = currentImage.replace(/^data:image\/\w+;base64,/, '')

    fs.writeFile({
      filePath,
      data: base64Data,
      encoding: 'base64',
      success: () => {
        wx.saveImageToPhotosAlbum({
          filePath,
          success: () => {
            wx.showToast({ title: '保存成功', icon: 'success' })
          },
          fail: (err) => {
            if (err.errMsg.includes('auth deny')) {
              wx.showModal({
                title: '权限提示',
                content: '请在设置中允许访问相册',
                showCancel: false
              })
            }
          }
        })
      },
      fail: () => {
        wx.showToast({ title: '保存失败', icon: 'error' })
      }
    })
  },

  previewImage() {
    const { currentImage } = this.data
    wx.previewImage({
      current: currentImage,
      urls: [currentImage]
    })
  },

  async exportPDF() {
    const { pages, orderIndex, orderOptions } = this.data

    if (pages.length === 0) {
      wx.showToast({ title: '没有可导出的页面', icon: 'none' })
      return
    }

    this.setData({ loading: true, loadingText: '生成PDF...' })

    try {
      let orderedPages = [...pages]
      if (orderOptions[orderIndex].value === 'desc') {
        orderedPages.reverse()
      }

      const pagesData = orderedPages.map(p => p.enhanced)

      // 直接下载PDF
      const result = await this.downloadPDF(pagesData)

      if (result.tempFilePath) {
        wx.showActionSheet({
          itemList: ['打开PDF', '保存到相册'],
          success: (res) => {
            if (res.tapIndex === 0) {
              wx.openDocument({
                filePath: result.tempFilePath,
                fileType: 'pdf',
                fail: () => {
                  wx.showToast({ title: '打开失败', icon: 'error' })
                }
              })
            } else if (res.tapIndex === 1) {
              wx.saveFile({
                tempFilePath: result.tempFilePath,
                success: () => {
                  wx.showToast({ title: '已保存', icon: 'success' })
                }
              })
            }
          }
        })
      }
    } catch (error) {
      console.error('导出PDF失败:', error)
      wx.showToast({ title: '导出失败', icon: 'error' })
    } finally {
      this.setData({ loading: false })
    }
  },

  // 下载PDF
  downloadPDF(pagesData) {
    return new Promise((resolve, reject) => {
      // 先用request获取PDF数据
      wx.request({
        url: `${SERVER_URL}/api/export-pdf`,
        method: 'POST',
        data: { pages: pagesData },
        header: {
          'content-type': 'application/json'
        },
        responseType: 'arraybuffer',
        timeout: 120000,
        success: (res) => {
          if (res.statusCode === 200) {
            // 保存为临时文件
            const fs = wx.getFileSystemManager()
            const tempPath = `${wx.env.USER_DATA_PATH}/scan_${Date.now()}.pdf`

            fs.writeFile({
              filePath: tempPath,
              data: res.data,
              encoding: 'binary',
              success: () => {
                resolve({ tempFilePath: tempPath })
              },
              fail: reject
            })
          } else {
            reject(new Error(`服务器错误: ${res.statusCode}`))
          }
        },
        fail: reject
      })
    })
  }
})
