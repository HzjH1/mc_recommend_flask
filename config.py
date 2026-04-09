import os

# 是否开启debug模式
DEBUG = os.environ.get("DEBUG", "true").lower() == "true"

# 读取数据库环境变量
username = os.environ.get("MYSQL_USERNAME", 'root')
password = os.environ.get("MYSQL_PASSWORD", 'root')
db_address = os.environ.get("MYSQL_ADDRESS", '127.0.0.1:3306')

# AI 模型配置
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "sk-a3933f52b50d4629b9df0dfd3a99e133")
OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "qwen-plus-3.6")
OPENAI_TIMEOUT_SECONDS = int(os.environ.get("OPENAI_TIMEOUT_SECONDS", "15"))
OPENAI_TEMPERATURE = float(os.environ.get("OPENAI_TEMPERATURE", "0.2"))

# 内部任务配置
INTERNAL_JOB_TOKEN = os.environ.get("INTERNAL_JOB_TOKEN", "")
AUTO_ORDER_CUTOFF_LUNCH = os.environ.get("AUTO_ORDER_CUTOFF_LUNCH", "11:00")
AUTO_ORDER_CUTOFF_DINNER = os.environ.get("AUTO_ORDER_CUTOFF_DINNER", "17:00")
