// 云函数入口文件
const cloud = require('wx-server-sdk')

cloud.init({
  env: cloud.DYNAMIC_CURRENT_ENV
})

// 后端服务器地址
const SERVER_URL = 'https://document-scanner-api.onrender.com/api'

/**
 * 云函数入口函数
 * action: scan | enhance | export-pdf
 * data: 请求数据
 */
exports.main = async (event, context) => {
  const { action, data } = event

  console.log(`云函数调用: action=${action}`)

  try {
    let result

    switch (action) {
      case 'scan':
        result = await scanDocument(data)
        break
      case 'enhance':
        result = await enhanceDocument(data)
        break
      case 'export-pdf':
        result = await exportPDF(data)
        break
      default:
        throw new Error(`未知操作: ${action}`)
    }

    return result
  } catch (error) {
    console.error('云函数错误:', error)
    return {
      success: false,
      error: error.message
    }
  }
}

/**
 * 扫描文档
 */
async function scanDocument(data) {
  const response = await fetch(`${SERVER_URL}/scan`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(data)
  })

  const result = await response.json()
  return result
}

/**
 * 增强文档
 */
async function enhanceDocument(data) {
  const response = await fetch(`${SERVER_URL}/enhance`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(data)
  })

  const result = await response.json()
  return result
}

/**
 * 导出PDF
 */
async function exportPDF(data) {
  const response = await fetch(`${SERVER_URL}/export-pdf`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(data)
  })

  // 获取PDF文件
  const buffer = await response.arrayBuffer()

  // 上传到云存储
  const uploadResult = await cloud.uploadFile({
    cloudPath: `pdfs/scanned_${Date.now()}.pdf`,
    fileContent: Buffer.from(buffer)
  })

  // 获取临时访问链接
  const urlResult = await cloud.getTempFileURL({
    fileList: [uploadResult.fileID]
  })

  return {
    success: true,
    fileUrl: urlResult.fileList[0].tempFileURL
  }
}
