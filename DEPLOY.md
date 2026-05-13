# 部署文档扫描器到 Render

## 步骤一：创建 GitHub 仓库

1. 登录 GitHub，创建新仓库（如 `document-scanner-api`）
2. 将代码推送到 GitHub：

```bash
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/你的用户名/document-scanner-api.git
git push -u origin main
```

## 步骤二：注册 Render 账号

1. 访问 https://render.com
2. 点击 "Get Started" 注册账号
3. 选择 "Sign up with GitHub" 用 GitHub 账号登录

## 步骤三：创建 Web Service

1. 在 Render Dashboard 点击 "New +" 按钮
2. 选择 "Web Service"
3. 连接你的 GitHub 仓库
4. 填写配置：

| 配置项 | 值 |
|--------|-----|
| Name | document-scanner-api |
| Region | Oregon (US West) 或 Singapore |
| Branch | main |
| Root Directory | . (留空或填 .) |
| Runtime | Python 3 |
| Build Command | pip install -r requirements-server.txt |
| Start Command | gunicorn app_server:app --bind 0.0.0.0:$PORT --timeout 120 |

5. 选择 "Free" 计划
6. 点击 "Create Web Service"

## 步骤四：等待部署完成

- Render 会自动安装依赖并启动服务
- 大约需要 3-5 分钟
- 部署成功后会显示绿色的 "Live"

## 步骤五：获取 API 地址

部署成功后，你会得到一个类似这样的地址：
```
https://document-scanner-api-xxxx.onrender.com
```

## 步骤六：更新小程序配置

1. 打开 `miniprogram/cloudfunctions/scan/index.js`
2. 修改 `SERVER_URL` 为你的 Render 地址：

```javascript
const SERVER_URL = 'https://document-scanner-api-xxxx.onrender.com/api'
```

3. 重新上传云函数

## 步骤七：测试 API

测试扫描接口：
```bash
curl -X POST https://document-scanner-api-xxxx.onrender.com/api/scan \
  -H "Content-Type: application/json" \
  -d '{"image": "base64编码的图片", "mode": "scanner"}'
```

## 注意事项

1. **免费计划限制**：
   - 每月 750 小时免费
   - 服务在 15 分钟无请求后会休眠
   - 冷启动可能需要 30-60 秒

2. **超时设置**：
   - 免费版最长请求时间 100 秒
   - 大图片可能需要更长时间处理

3. **内存限制**：
   - 免费版 512MB 内存
   - 处理大图片可能内存不足

## 故障排查

查看日志：
1. 在 Render Dashboard 点击你的服务
2. 点击 "Logs" 标签
3. 查看实时日志输出

常见错误：
- `Memory limit exceeded`: 图片太大，需要压缩
- `Timeout`: 处理时间过长，需要优化或升级计划
- `Module not found`: 检查 requirements-server.txt 是否包含所有依赖
