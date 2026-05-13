// app.js
App({
  onLaunch() {
    // 初始化云开发
    if (!wx.cloud) {
      console.error('请使用 2.2.3 或以上的基础库以使用云能力')
    } else {
      wx.cloud.init({
        env: 'your-env-id', // 替换为你的云开发环境ID
        traceUser: true
      })
    }

    // 获取系统信息
    const systemInfo = wx.getSystemInfoSync()
    this.globalData.systemInfo = systemInfo
    this.globalData.statusBarHeight = systemInfo.statusBarHeight
    this.globalData.screenWidth = systemInfo.screenWidth
    this.globalData.screenHeight = systemInfo.screenHeight
  },

  globalData: {
    systemInfo: null,
    statusBarHeight: 0,
    screenWidth: 375,
    screenHeight: 667,
    // 后端服务器地址
    serverUrl: 'https://document-scanner-api.onrender.com/api',
    // 已扫描的页面
    pages: [],
    // 当前页面索引
    currentPageIndex: -1
  }
})
