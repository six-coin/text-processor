import datetime
import importlib
import sys

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QWidget, QPushButton, QLabel,
                             QTextEdit, QSplitter, QScrollArea, QDialog, QSizePolicy)

from libs import dialogs
from libs import file
from libs import log
from libs import project_log
from libs import validate_id


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        # 设置窗口标题、大小、居中显示
        self.setWindowTitle("文本处理器")
        self.resize(1400, 700)
        screen = QApplication.primaryScreen().availableGeometry()
        self.move((screen.width() - self.width()) // 2, (screen.height() - self.height()) // 2)

        # 一些运行中必要的变量
        # 当前打开的项目的字典：{"project_id", "project_name", "project_creation_time", "project_path"}
        self.current_project = None
        # 当前打开的文件的路径
        self.current_file_path = None
        # 当前打开的文件的文件名
        self.current_file_name = ""
        # 从项目 ID 映射到项目的字典
        self.projects = {}
        # 所有项目 ID
        self.project_ids = []
        # 从处理器 ID 映射到处理器模块
        self.processor_modules = {}
        # 所有处理器的 init 字典
        self.processors = []

        # 确保所有所需路径存在
        file.make_dir("projects")
        file.make_dir("processors")

        # 加载处理器
        for filename in file.list_dir("processors"):
            if filename.endswith(".py"):
                module_name = filename[:-3]
                try:
                    module = importlib.import_module(f"processors.{module_name}")
                    init_dict = module.init()
                    required_keys = {
                        "processor_id",
                        "processor_type",
                        "processor_name",
                        "processor_desc",
                        "processor_args"
                    }
                    if all(key in init_dict for key in required_keys):
                        processor_id = init_dict["processor_id"]
                        processor_type = init_dict["processor_type"]
                        processor_name = init_dict["processor_name"]
                        processor_desc = init_dict["processor_desc"]
                        processor_args = init_dict["processor_args"]
                        if not processor_type in ["file", "line", "check"]:
                            raise Exception("processor_type 不被支持")
                        if not validate_id.validate_id(processor_id):
                            raise Exception("processor_id 不符合命名规范")
                        if not module_name == processor_id:
                            raise Exception("processor_id 与文件名不匹配")
                        self.processors.append({
                            "processor_id": processor_id,
                            "processor_type": processor_type,
                            "processor_name": processor_name,
                            "processor_desc": processor_desc,
                            "processor_args": processor_args
                        })
                        self.processor_modules[processor_id] = module
                        log.write(f"成功加载处理器：{processor_name}（{processor_id}）", 3)
                    else:
                        raise Exception("init 函数没有返回全部需要的键值对")
                except Exception as e:
                    log.write(f"加载处理器 {filename} 失败，已跳过：{e}", 2)

        # 加载所有项目
        self.reload_projects()

        # 初始化 UI
        self.switch_btn = None
        self.info_label = None
        self.text_edit = None
        self.init_ui()

    def init_ui(self):
        # 上侧 - 工具栏
        toolbar = QWidget()
        toolbar_layout = QHBoxLayout(toolbar)

        project_btn = QPushButton("项目管理")
        project_btn.clicked.connect(self.show_project_management)

        switch_btn = QPushButton("切换文件")
        switch_btn.setEnabled(False)
        switch_btn.clicked.connect(self.show_switch_file)

        toolbar_layout.addWidget(project_btn)
        toolbar_layout.addWidget(switch_btn)
        toolbar_layout.addStretch()

        toolbar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        # 下侧 - 左侧
        info_label = QLabel("当前项目：未打开")
        info_label.setStyleSheet("font-weight: bold; padding: 5px;")

        text_edit = QTextEdit()
        text_edit.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        text_edit.setAcceptRichText(False)
        text_edit.setReadOnly(True)

        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.addWidget(info_label)
        left_layout.addWidget(text_edit)

        # 下侧 - 右侧
        processor_label = QLabel("可用操作")
        processor_label.setStyleSheet("font-weight: bold; padding: 5px;")

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll.setWidget(scroll_content)

        processor_layout = QVBoxLayout(scroll_content)
        manual_btn = QPushButton("手动修改文件")
        manual_btn.clicked.connect(self.manual_edit)
        processor_layout.addWidget(manual_btn)
        processor_layout.addWidget(QLabel("<hr>"))
        for processor in self.processors:
            btn = QPushButton(processor["processor_name"])
            btn.clicked.connect(lambda checked, p=processor: self.apply_processor(p))
            processor_layout.addWidget(btn)
        processor_layout.addStretch()

        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.addWidget(processor_label)
        right_layout.addWidget(scroll)

        # 下侧 - 整体
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setSizes([1100, 300])

        # 中央部件
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.addWidget(toolbar)
        main_layout.addWidget(splitter)

        # 赋值声明的属性
        self.switch_btn = switch_btn
        self.info_label = info_label
        self.text_edit = text_edit

    @staticmethod
    def get_version(filename):
        """提取文件名中的版本号"""
        if "_" in filename:
            a, _ = filename.split("_", maxsplit=1)
            try:
                return int(a)
            except ValueError:
                return -1
        else:
            return -1

    def get_file_names(self, project_history_path):
        """获取当前项目下的所有文件名"""
        file_names = []
        for file_name in file.list_dir(project_history_path):
            if file_name.endswith(".txt"):
                file_names.append(file_name)
        file_names.sort(key=self.get_version)
        return file_names

    def update_info_label(self):
        """更新主界面的标签"""
        project_id = self.current_project["project_id"]
        project_name = self.current_project["project_name"]
        text = f"当前项目：{project_name}（{project_id}） 查看文件：{self.current_file_name}"
        self.info_label.setText(text)

    def update_project_last_modify(self):
        """更新当前项目的最后更新时间"""
        project_id = self.current_project["project_id"]
        project_name = self.current_project["project_name"]
        project_creation_time = self.current_project["project_creation_time"]
        project_path = self.current_project["project_path"]
        project_info_path = f"{project_path}/project_info.txt"

        now_str = datetime.datetime.now().strftime("%Y/%m/%d %H:%M")
        file.new_file(
            project_info_path,
            f"project_id={project_id}\n"
            f"project_name={project_name}\n"
            f"project_creation_time={project_creation_time}\n"
            f"project_last_modify={now_str}\n"
        )

    def save_new_version(self, new_file_text, processor_name, params_str):
        """保存新版本的文件"""
        project_id = self.current_project["project_id"]
        project_path = self.current_project["project_path"]
        project_history_path = f"{project_path}/history"

        file_names = self.get_file_names(project_history_path)
        latest_file = file_names[-1]
        latest_file_version = self.get_version(latest_file)
        new_file_version = latest_file_version + 1
        new_file_name = f"{new_file_version}_{processor_name}.txt"
        new_file_path = f"{project_path}/history/{new_file_name}"

        file.new_file(new_file_path, new_file_text)

        self.current_file_path = new_file_path
        self.current_file_name = new_file_name
        self.text_edit.setPlainText(new_file_text)
        self.update_info_label()
        self.update_project_last_modify()

        project_log.write(f"已写入文件：{new_file_name}，操作：{processor_name}，参数：{params_str}", project_id, 3)

    def manual_edit(self):
        """执行手动修改处理器"""
        if not self.current_project:
            dialogs.MessageDialog("警告", "请先打开一个项目", self).exec()
            return

        project_id = self.current_project["project_id"]

        current_text = self.text_edit.toPlainText()
        dialog = dialogs.TextEditorDialog("手动修改", current_text, project_id=project_id, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_text = dialog.get_text()
            if new_text != current_text:
                self.save_new_version(new_text, "manual_change", "无")
            else:
                dialogs.MessageDialog("警告", "内容无变化，操作已取消", self).exec()

        # 外部编辑模式下删除临时文件
        if dialog.external_mode:
            try:
                file.delete(dialog.temp_file_path)
            except Exception as e:
                project_log.write(f"删除临时手动编辑文件失败：{e}", project_id, 2)

    def apply_processor(self, processor_dict):
        """执行自定义处理器"""
        # TODO：查看上下文内容
        # TODO：check的标记本行
        # TODO：加一个总共的
        if not self.current_project:
            dialogs.MessageDialog("警告", "请先打开一个项目", self).exec()
            return

        processor_name = processor_dict["processor_name"]
        processor_type = processor_dict["processor_type"]
        processor_id = processor_dict["processor_id"]
        processor_desc = processor_dict["processor_desc"]
        processor_args = processor_dict["processor_args"]

        is_line = processor_dict["processor_type"] == "line"
        param_dialog = dialogs.ProcessorParamDialog(processor_name, processor_desc, processor_args, is_line, self)
        if param_dialog.exec() != QDialog.DialogCode.Accepted:
            return
        params = param_dialog.get_params()
        if isinstance(params, str):  # 如果返回的是字符串则该字符串是参数具体错误信息
            dialogs.MessageDialog("警告", f"操作已取消：{params}", self).exec()
            return

        old_text = self.text_edit.toPlainText()
        processor_module = self.processor_modules[processor_id]
        processor_func = processor_module.processor
        is_compare = param_dialog.is_compare

        try:
            if processor_type == "line":
                old_lines = old_text.splitlines()
                new_lines = [processor_func(old_line, **params) for old_line in old_lines]

                if is_compare and old_lines != new_lines:
                    confirm_dialog = dialogs.LineConfirmDialog(old_lines, new_lines, self)
                    if confirm_dialog.exec() != QDialog.DialogCode.Accepted or confirm_dialog.result == "cancel_all":
                        dialogs.MessageDialog("提示", "本次操作已取消", self).exec()
                        return
                    else:
                        new_lines = confirm_dialog.modified_new_lines

                new_text = "\n".join(new_lines)
            elif processor_type == "file":
                new_text = processor_func(old_text, **params)
            elif processor_type == "check":
                old_lines = old_text.splitlines()
                new_lines = old_lines
                if_check = [processor_func(old_line, **params) for old_line in old_lines]

                if any(condition for condition in if_check):
                    check_dialog = dialogs.LineCheckDialog(old_lines, if_check, self)
                    if check_dialog.exec() != QDialog.DialogCode.Accepted or check_dialog.result == "cancel_all":
                        dialogs.MessageDialog("提示", "本次操作已取消", self).exec()
                        return
                    else:
                        new_lines = check_dialog.new_lines

                new_text = "\n".join(new_lines)
            else:
                raise ValueError("未知的 processor_type")
        except Exception as e:
            dialogs.MessageDialog("警告", f"本次操作执行失败：{e}", self).exec()
            return

        if new_text == old_text:
            dialogs.MessageDialog("提示", f"本次操作已被取消，因为文件未被修改", self).exec()
            return

        self.save_new_version(new_text, processor_id, str(params))

    def open_project(self, project_id):
        """执行打开项目"""
        project = self.projects[project_id]
        self.current_project = project
        project_name = project["project_name"]
        project_path = project["project_path"]
        project_history_path = f"{project_path}/history"
        project_temp_path = f"{project_path}/temp"
        project_origin_file_path = f"{project_path}/history/1_origin_file.txt"

        file.make_dir(project_path)
        file.make_dir(project_history_path)
        file.make_dir(project_temp_path)

        file_names = self.get_file_names(project_history_path)
        if not "1_origin_file.txt" in file_names:
            file.new_file(project_origin_file_path, "Default Content")
            file_names.append("1_origin_file.txt")
            file_names.sort(key=self.get_version)
        latest_file = file_names[-1]

        self.current_file_path = f"{project_path}/history/{latest_file}"
        self.current_file_name = latest_file
        content = file.read_file(self.current_file_path)
        self.text_edit.setPlainText(content)

        self.setWindowTitle(f"文本处理器 - {project_name}")
        self.switch_btn.setEnabled(True)
        self.update_info_label()

        project_log.write(f"已打开项目：{project_name}（{project_id}）", project_id, 3)

    def delete_project(self, project_id):
        """执行删除项目"""
        if self.current_project:
            if project_id == self.current_project["project_id"]:
                dialogs.MessageDialog("提示", f"不能删除当前打开的项目", self).exec()
                return

        project = self.projects[project_id]
        project_id = project["project_id"]
        project_name = project["project_name"]
        project_path = project["project_path"]

        recycle_dir = "projects/_recycle"
        file.make_dir(recycle_dir)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        new_location = f"{recycle_dir}/{project_id}_{timestamp}"

        dialog_code = dialogs.ConfirmDialog(
            f"删除项目 {project_name}",
            "这将会把该项目移动至回收站\n"
            f"项目名称：{project_name}\n"
            f"项目 ID：{project_id}\n"
            f"删除后，项目会被移动至：\n"
            f"{new_location}",
            self
        ).exec()
        if not dialog_code == QDialog.DialogCode.Accepted:
            return

        try:
            file.move(project_path, new_location)
            dialogs.MessageDialog("提示", f"项目删除完成，已移至\n{new_location}", self).exec()
            log.write(f"已删除项目：{project_name}（{project_id}），新位置：{new_location}", 3)
        except Exception as e:
            dialogs.MessageDialog("警告", f"删除失败：{e}", self).exec()
            log.write(f"删除项目失败：{project_name}（{project_id}）", 1)

    def new_project(self, project_info):
        """执行新建项目"""
        project_id = project_info["project_id"]
        project_name = project_info["project_name"]
        project_path = f"projects/{project_id}"
        project_info_path = f"{project_path}/project_info.txt"
        project_log_path = f"{project_path}/project_log.log"
        project_history_path = f"{project_path}/history"
        project_temp_path = f"{project_path}/temp"
        project_origin_file_path = f"{project_path}/history/1_origin_file.txt"
        initial_text = project_info["initial_text"]

        file.make_dir(project_path)
        file.make_dir(project_history_path)
        file.make_dir(project_temp_path)

        now_str = datetime.datetime.now().strftime("%Y/%m/%d %H:%M")
        file.new_file(
            project_info_path,
            f"project_id={project_id}\n"
            f"project_name={project_name}\n"
            f"project_creation_time={now_str}\n"
            f"project_last_modify={now_str}\n"
        )
        file.new_file(project_log_path)
        file.new_file(project_origin_file_path, initial_text)

        project_log.write(f"项目创建：{project_name}（{project_id}）", project_id, 3)
        project_log.write(f"已写入文件：{project_origin_file_path}，项目初始化", project_id, 3)

        self.reload_projects()
        self.open_project(project_id)

    def reload_projects(self):
        """重新加载项目文件夹中的所有项目"""
        self.projects = {}
        self.project_ids = []
        for project_id in file.list_dir("projects"):
            try:
                if project_id == "_recycle":
                    continue
                if not validate_id.validate_id(project_id):
                    raise Exception("项目 ID 不符合命名规范")
                project_path = f"projects/{project_id}"
                info_path = f"projects/{project_id}/project_info.txt"
                if not file.is_dir(project_path):
                    raise Exception("该项目不是文件夹")
                if file.exists(info_path):
                    try:
                        info_file_content = file.read_file(info_path)
                        info = {}
                        for line in info_file_content.split("\n"):
                            if "=" in line:
                                key, value = line.strip().split("=", 1)
                                info[key] = value
                        required_keys = {"project_id", "project_name", "project_creation_time"}
                        if all(k in info for k in required_keys):
                            if not project_id == info.get("project_id"):
                                raise Exception("项目文件夹名与项目 ID 不一致")
                            self.project_ids.append(info.get("project_id"))
                            self.projects[info.get("project_id")] = {
                                "project_id": info.get("project_id"),
                                "project_name": info.get("project_name"),
                                "project_creation_time": info.get("project_creation_time"),
                                "project_path": project_path
                            }
                        else:
                            raise Exception("没有读取到全部需要的键值对")
                    except Exception as e:
                        raise Exception(f"读取 project_info.txt 时发生错误：{e}")
                else:
                    raise Exception("该项目中没有 project_info.txt")
            except Exception as e:
                log.write(f"读取项目 {project_id} 失败：{e}", 2)

    def show_project_management(self):
        """执行项目管理"""
        self.reload_projects()
        dialog = dialogs.ProjectManagement(self.project_ids, self.projects, self)
        dialog.open_requested.connect(self.open_project)
        dialog.delete_requested.connect(self.delete_project)
        dialog.new_requested.connect(self.new_project)
        dialog.exec()

    def show_switch_file(self):
        """执行文件选择"""
        project_id = self.current_project["project_id"]
        project_name = self.current_project["project_name"]
        project_path = self.current_project["project_path"]
        project_history_path = f"{project_path}/history"
        file_names = self.get_file_names(project_history_path)

        # 弹出选择文件对话框
        dialog = dialogs.SwitchFile(project_id, project_name, file_names, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            sel_file_name = dialog.selected_file
            sel_file_path = f"{project_history_path}/{sel_file_name}"
            sel_file_content = file.read_file(sel_file_path)
            sel_file_version = self.get_version(sel_file_name)

            # 删除在选取文件版本之后的文件
            for file_name in file.list_dir(project_history_path):
                if file_name.endswith(".txt") and self.get_version(file_name) > sel_file_version:
                    del_path = f"{project_history_path}/{file_name}"
                    try:
                        file.delete(del_path)
                        project_log.write(f"已删除文件：{file_name}（切换至 {sel_file_name}）", project_id, 3)
                    except Exception as e:
                        project_log.write(f"删除文件失败：{file_name}：{e}（切换至 {sel_file_name}）", project_id, 2)
                        pass

            self.current_file_path = sel_file_path
            self.current_file_name = sel_file_name
            self.text_edit.setPlainText(sel_file_content)
            self.update_info_label()

            project_log.write(f"已切换文件：{sel_file_name}", project_id, 3)


def main():
    log.init()

    try:
        # 创建 app
        app = QApplication(sys.argv)
        window = MainWindow()
        window.show()
        log.write("程序完成初始化", 3)

        # 运行程序
        sys.exit(app.exec())
    except Exception as e:
        log.write(f"程序运行中出现未知错误：{e}", 0)


if __name__ == "__main__":
    main()
