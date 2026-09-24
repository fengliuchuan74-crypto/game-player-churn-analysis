# 游戏玩家流失风险分析工具

一个在本机运行的 Streamlit 应用。上传玩家行为数据后，完成字段映射、数据清洗、风险分层、驱动因素分析、图表展示和 HTML 报告导出。

当前版本使用确定性规则评分，没有接入大模型 API，也没有经过训练和校准的机器学习预测模型。页面中的“流失概率”来自规则换算，应理解为风险排序参考，不能直接作为真实流失概率、召回收益或实际流失人数的预测。用于业务决策前，需要用项目自己的历史结果验证阈值和效果。

## 功能

- 上传 CSV、XLSX 或 XLS 文件，自动识别常见中英文字段，并允许手动映射。
- 清理空白记录、重复记录和异常数值，展示清洗情况及分析假设。
- 按近期登录、活跃间隔、付费、等级、失败次数和社交互动计算规则风险。
- 展示高、中、低风险分层、主要驱动因素、典型样本及分层处理建议。
- 预览、下载 HTML 报告，或保存为带递增版本号的本地报告。

## 输入数据

每行对应一名玩家。推荐使用以下字段；原始字段名不同也可以在界面中映射。缺失字段的处理假设会影响分析结果，应在分析前核查。

| 推荐字段 | 含义 |
| --- | --- |
| `user_id` | 玩家或角色标识 |
| `login_days_7d` | 近 7 日登录天数 |
| `last_active_days` | 距上次活跃天数，也支持识别日期类型字段 |
| `payment_amount_30d` | 近 30 日付费金额，需在同一数据集中统一币种 |
| `level` | 当前等级 |
| `fail_count_3d` | 近 3 日失败次数 |
| `social_interactions_7d` | 近 7 日社交互动次数 |

仓库不包含玩家数据、既有报告、Python 运行时或打包后的 EXE。无需数据文件即可启动应用；打开后上传自己的数据开始分析。CSV 建议采用 UTF-8 编码。

## 安装与启动

推荐 Windows 与 Python 3.12。首次安装依赖需要联网；安装后，规则分析和 HTML 报告生成在本机运行，无需模型密钥。

双击 `安装依赖.bat`：脚本查找标准 Python 3.12，在项目中创建 `.venv` 并安装依赖。随后双击 `启动流失分析应用.bat`。启动脚本优先使用项目 `.venv`，也可使用已安装依赖的标准 Python 环境，不依赖某台电脑的桌面路径。

也可以在项目目录使用 PowerShell：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe launcher.py
```

启动器在 `127.0.0.1` 的 8501—8530 端口间寻找空闲端口，并自动打开浏览器。已有其他 Streamlit 工具运行时会选择其他可用端口。在终端按 `Ctrl+C` 停止服务。

需要指定端口时：

```powershell
.\.venv\Scripts\python.exe -m streamlit run streamlit_app.py --server.address 127.0.0.1 --server.port 8502 --browser.gatherUsageStats false
```

`requirements.txt` 包含 CSV/Excel 读取所需的 `pandas`、`openpyxl` 与 `xlrd`。依赖清单目前使用最低版本约束，没有提供完整锁定文件。

## 报告与数据保存

上传内容在当前应用会话中进行分析，应用没有自动导入数据库的功能。HTML 报告含统计结果及选中的玩家样本，导出前应确认可分享范围。

侧栏可指定报告输出目录，默认是项目目录；点击本地保存时自动创建下一份 `user_churn_analysis_report_版本N.html`。下载报告也可以直接通过浏览器保存。关闭会话后如需继续分析，应重新上传原始文件。

`.gitignore` 排除玩家数据表、生成报告、日志、凭证、虚拟环境及构建产物。请继续将真实数据和报告保存在本地；仓库中的源码无需这些文件即可运行。

## 可选：打包 Windows EXE

完成依赖安装后双击 `build_exe.bat`。该脚本安装 `requirements-build.txt` 中的 PyInstaller，再使用 `churn-analysis-app.spec` 打包。也可以执行：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.\.venv\Scripts\python.exe -m PyInstaller churn-analysis-app.spec
```

生成文件为 `dist/churn-analysis-app.exe`，可以通过 `启动流失分析EXE.bat` 打开。打包脚本不会关闭其他应用或删除已有 EXE；如果目标 EXE 已存在，需先自行关闭并移动或重命名旧文件。构建产物不纳入源代码仓库。本次整理未重新构建或验收 EXE。

## 项目结构与限制

| 文件 | 用途 |
| --- | --- |
| `streamlit_app.py` | 页面、数据清洗、规则分析与 HTML 报告 |
| `launcher.py` | 本机端口选择与启动 |
| `requirements.txt` | 运行依赖 |
| `requirements-build.txt` | 可选打包依赖 |
| `.streamlit/config.toml` | Streamlit 配置 |
| `churn-analysis-app.spec` | PyInstaller 打包配置 |

目前适合单机上传文件与演示分析；没有多用户权限、后台任务队列、定时数据接入、模型训练或效果回流。风险阈值、数据字段口径与建议需要结合游戏阶段、玩家分层和实际运营目标调整。大量文件会整体读入内存，尚未经过大规模数据性能验收。
