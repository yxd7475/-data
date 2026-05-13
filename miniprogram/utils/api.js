/**
 * API 工具函数
 */

const app = getApp()

/**
 * 调用云函数
 * @param {string} action - 操作类型: scan | enhance | export-pdf
 * @param {object} data - 请求数据
 * @returns {Promise} 返回结果
 */
function callCloudFunction(action, data) {
  return new Promise((resolve, reject) => {
    wx.cloud.callFunction({
      name: 'scan',
      data: {
        action,
        data
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
}

/**
 * 图片转base64
 * @param {string} imagePath - 图片路径
 * @returns {Promise<string>} base64字符串
 */
function imageToBase64(imagePath) {
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
}

/**
 * 压缩图片
 * @param {string} imagePath - 图片路径
 * @param {number} quality - 压缩质量 0-100
 * @returns {Promise<string>} 压缩后的图片路径
 */
function compressImage(imagePath, quality = 80) {
  return new Promise((resolve, reject) => {
    wx.compressImage({
      src: imagePath,
      quality,
      success: (res) => resolve(res.tempFilePath),
      fail: reject
    })
  })
}

/**
 * 显示加载
 * @param {string} title - 加载提示文字
 */
function showLoading(title = '处理中...') {
  wx.showLoading({
    title,
    mask: true
  })
}

/**
 * 隐藏加载
 */
function hideLoading() {
  wx.hideLoading()
}

/**
 * 显示错误提示
 * @param {string} message - 错误信息
 */
function showError(message) {
  wx.showToast({
    title: message,
    icon: 'error',
    duration: 2000
  })
}

/**
 * 显示成功提示
 * @param {string} message - 成功信息
 */
function showSuccess(message) {
  wx.showToast({
    title: message,
    icon: 'success',
    duration: 1500
  })
}

module.exports = {
  callCloudFunction,
  imageToBase64,
  compressImage,
  showLoading,
  hideLoading,
  showError,
  showSuccess
}
