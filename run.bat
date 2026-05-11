@echo off
chcp 65001 > nul
echo ========================================
echo     文档扫描器 - 启动程序
echo ========================================
echo.
echo 请选择启动模式:
echo [1] 图形界面模式 (推荐)
echo [2] 命令行模式
echo [3] 安装依赖
echo [4] 退出
echo.
set /p choice=请输入选项 (1-4):

if "%choice%"=="1" goto gui
if "%choice%"=="2" goto cli
if "%choice%"=="3" goto install
if "%choice%"=="4" goto end

:gui
echo.
echo 正在启动图形界面...
cd src
python gui.py
goto end

:cli
echo.
echo 命令行模式使用说明:
echo   python src/cli.py 输入图片 -o 输出图片
echo   python src/cli.py 输入文件夹 -o 输出文件夹 --batch
echo.
set /p input=请输入图片路径:
set /p output=请输入输出路径:
python src/cli.py "%input%" -o "%output%" --show
goto end

:install
echo.
echo 正在安装依赖...
pip install -r requirements.txt
echo.
echo 安装完成！
pause
goto end

:end
