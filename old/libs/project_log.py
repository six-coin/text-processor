import datetime

from libs import file
from libs import log

log_level_dict = {0: "FATAL", 1: "ERROR", 2: "WARN", 3: "INFO", 4: "DEBUG"}


def write(log_content, project_id, log_level):
    # 写入总日志
    main_log_content = f"{project_id}：{log_content}"
    log.write(main_log_content, log_level)

    # 写入项目日志
    log_level_name = log_level_dict.get(log_level, "UNKNOWN")
    log_path = f"projects/{project_id}/project_log.log"
    log_time = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S_%f")
    project_log_content = f"[{log_level_name}] [{log_time}] {log_content}\n"
    file.add_file(log_path, project_log_content)
