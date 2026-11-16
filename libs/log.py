import datetime
import os
import subprocess

log_file_path = "None"


def init():
    global log_file_path
    log_file_path = f"logs/{_get_time()}.log"
    _new_file(log_file_path)
    write(f"已初始化日志文件：{log_file_path}", 3)


def write(log_content, log_level):
    if log_file_path == "None":
        return
    if not os.path.exists(log_file_path):
        _new_file(log_file_path)
        write(f"原日志文件被删除，重新创建：{log_file_path}", 2)
    log_level_name = {0: "FATAL", 1: "ERROR", 2: "WARN", 3: "INFO", 4: "DEBUG"}.get(log_level, "UNKNOWN")
    write_content = f"[{log_level_name}] [{_get_time()}] {log_content}\n"
    try:
        with open(log_file_path, "a", encoding="utf-8") as file_content:
            file_content.write(write_content)
    except Exception as e:
        error(f"写入日志时发生错误：{e}")


def error(error_message):
    current_cwd = os.getcwd().replace("\\", "/")
    crash_report = ("cmd /c echo ========崩溃报告======== &"
                    "echo 程序在运行中出现错误，无法继续执行 &"
                    f"echo 当前时间：{_get_time()} &"
                    f"echo 工作目录：{current_cwd} &"
                    f"echo 日志文件：{log_file_path} &"
                    f"echo 错误信息：{error_message} &"
                    f"pause")
    subprocess.Popen(crash_report)
    os._exit(0)


def _get_time():
    return datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


def _new_file(file_path):
    try:
        os.makedirs("logs", exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("")
    except Exception as e:
        error(f"创建日志时发生错误：{e}")
