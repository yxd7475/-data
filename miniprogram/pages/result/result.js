// pages/result/result.js
const app = getApp()

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

  // 加载页面数据
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

  // 更新当前显示的图片
  updateCurrentImage() {
    const { pages, currentIndex } = this.data
    if (pages[currentIndex]) {
      this.setData({
        currentImage: pages[currentIndex].enhanced
      })
    }
  },

  // 选择页面
  selectPage(e) {
    const index = e.currentTarget.dataset.index
    this.setData({ currentIndex: index })
    this.updateCurrentImage()
  },

  // 滤镜变化
  async onFilterChange(e) {
    const newIndex = e.detail.value

    this.setData({ loading: true, loadingText: '应用滤镜...' })

    try {
      const { pages, currentIndex } = this.data
      const croppedImage = pages[currentIndex].cropped

      // 调用云函数应用滤镜
      const result = await this.callEnhanceFunction(croppedImage, this.data.filterOptions[newIndex].value)

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

  // 排序变化
  onOrderChange(e) {
    this.setData({ orderIndex: e.detail.value })
  },

  // 调用增强云函数
  callEnhanceFunction(imageBase64, mode) {
    return new Promise((resolve, reject) => {
      wx.cloud.callFunction({
        name: 'scan',
        data: {
          action: 'enhance',
          data: {
            image: imageBase64,
            mode: mode
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

  // 继续拍摄
  continueCapture() {
    wx.navigateBack()
  },

  // 重拍
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

  // 保存图片
  saveImage() {
    const { currentImage } = this.data

    // base64转临时文件
    const fs = wx.getFileSystemManager()
    const filePath = `${wx.env.USER_DATA_PATH}/scan_${Date.now()}.png`

    // 去掉base64前缀
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
            console.error('保存到相册失败:', err)
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
      fail: (err) => {
        console.error('写入文件失败:', err)
        wx.showToast({ title: '保存失败', icon: 'error' })
      }
    })
  },

  // 预览图片
  previewImage() {
    const { currentImage } = this.data
    wx.previewImage({
      current: currentImage,
      urls: [currentImage]
    })
  },

  // 导出PDF
  async exportPDF() {
    const { pages, orderIndex, orderOptions } = this.data

    if (pages.length === 0) {
      wx.showToast({ title: '没有可导出的页面', icon: 'none' })
      return
    }

    this.setData({ loading: true, loadingText: '生成PDF...' })

    try {
      // 准备页面数据
      let orderedPages = [...pages]
      if (orderOptions[orderIndex].value === 'desc') {
        orderedPages.reverse()
      }

      const pagesData = orderedPages.map(p => p.enhanced)

      // 调用云函数生成PDF
      const result = await this.callExportPDFFunction(pagesData)

      if (result.fileUrl) {
        // 下载PDF
        this.setData({ loadingText: '下载PDF...' })

        const downloadRes = await this.downloadFile(result.fileUrl)

        // 打开或分享
        wx.showActionSheet({
          itemList: ['打开PDF', '发送给朋友'],
          success: (res) => {
            if (res.tapIndex === 0) {
              this.openDocument(downloadRes.tempFilePath)
            } else if (res.tapIndex === 1) {
              this.shareFile(downloadRes.tempFilePath)
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

  // 调用导出PDF云函数
  callExportPDFFunction(pagesData) {
    return new Promise((resolve, reject) => {
      wx.cloud.callFunction({
        name: 'scan',
        data: {
          action: 'export-pdf',
          data: { pages: pagesData }
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

  // 下载文件
  downloadFile(url) {
    return new Promise((resolve, reject) => {
      wx.downloadFile({
        url,
        success: resolve,
        fail: reject
      })
    })
  },

  // 打开文档
  openDocument(filePath) {
    wx.openDocument({
      filePath,
      fileType: 'pdf',
      fail: (err) => {
        console.error('打开文档失败:', err)
        wx.showToast({ title: '打开失败', icon: 'error' })
      }
    })
  },

  // 分享文件
  shareFile(filePath) {
    wx.shareFileMessage({
      filePath,
      fileType: 'pdf',
      success: () => {
        wx.showToast({ title: '发送成功', icon: 'success' })
      },
      fail: (err) => {
        console.error('分享失败:', err)
        wx.showToast({ title: '发送失败', icon: 'error' })
      }
    })
  }
})
