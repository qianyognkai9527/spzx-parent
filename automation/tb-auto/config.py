"""配置文件"""

CDP_URL = "http://127.0.0.1:9222"
TARGET_URL = "https://ufuwu.1688.com/page/fuwu_work_isv_container.htm?appkey=2839818"

# 延时配置 (秒) - 下班放开干, 提速(滑块手动验证兜底)
MIN_DELAY = 6
MAX_DELAY = 10
BATCH_50_BREAK_MIN = 60       # 1分钟
BATCH_50_BREAK_MAX = 120      # 2分钟
BATCH_200_BREAK_MIN = 480     # 8分钟
BATCH_200_BREAK_MAX = 540     # 9分钟

# 批次大小(提效:更少次休息)
BATCH_50 = 120
BATCH_200 = 500

# 文件路径
PROGRESS_FILE = "progress.json"
LOG_FILE = "auto_list.log"

# 滑块验证检测 - 只检测真实可见的阿里云验证码元素
SLIDER_SELECTORS = [
    "#nc_1_wrapper",
    "#nc_1__scale_text",
    "#aliyunCaptcha-window",
    "#baxia-dialog-content",
    "#baxia-dialog",
    "#smcaptcha",
    "#nc_1_n1z",
]
