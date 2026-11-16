from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QTextEdit, QListWidget, QListWidgetItem,
                             QDialog, QLineEdit, QFormLayout, QCheckBox)

from libs import check_different
from libs import file
from libs import project_log
from libs import validate_id


class MessageDialog(QDialog):
    def __init__(self, title, message, parent=None):
        super().__init__(parent)

        self.setWindowTitle(f"文本处理器 - {title}")
        self.resize(300, 1)

        title_label = QLabel("提示信息")
        title_label.setStyleSheet("font-weight: bold;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        message_label = QLabel(message)
        message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        message_label.setWordWrap(True)

        complete_btn = QPushButton("完成")
        complete_btn.clicked.connect(self.accept)
        complete_btn.setDefault(True)
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(complete_btn)

        layout = QVBoxLayout(self)
        layout.addWidget(title_label)
        layout.addSpacing(4)
        layout.addWidget(message_label)
        layout.addSpacing(4)
        layout.addLayout(btn_layout)
        layout.addStretch()


class ConfirmDialog(QDialog):
    def __init__(self, title, message, parent=None):
        super().__init__(parent)

        self.setWindowTitle(f"文本处理器 - {title}")
        self.resize(300, 1)

        title_label = QLabel("提示信息")
        title_label.setStyleSheet("font-weight: bold;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        message_label = QLabel(message)
        message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        message_label.setWordWrap(True)

        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        confirm_btn = QPushButton("确认")
        confirm_btn.clicked.connect(self.accept)
        confirm_btn.setDefault(True)
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(confirm_btn)

        layout = QVBoxLayout(self)
        layout.addWidget(title_label)
        layout.addSpacing(4)
        layout.addWidget(message_label)
        layout.addSpacing(4)
        layout.addLayout(btn_layout)
        layout.addStretch()


class TextEditorDialog(QDialog):
    def __init__(self, title, initial_text="", project_id=None, is_read_only=False, parent=None):
        super().__init__(parent)

        # 设置窗口标题、大小
        self.setWindowTitle(f"文本处理器 - {title}")
        self.resize(900, 600)

        # 运行所需变量
        self.project_id = project_id
        self.external_mode = False
        self.temp_file_path = None

        # 初始化 UI
        text_edit = QTextEdit()
        text_edit.setPlainText(initial_text)
        text_edit.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        if is_read_only:
            text_edit.setReadOnly(True)
        self.text_edit = text_edit

        btn_layout = QHBoxLayout()
        if project_id is not None:  # 仅在有 project_id（即手动修改的场景）时显示外部编辑按钮
            external_btn = QPushButton("使用外部编辑器编辑")
            external_btn.clicked.connect(self.external_edit)
            btn_layout.addWidget(external_btn)
            self.external_btn = external_btn
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        complete_btn = QPushButton("完成")
        complete_btn.clicked.connect(self.accept)
        complete_btn.setDefault(True)
        btn_layout.addStretch()
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(complete_btn)

        layout = QVBoxLayout(self)
        layout.addWidget(text_edit)
        layout.addLayout(btn_layout)

    def external_edit(self):
        self.external_mode = True
        self.external_btn.setEnabled(False)

        temp_file_path = f"projects/{self.project_id}/temp/manual_edit.txt"
        file.new_file(temp_file_path, self.text_edit.toPlainText())
        self.temp_file_path = temp_file_path

        try:
            self.text_edit.setReadOnly(True)
            self.text_edit.setPlainText(
                f"正在 {temp_file_path} 中修改文档。\n"
                f"点击“完成”按钮后将以该文件中的内容作为手动修改结果。"
            )
            file.open_file(temp_file_path)
        except Exception as e:
            project_log.write(f"外部编辑器打开失败：{e}", self.project_id, 2)

    def get_text(self):
        if self.external_mode:
            try:
                return file.read_file(self.temp_file_path)
            except Exception as e:
                return f"外部编辑文件读取失败：{e}"
        else:
            return self.text_edit.toPlainText()


class ProcessorParamDialog(QDialog):
    def __init__(self, processor_name, processor_desc, processor_args, is_line, parent=None):
        super().__init__(parent)

        # 设置窗口标题、大小
        self.setWindowTitle(f"文本处理器 - {processor_name}")
        self.resize(500, 1)

        # 运行所需变量
        self.inputs = {}
        self.is_compare = False

        # 初始化 UI
        # 基本信息
        name_label = QLabel(processor_name)
        name_label.setStyleSheet("font-weight: bold;")
        name_label.setWordWrap(True)
        desc_label = QLabel(processor_desc)
        desc_label.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.addWidget(name_label)
        layout.addWidget(desc_label)
        layout.addSpacing(12)

        # 参数输入
        for arg_id, arg_info in processor_args.items():
            arg_name = arg_info["name"]
            arg_description = arg_info["description"]
            arg_type = arg_info["type"]
            arg_default = arg_info["default"]

            arg_name_label = QLabel(f"{arg_name}（{arg_id}）")
            arg_name_label.setStyleSheet("font-weight: bold;")
            arg_name_label.setWordWrap(True)
            arg_desc_label = QLabel(arg_description)
            arg_desc_label.setWordWrap(True)
            input_area = QLineEdit()
            input_area.setPlaceholderText(arg_default)

            self.inputs[arg_id] = (input_area, arg_type, arg_default)

            layout.addWidget(arg_name_label)
            layout.addWidget(arg_desc_label)
            layout.addWidget(input_area)
            layout.addSpacing(12)

        # 对比修改的行并手动决定复选框
        if is_line:
            compare_checkbox = QCheckBox("对比修改的行并手动决定")
            compare_checkbox.checkStateChanged.connect(self.update_checkbox)
            self.compare_checkbox = compare_checkbox
            layout.addWidget(compare_checkbox)
            layout.addSpacing(12)

        # 下侧按钮
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        complete_btn = QPushButton("完成")
        complete_btn.clicked.connect(self.accept)
        complete_btn.setDefault(True)
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(complete_btn)

        layout.addLayout(btn_layout)
        layout.addStretch()

    def update_checkbox(self):
        self.is_compare = self.compare_checkbox.isChecked()

    def get_params(self):
        params = {}
        for arg_id, (input_area, arg_type, arg_default) in self.inputs.items():
            value_str = input_area.text()
            if value_str == "":
                value_str = arg_default
            try:
                if arg_type == int:
                    params[arg_id] = int(value_str)
                elif arg_type == str:
                    params[arg_id] = value_str
                elif arg_type == bool:
                    if value_str.lower() in ["true", "1"]:
                        params[arg_id] = True
                    elif value_str.lower() in ["false", "0"]:
                        params[arg_id] = False
                    else:
                        raise ValueError("布尔值格式不符合要求")
            except ValueError:
                return f"参数 {arg_id} 类型错误，应为 {arg_type.__name__}"
        return params


class LineConfirmDialog(QDialog):
    def __init__(self, old_lines, new_lines, parent=None):
        super().__init__(parent)

        # 设置窗口标题、大小
        self.setWindowTitle("文本处理器 - 修改确认")
        self.resize(800, 1)

        # 运行所需变量
        self.result = None
        self.old_lines = old_lines
        self.origin_new_lines = new_lines
        self.line_num = len(self.old_lines)
        self.modified_new_lines = []
        self.current_line = 0

        # 初始化 UI
        old_label = QLabel("原始行内容：")
        old_label.setStyleSheet("font-weight: bold;")
        old_edit = QTextEdit()
        old_edit.setReadOnly(True)
        old_edit.setMinimumHeight(180)
        old_edit.setMaximumHeight(180)

        new_label = QLabel("修改后行内容：")
        new_label.setStyleSheet("font-weight: bold;")
        new_edit = QTextEdit()
        new_edit.setReadOnly(True)
        new_edit.setMinimumHeight(180)
        new_edit.setMaximumHeight(180)

        cancel_all_btn = QPushButton("取消本次操作")
        cancel_all_btn.clicked.connect(lambda: self.cancel_all())
        keep_old_btn = QPushButton("取消本行修改")
        keep_old_btn.clicked.connect(lambda: self.set_choice("keep_old"))
        apply_new_btn = QPushButton("应用本行修改")
        apply_new_btn.setDefault(True)
        apply_new_btn.clicked.connect(lambda: self.set_choice("apply_new"))

        btn_layout = QHBoxLayout()
        btn_layout.addWidget(cancel_all_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(keep_old_btn)
        btn_layout.addWidget(apply_new_btn)

        layout = QVBoxLayout(self)
        layout.addWidget(old_label)
        layout.addSpacing(4)
        layout.addWidget(old_edit)
        layout.addSpacing(12)
        layout.addWidget(new_label)
        layout.addSpacing(4)
        layout.addWidget(new_edit)
        layout.addSpacing(12)
        layout.addLayout(btn_layout)
        layout.addStretch()

        self.old_edit = old_edit
        self.new_edit = new_edit

        self.confirm()

    def confirm(self):
        if self.current_line == self.line_num:
            self.accept()
            return

        while True:
            old_line = self.old_lines[self.current_line]
            new_line = self.origin_new_lines[self.current_line]
            if old_line == new_line:
                self.modified_new_lines.append(old_line)
                self.current_line += 1
                if self.current_line == len(self.old_lines):
                    self.accept()
                    return
            else:
                break
        old_line, new_line = check_different.check_different(old_line, new_line)
        self.setWindowTitle(f"文本处理器 - 修改确认 - 行 {self.current_line + 1}")
        self.old_edit.setHtml(old_line)
        self.new_edit.setHtml(new_line)

    def set_choice(self, choice):
        if choice == "keep_old":
            self.modified_new_lines.append(self.old_lines[self.current_line])
        elif choice == "apply_new":
            self.modified_new_lines.append(self.origin_new_lines[self.current_line])
        self.current_line += 1
        self.confirm()

    def cancel_all(self):
        self.result = "cancel_all"
        self.accept()


class LineCheckDialog(QDialog):
    def __init__(self, old_lines, if_check, parent=None):
        super().__init__(parent)

        # 设置窗口标题、大小
        self.setWindowTitle("文本处理器 - 行检查")
        self.resize(800, 1)

        # 运行所需变量
        self.result = None
        self.old_lines = old_lines
        self.new_lines = []
        self.line_num = len(self.old_lines)
        self.if_check = if_check
        self.current_line = 0

        # 初始化 UI
        old_label = QLabel("检查到的行原始内容：")
        old_label.setStyleSheet("font-weight: bold;")
        old_edit = QTextEdit()
        old_edit.setReadOnly(True)
        old_edit.setMinimumHeight(180)
        old_edit.setMaximumHeight(180)

        new_label = QLabel("手动修改：")
        new_label.setStyleSheet("font-weight: bold;")
        new_edit = QTextEdit()
        new_edit.setMinimumHeight(180)
        new_edit.setMaximumHeight(180)

        cancel_all_btn = QPushButton("取消本次操作")
        cancel_all_btn.clicked.connect(lambda: self.cancel_all())
        keep_old_btn = QPushButton("取消本行修改")
        keep_old_btn.clicked.connect(lambda: self.set_choice("keep_old"))
        apply_new_btn = QPushButton("应用本行修改")
        apply_new_btn.setDefault(True)
        apply_new_btn.clicked.connect(lambda: self.set_choice("apply_new"))

        btn_layout = QHBoxLayout()
        btn_layout.addWidget(cancel_all_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(keep_old_btn)
        btn_layout.addWidget(apply_new_btn)

        layout = QVBoxLayout(self)
        layout.addWidget(old_label)
        layout.addSpacing(4)
        layout.addWidget(old_edit)
        layout.addSpacing(12)
        layout.addWidget(new_label)
        layout.addSpacing(4)
        layout.addWidget(new_edit)
        layout.addSpacing(12)
        layout.addLayout(btn_layout)
        layout.addStretch()

        self.old_edit = old_edit
        self.new_edit = new_edit

        self.confirm()

    def confirm(self):
        if self.current_line == self.line_num:
            self.accept()
            return

        while True:
            old_line = self.old_lines[self.current_line]
            if not self.if_check[self.current_line]:
                self.new_lines.append(old_line)
                self.current_line += 1
                if self.current_line == len(self.old_lines):
                    self.accept()
                    return
            else:
                break
        self.setWindowTitle(f"文本处理器 - 行检查 - 行 {self.current_line + 1}")
        self.old_edit.setPlainText(old_line)
        self.new_edit.setPlainText(old_line)

    def set_choice(self, choice):
        if choice == "keep_old":
            self.new_lines.append(self.old_lines[self.current_line])
        elif choice == "apply_new":
            self.new_lines.append(self.new_edit.toPlainText())
        self.current_line += 1
        self.confirm()

    def cancel_all(self):
        self.result = "cancel_all"
        self.accept()


class SwitchFile(QDialog):
    def __init__(self, project_id, project_name, file_names, parent=None):
        super().__init__(parent)

        # 设置窗口标题、大小
        self.setWindowTitle(f"文本处理器 - {project_name} - 切换文件")
        self.resize(700, 500)

        # 选择的文件名称
        self.project_id = project_id
        self.project_name = project_name
        self.selected_file = ""

        # 初始化 UI
        list_widget = QListWidget()
        list_widget.itemSelectionChanged.connect(self.on_file_selected)
        for f in file_names:
            list_widget.addItem(QListWidgetItem(f))

        preview_btn = QPushButton("预览")
        preview_btn.clicked.connect(self.preview)
        preview_btn.setEnabled(False)
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setDefault(True)
        complete_btn = QPushButton("完成")
        complete_btn.clicked.connect(self.accept)
        complete_btn.setEnabled(False)
        btn_layout = QHBoxLayout()
        btn_layout.addWidget(preview_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(complete_btn)

        layout = QVBoxLayout(self)
        layout.addWidget(list_widget)
        layout.addLayout(btn_layout)

        self.preview_btn = preview_btn
        self.complete_btn = complete_btn
        self.list_widget = list_widget

    def preview(self):
        preview_file_path = f"projects/{self.project_id}/history/{self.selected_file}"
        initial_text = file.read_file(preview_file_path)
        TextEditorDialog(f"{self.project_name} - 切换文件 - 预览 - {self.selected_file}", initial_text,
                         is_read_only=True, parent=self).exec()

    def on_file_selected(self):
        self.selected_file = self.list_widget.currentItem().text()
        self.preview_btn.setEnabled(True)
        self.complete_btn.setEnabled(True)
        self.complete_btn.setDefault(True)


class ProjectManagement(QDialog):
    """主窗口 - 项目管理"""

    open_requested = pyqtSignal(str)
    delete_requested = pyqtSignal(str)
    new_requested = pyqtSignal(dict)

    def __init__(self, project_ids, projects, parent=None):
        super().__init__(parent)

        # 设置窗口标题、大小
        self.setWindowTitle("文本处理器 - 项目管理")
        self.resize(700, 500)

        # 项目列表
        project_list = QListWidget()
        project_list.itemSelectionChanged.connect(self.on_project_selected)
        for project_id in project_ids:
            project = projects[project_id]
            project_name = project["project_name"]
            item = QListWidgetItem(f"{project_name}（{project_id}）")
            item.setData(Qt.ItemDataRole.UserRole, project_id)
            project_list.addItem(item)

        # 底部按钮
        new_btn = QPushButton("新建项目")
        open_btn = QPushButton("打开项目")
        delete_btn = QPushButton("删除项目")
        cancel_btn = QPushButton("取消")
        new_btn.clicked.connect(self.on_new)
        open_btn.clicked.connect(self.on_open)
        delete_btn.clicked.connect(self.on_delete)
        cancel_btn.clicked.connect(self.reject)
        open_btn.setEnabled(False)
        delete_btn.setEnabled(False)

        btn_layout = QHBoxLayout()
        btn_layout.addWidget(new_btn)
        btn_layout.addWidget(open_btn)
        btn_layout.addWidget(delete_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(cancel_btn)

        layout = QVBoxLayout(self)
        layout.addWidget(project_list)
        layout.addLayout(btn_layout)

        # 赋值声明的属性
        self.open_btn = open_btn
        self.delete_btn = delete_btn
        self.project_list = project_list

    def on_project_selected(self):
        self.open_btn.setEnabled(True)
        self.open_btn.setDefault(True)
        self.delete_btn.setEnabled(True)

    def on_new(self):
        dialog = NewProject(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.new_requested.emit(dialog.project_info)
            self.accept()

    def on_open(self):
        item = self.project_list.currentItem()
        project_id = item.data(Qt.ItemDataRole.UserRole)
        self.open_requested.emit(project_id)
        self.accept()

    def on_delete(self):
        item = self.project_list.currentItem()
        project_id = item.data(Qt.ItemDataRole.UserRole)
        self.delete_requested.emit(project_id)


class NewProject(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        # 运行所需变量
        self.initial_text = ""
        self.project_info = {}

        # 初始化 UI
        self.setWindowTitle("文本处理器 - 项目管理 - 新建项目")
        self.resize(600, 1)

        name_edit = QLineEdit()
        id_edit = QLineEdit()
        set_initial_btn = QPushButton("设置初始文本")
        set_initial_btn.clicked.connect(self.open_initial_editor)

        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        complete_btn = QPushButton("完成")
        complete_btn.clicked.connect(self.create_project)
        complete_btn.setDefault(True)
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(complete_btn)

        layout = QFormLayout(self)
        layout.addRow("项目名称：", name_edit)
        layout.addRow("项目 ID（文件夹名）：", id_edit)
        layout.addRow(set_initial_btn)
        layout.addRow(btn_layout)

        self.name_edit = name_edit
        self.id_edit = id_edit

    def open_initial_editor(self):
        editor = TextEditorDialog("项目管理 - 新建项目 - 设置初始文本", parent=self)
        if editor.exec() == QDialog.DialogCode.Accepted:
            self.initial_text = editor.get_text()

    def create_project(self):
        project_name = self.name_edit.text().strip()
        project_id = self.id_edit.text().strip()
        project_path = f"projects/{project_id}"

        if not project_name or not project_id:
            MessageDialog("警告", "名称和 ID 不能为空", self).exec()
            return
        if not self.initial_text.strip():
            MessageDialog("警告", "必须设置初始文本", self).exec()
            return
        if file.exists(project_path):
            MessageDialog("警告", "项目 ID 已存在", self).exec()
            return
        if not validate_id.validate_id(project_id):
            MessageDialog("警告",
                          f"项目 ID 不能包含除数字、小写英文字母、下划线以外的字符，且不能以下划线或数字开头",
                          self).exec()
            return

        self.project_info = {
            "project_id": project_id,
            "project_name": project_name,
            "initial_text": self.initial_text
        }
        self.accept()
