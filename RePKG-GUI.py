import ctypes
import datetime  # 用于备份时间戳
import glob
import json
import os
import shutil
import subprocess
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

CONFIG_FILE = "assets/repkg_config.json"
FIRST_RUN_FILE = ".first_run"


def win_path(path: str) -> str:
    """将路径统一转换为 Windows 格式（反斜杠）"""
    return os.path.normpath(path)


def set_file_hidden(file_path):
    """
    设置文件为隐藏属性
    Set file as hidden attribute
    """
    try:
        # 使用 Windows API 设置文件属性为隐藏
        FILE_ATTRIBUTE_HIDDEN = 0x2
        ctypes.windll.kernel32.SetFileAttributesW(file_path, FILE_ATTRIBUTE_HIDDEN)
        return True
    except Exception as e:
        print(f"  [Warning]  无法设置隐藏属性 / Cannot set hidden attribute for {file_path}: {e}")
        return False


def create_transparent_mapping(parent_dir):
    """
    为分类后的项目创建透明映射（隐藏版本）
    Create transparent mapping for classified projects (hidden version)
    """

    print(f" 创建透明映射 / Creating transparent mapping...")

    # 获取所有分类目录
    category_dirs = []
    for item in os.listdir(parent_dir):
        item_path = os.path.join(parent_dir, item)
        # 排除隐藏目录、脚本文件和.first_run文件
        if (os.path.isdir(item_path) and
                item not in ["Unknown"] and
                not item.startswith('.')):
            category_dirs.append(item)

    created_links = []
    skipped_items = []

    for category in category_dirs:
        category_path = os.path.join(parent_dir, category)

        # 遍历该分类目录下的所有项目
        for project in os.listdir(category_path):
            project_path = os.path.join(category_path, project)

            # 只处理目录
            if not os.path.isdir(project_path):
                continue

            # 在父目录中创建符号链接的目标路径
            link_path = os.path.join(parent_dir, project)

            # 检查是否已存在同名项目 (符号链接不算，因为它将被删除后重新创建)
            if os.path.exists(link_path) and not os.path.islink(link_path):
                # 如果存在且不是符号链接，则跳过
                skipped_items.append(project)
                continue

            # 如果是已存在的符号链接，先删除，确保链接指向正确
            if os.path.islink(link_path):
                try:
                    os.unlink(link_path)
                except Exception as e:
                    print(f"  [Warning]  无法删除旧链接 / Failed to remove old link for {project}: {e}")
                    skipped_items.append(project)
                    continue

            try:
                # 创建符号链接
                relative_path = os.path.join(category, project)
                # 使用 os.symlink 创建相对路径链接
                os.symlink(relative_path, link_path)

                # 设置符号链接为隐藏
                set_file_hidden(link_path)

                created_links.append((project, category))

            except OSError as e:
                # 权限不足等错误
                print(f"  [Error] 创建链接失败 / Failed to create link for {project}: {e}")
                skipped_items.append(project)

    if created_links:
        print(
            f"  [Success] 成功创建 {len(created_links)} 个隐藏映射链接 / Successfully created {len(created_links)} hidden mapping links")

    if skipped_items:
        print(f"  [Warning]  跳过 {len(skipped_items)} 个项目 / Skipped {len(skipped_items)} items")

    return created_links, skipped_items


def classify_projects(parent_dir, log_callback=None, create_mapping=False):
    """
    根据 project.json 的 'type' 字段分类子文件夹。
    create_mapping: 是否在分类后自动创建透明映射
    """

    if log_callback:
        log_callback(f"📂 开始分类项目 / Starting project classification: {parent_dir}\n")

    # 定义 Unknown 文件夹路径
    unknown_dir = os.path.join(parent_dir, "Unknown")
    os.makedirs(unknown_dir, exist_ok=True)

    # 统计信息
    classified_count = 0
    error_count = 0

    # 遍历父目录下所有子文件夹
    items_to_process = [item for item in os.listdir(parent_dir) if
                        os.path.isdir(os.path.join(parent_dir, item)) and
                        item not in ["Unknown", "scene", "video"] and
                        not item.startswith('.') and
                        not item.endswith('.py') and
                        not item.endswith('.md')]

    for item in items_to_process:
        item_path = os.path.join(parent_dir, item)
        json_path = os.path.join(item_path, "project.json")

        # 默认分类为 Unknown
        category = "Unknown"

        # 尝试读取 project.json
        if os.path.exists(json_path):
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                # 获取 type 字段
                category = data.get("type", "Unknown").strip()
                if not category:  # 避免空字符串分类
                    category = "Unknown"
            except Exception as e:
                if log_callback:
                    log_callback(f"[错误/Error] 无法解析 {json_path}: {e}\n")
                error_count += 1
                category = "Unknown"  # 解析失败也归类到 Unknown

        # 目标目录路径
        target_dir = os.path.join(parent_dir, category)
        os.makedirs(target_dir, exist_ok=True)

        # 移动文件夹
        target_path = os.path.join(target_dir, item)

        # 若目标已存在，则重命名避免冲突 (此逻辑可能导致用户项目名改变，但为确保操作成功暂时保留)
        if os.path.exists(target_path):
            base = item
            counter = 1
            original_target_path = target_path
            while os.path.exists(target_path):
                new_name = f"{base}_{counter}"
                target_path = os.path.join(target_dir, new_name)
                counter += 1
            if log_callback:
                log_callback(
                    f"[警告/Warning] 目标路径 {original_target_path} 已存在，重命名 {item} → {os.path.basename(target_path)}\n")

        try:
            shutil.move(item_path, target_path)
            if log_callback:
                log_callback(f"[分类/Classified] {item} → {category}\n")
            classified_count += 1
        except Exception as e:
            if log_callback:
                log_callback(f"[错误/Error] 移动 {item} 失败: {e}\n")
            error_count += 1

    if log_callback:
        log_callback(f"\n 分类统计 / Classification statistics:\n")
        log_callback(f"  [Success] 成功分类 / Successfully classified: {classified_count}\n")
        log_callback(f"  [Error] 分类失败 / Classification failed: {error_count}\n")

    # 根据标志创建透明映射
    if classified_count > 0 and create_mapping:
        if log_callback:
            log_callback(f"\n 自动创建透明映射 / Auto-creating transparent mapping...\n")
        created_links, skipped_items = create_transparent_mapping(parent_dir)

        if log_callback:
            log_callback(f"\n[Success] 分类和映射完成 / Classification and mapping completed.\n")
            log_callback(f"  📁 项目已按类型分类到子目录 / Projects classified into subdirectories\n")
            log_callback(f"   已创建透明映射链接 / Transparent mapping links created\n")
            log_callback(f"  👁️  映射链接已隐藏，对用户不可见 / Mapping links are hidden from users\n")
    elif classified_count > 0 and not create_mapping:
        if log_callback:
            log_callback(f"\n[Success] 分类完成 / Classification completed. (跳过创建映射 / Skip creating mapping)\n")
    else:
        if log_callback:
            log_callback(f"\n[Warning]  没有项目需要分类 / No projects to classify\n")

    return classified_count, error_count


def remove_all_mappings(parent_dir, log_callback=None):
    """
    移除所有映射链接
    Remove all mapping links
    """

    if log_callback:
        log_callback(f"  移除所有映射链接 / Removing all mapping links...\n")

    removed_count = 0

    for item in os.listdir(parent_dir):
        item_path = os.path.join(parent_dir, item)

        # 只处理符号链接
        if os.path.islink(item_path):
            try:
                os.unlink(item_path)
                removed_count += 1
            except OSError as e:
                if log_callback:
                    log_callback(f"  [Error] 移除链接失败 / Failed to remove link {item}: {e}\n")

    if log_callback:
        log_callback(
            f"  [Success] 成功移除 {removed_count} 个映射链接 / Successfully removed {removed_count} mapping links\n")


def list_current_status(parent_dir, log_callback=None):
    """
    列出当前状态
    List current status
    """

    if log_callback:
        log_callback(f"📋 当前状态 / Current status in: {parent_dir}\n\n")

    # 统计分类目录
    category_dirs = []
    total_projects = 0
    linked_projects = 0

    # 忽略隐藏目录和链接
    for item in os.listdir(parent_dir):
        item_path = os.path.join(parent_dir, item)
        if (os.path.isdir(item_path) and
                item not in ["Unknown"] and
                not os.path.islink(item_path) and
                not item.startswith('.')):
            category_dirs.append(item)

    if log_callback:
        log_callback(f"📁 分类目录 / Category directories:\n")
        for category in category_dirs:
            category_path = os.path.join(parent_dir, category)
            # 统计子目录（项目）数量
            projects = [item for item in os.listdir(category_path)
                        if os.path.isdir(os.path.join(category_path, item))]
            total_projects += len(projects)

            log_callback(f"  {category}: {len(projects)} 个项目 / projects\n")

    # 统计 Unknown 目录的项目
    unknown_path = os.path.join(parent_dir, "Unknown")
    if os.path.exists(unknown_path) and os.path.isdir(unknown_path):
        unknown_projects = [item for item in os.listdir(unknown_path)
                            if os.path.isdir(os.path.join(unknown_path, item))]
        total_projects += len(unknown_projects)
        if log_callback:
            log_callback(f"  Unknown: {len(unknown_projects)} 个项目 / projects\n")

    # 统计映射链接
    if log_callback:
        log_callback(f"\n 映射链接 / Mapping links:\n")
        link_items = []
        for item in os.listdir(parent_dir):
            item_path = os.path.join(parent_dir, item)
            if os.path.islink(item_path):
                linked_projects += 1
                link_items.append(item_path)

        for item_path in link_items:
            item = os.path.basename(item_path)
            # 检查是否为隐藏文件
            try:
                attrs = ctypes.windll.kernel32.GetFileAttributesW(item_path)
                is_hidden = bool(attrs & 0x2)  # FILE_ATTRIBUTE_HIDDEN
                status = "隐藏/hidden" if is_hidden else "可见/visible"
            except:
                status = "未知/unknown"
            log_callback(f"  {item} ({status}) -> {os.path.basename(os.readlink(item_path))}\n")

    if log_callback:
        log_callback(f"\n 总体统计 / Overall statistics:\n")
        log_callback(f"  总项目数 / Total projects: {total_projects}\n")
        log_callback(f"  映射链接数 / Mapping links: {linked_projects}\n")
        log_callback(f"  未映射项目数 / Unmapped projects: {total_projects - linked_projects}\n")


class RePKG_GUI:
    def __init__(self, root):
        self.root = root
        # === 检查首次启动 ===
        if self.is_first_run():
            self.show_user_agreement()

        # === 加载配置 ===
        self.config = self.load_config()

        # --- UI Initialization / Data Setup ---
        self.initialize_data()

        title = f"{self.config['app_name']} {self.config['version']} ({self.config['platform']}) - {self.config['author']}"
        self.root.title(title)

        # === 创建主框架 ===
        main_frame = tk.Frame(root)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Grid setup for main_frame (3. & 4. 增大日志显示占比 & 动态调整)
        # Row 0: Notebook (weight 1)
        # Row 1: Log Area (weight 3 - 更多空间)
        # Row 2: Control Buttons (weight 0 - 固定高度)
        main_frame.grid_rowconfigure(0, weight=1)
        main_frame.grid_rowconfigure(1, weight=3)
        main_frame.grid_rowconfigure(2, weight=0)
        main_frame.grid_columnconfigure(0, weight=1)

        # === 标签页控件 (Row 0) ===
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.grid(row=0, column=0, sticky="nsew", pady=(0, 5))

        # === 创建各个标签页 ===
        self.create_config_tab()  # 1. 重命名并调整布局
        self.create_classify_tab()
        self.create_backup_restore_tab()  # 新增备份还原标签页
        self.create_about_tab()

        # === 日志区域 (Row 1, independent) ===
        log_area_frame = self.create_log_area(main_frame)
        log_area_frame.grid(row=1, column=0, sticky="nsew", pady=5)

        # === 底部控制按钮区域 (Row 2) ===
        control_frame = self.create_control_buttons(main_frame)
        control_frame.grid(row=2, column=0, sticky="ew", pady=(5, 0))

        # 首次加载时更新预览
        self.root.after(100, self.update_preview)

    def initialize_data(self):
        """初始化配置和Tkinter变量 (使用 StringVar)"""
        script_dir = os.path.dirname(os.path.abspath(__file__))

        # Paths
        default_exe = self.config.get("repkg_path", os.path.join(script_dir, "RePKG.exe"))
        default_output = self.config.get("output_dir", os.path.join(script_dir, "output"))
        default_classify_dir = self.config.get("classify_dir", default_output)

        self.repkg_path = tk.StringVar(value=default_exe)
        self.input_entry = tk.StringVar(value=self.config.get("input_dir", ""))
        self.output_entry = tk.StringVar(value=default_output)
        self.classify_dir = tk.StringVar(value=default_classify_dir)
        # 统一备份根目录变量 (新的)
        self.unified_backup_root = tk.StringVar(value=self.config.get("unified_backup_root", default_output))

        # Mode
        self.mode = tk.StringVar(value=self.config.get("mode", "extract"))

        # Options
        self.options = {
            "-t, --tex (转换TEX)": tk.BooleanVar(value=self.config.get("tex", True)),
            "-c, --copyproject (复制项目文件)": tk.BooleanVar(value=self.config.get("copyproject", True)),
            "-n, --usename (使用项目名)": tk.BooleanVar(value=self.config.get("usename", True)),
            "--overwrite (覆盖现有文件)": tk.BooleanVar(value=self.config.get("overwrite", True)),
            "-r, --recursive (递归搜索)": tk.BooleanVar(value=self.config.get("recursive", True)),
        }
        self.python_options = {
            "复制预览图像 (preview.*)": tk.BooleanVar(value=self.config.get("copy_preview", True)),
            "原地替换模式自动备份": tk.BooleanVar(value=self.config.get("auto_backup", True)),
        }
        self.classify_options = {
            "创建透明映射（隐藏链接）": tk.BooleanVar(value=True),
        }

        # Bindings for preview update
        self.repkg_path.trace_add("write", lambda *args: self.update_preview())
        self.input_entry.trace_add("write", lambda *args: self.update_preview())
        self.output_entry.trace_add("write", lambda *args: self.update_preview())
        self.mode.trace_add("write", lambda *args: self.update_preview())
        for var in self.options.values():
            var.trace_add("write", lambda *args: self.update_preview())

    def pack_path_selector(self, parent_frame, label_text, var_control, button_command):
        """Helper to create a path entry with a browse button."""

        tk.Label(parent_frame, text=label_text, font=("Arial", 10, "bold")).pack(anchor="w", padx=0, pady=(10, 2))
        frame_selector = tk.Frame(parent_frame)
        frame_selector.pack(fill="x", padx=0, pady=2)

        tk.Entry(frame_selector, textvariable=var_control).pack(side="left", fill="x", expand=True)
        tk.Button(frame_selector, text="浏览", command=button_command).pack(side="left", padx=5)

    def pack_mode_selector(self, parent_frame, label_text, var_control, modes):
        """Helper to create radio buttons for mode selection."""

        tk.Label(parent_frame, text=label_text, font=("Arial", 10, "bold")).pack(anchor="w", padx=0, pady=(10, 2))
        mode_frame = tk.Frame(parent_frame)
        mode_frame.pack(anchor="w", padx=10, pady=2)

        for mode in modes:
            text = f"{mode} 模式"
            if mode == "extract":
                text += " (extract)"
            elif mode == "info":
                text += " (info)"

            tk.Radiobutton(mode_frame, text=text, variable=var_control, value=mode).pack(anchor="w")

    def pack_checkbox_group(self, parent_frame, label_text, options_dict):
        """Helper to create a group of checkboxes."""

        tk.Label(parent_frame, text=label_text, font=("Arial", 10, "bold")).pack(anchor="w", padx=0, pady=(10, 2))
        frame_opts = tk.Frame(parent_frame)
        frame_opts.pack(anchor="w", padx=10, pady=2)

        for text, var in options_dict.items():
            tk.Checkbutton(frame_opts, text=text, variable=var).pack(anchor="w")

    def create_config_tab(self):
        """
        创建配置标签页，重命名为 'RePKG'，并使用左右两栏布局
        2. 调整标签页布局为左侧（路径信息）右侧（配置参数）
        """
        config_frame = ttk.Frame(self.notebook)
        # 1. 重命名标签页
        self.notebook.add(config_frame, text="RePKG")

        # 配置 config_frame 的 Grid 布局
        config_frame.grid_columnconfigure(0, weight=1, uniform="col")  # 左栏 (路径)
        config_frame.grid_columnconfigure(1, weight=1, uniform="col")  # 右栏 (参数)
        config_frame.grid_rowconfigure(0, weight=1)  # 主要内容行 (扩展)
        config_frame.grid_rowconfigure(1, weight=0)  # 预览行 (固定高度)

        # --- 左侧框架 (路径信息) ---
        left_frame = ttk.LabelFrame(config_frame, text="路径信息", padding="10")
        left_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        left_frame.grid_columnconfigure(0, weight=1)

        # --- 右侧框架 (配置参数) ---
        right_frame = ttk.LabelFrame(config_frame, text="配置参数", padding="10")
        right_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        right_frame.grid_columnconfigure(0, weight=1)

        # === 左栏组件 (路径) ===
        self.pack_path_selector(left_frame, "RePKG.exe 路径（默认脚本所在目录）:",
                                self.repkg_path, self.select_exe)
        self.pack_path_selector(left_frame, "输入根目录（含 .pkg 文件或子目录）:",
                                self.input_entry, self.select_input_dir)
        self.pack_path_selector(left_frame, "输出根目录 (可与输入目录相同，将启用原地替换与备份):",
                                self.output_entry, self.select_output_dir)

        # === 右栏组件 (模式和选项) ===
        self.pack_checkbox_group(right_frame, "RePKG 命令选项:", self.options)
        self.pack_checkbox_group(right_frame, "Python 脚本选项:", self.python_options)

        # --- 命令预览 (Row 1) ---
        preview_frame = ttk.LabelFrame(config_frame, text="命令预览（Windows CMD 格式）", padding="10")
        preview_frame.grid(row=1, column=0, columnspan=2, sticky="ew", padx=10, pady=(0, 10))

        self.cmd_preview = tk.Text(preview_frame, height=4, bg="#f5f5f5", font=("Consolas", 9))
        self.cmd_preview.pack(fill="x", expand=True)

    def create_classify_tab(self):
        """创建项目分类标签页"""
        classify_frame = ttk.Frame(self.notebook)
        self.notebook.add(classify_frame, text=" 项目分类")

        # === 分类根目录 ===
        tk.Label(classify_frame, text="分类根目录（包含项目子目录）:", font=("Arial", 10, "bold")).pack(anchor="w",
                                                                                                      padx=10,
                                                                                                      pady=(10, 2))
        frame_classify = tk.Frame(classify_frame)
        frame_classify.pack(fill="x", padx=10, pady=2)

        tk.Entry(frame_classify, textvariable=self.classify_dir).pack(side="left", fill="x", expand=True)
        tk.Button(frame_classify, text="浏览", command=self.select_classify_dir).pack(side="left", padx=5)

        # === 选项 ===
        tk.Label(classify_frame, text="分类选项:", font=("Arial", 10, "bold")).pack(anchor="w", padx=10, pady=(10, 2))

        frame_opts = tk.Frame(classify_frame)
        frame_opts.pack(anchor="w", padx=20, pady=2)
        for text, var in self.classify_options.items():
            tk.Checkbutton(frame_opts, text=text, variable=var).pack(anchor="w")

        # === 操作按钮 ===
        tk.Label(classify_frame, text="操作:", font=("Arial", 10, "bold")).pack(anchor="w", padx=10, pady=(10, 2))
        control_frame = tk.Frame(classify_frame)
        control_frame.pack(fill="x", padx=10, pady=5)

        tk.Button(control_frame, text=" 开始分类", bg="#2196F3", fg="white",
                  font=("Arial", 10, "bold"), command=self.classify_projects).pack(side="left", padx=5)

        tk.Button(control_frame, text=" 增加映射", bg="#4CAF50", fg="white",
                  font=("Arial", 10, "bold"), command=self.create_mappings_manual).pack(side="left", padx=5)

        tk.Button(control_frame, text=" 查看状态", bg="#FF9800", fg="white",
                  font=("Arial", 10, "bold"), command=self.show_status).pack(side="left", padx=5)

        tk.Button(control_frame, text=" 移除映射", bg="#F44336", fg="white",
                  font=("Arial", 10, "bold"), command=self.remove_mappings).pack(side="left", padx=5)

    def create_backup_restore_tab(self):
        """创建备份还原标签页"""
        bkr_frame = ttk.Frame(self.notebook)
        self.notebook.add(bkr_frame, text="⏪ 备份还原")

        bkr_frame.grid_columnconfigure(0, weight=1)
        bkr_frame.grid_rowconfigure(1, weight=1)

        # === 路径选择 (Row 0) ===
        path_frame = ttk.LabelFrame(bkr_frame, text="统一备份根目录", padding="10")
        path_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=10)

        # 使用新的变量和选择器
        self.pack_path_selector(path_frame, "选择统一备份根目录（即执行原地替换的输出/输入根目录）:",
                                self.unified_backup_root, self.select_unified_backup_root)

        # === 备份列表和操作 (Row 1) ===
        list_frame = ttk.LabelFrame(bkr_frame, text="可用批次备份列表（位于根目录/.unified_backup/）", padding="10")
        list_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=0)
        list_frame.grid_columnconfigure(0, weight=1)
        list_frame.grid_rowconfigure(0, weight=1)

        # Listbox with Scrollbar
        list_scroll = tk.Scrollbar(list_frame)
        list_scroll.grid(row=0, column=1, sticky="ns")

        self.backup_listbox = tk.Listbox(list_frame, height=10, yscrollcommand=list_scroll.set, font=("Consolas", 10))
        self.backup_listbox.grid(row=0, column=0, sticky="nsew")
        list_scroll.config(command=self.backup_listbox.yview)

        # 底部操作按钮
        control_frame = tk.Frame(list_frame)
        control_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(10, 0))

        tk.Button(control_frame, text="🔄 刷新备份列表", command=self.refresh_backups_list).pack(side="left", padx=5)
        tk.Button(control_frame, text="↩️ 还原选中批次", bg="#F44336", fg="white",
                  font=("Arial", 10, "bold"), command=self.start_restore_task).pack(side="left", padx=5)

        self.backup_listbox.bind("<<ListboxSelect>>", self.on_backup_select)  # 绑定选择事件

        # 首次加载时刷新列表
        self.root.after(200, self.refresh_backups_list)

    def on_backup_select(self, event):
        """在选中备份时更新日志提示"""
        selection = self.backup_listbox.curselection()
        if selection:
            backup_name = self.backup_listbox.get(selection[0])
            self.log_box.insert(tk.END,
                                f"\n[{datetime.datetime.now().strftime('%H:%M:%S')}] 已选中批次备份: {backup_name}\n")
            self.log_box.see(tk.END)

    def create_log_area(self, parent):
        """创建日志区域，作为独立于标签页的区域，并返回框架"""

        # 使用 LabelFrame 增加日志区域的边界和标题
        log_area_frame = tk.LabelFrame(parent, text="📝 运行日志", padx=5, pady=5)
        # log_area_frame 不再在内部 pack，而是返回给 __init__ 进行 grid 布局

        # 日志控制按钮
        log_control_frame = tk.Frame(log_area_frame)
        log_control_frame.pack(fill="x", pady=2)

        tk.Button(log_control_frame, text="清空日志", command=self.clear_log).pack(side="left", padx=5)
        tk.Button(log_control_frame, text="保存日志", command=self.save_log).pack(side="left", padx=5)

        # 自动滚动状态和按钮
        self.auto_scroll = True
        self.auto_scroll_button = tk.Button(log_control_frame,
                                            text="自动滚动: 启用",
                                            command=self.toggle_auto_scroll)
        self.auto_scroll_button.pack(side="left", padx=5)

        # 日志显示区域
        self.log_box = scrolledtext.ScrolledText(log_area_frame,
                                                 font=("Consolas", 9),
                                                 wrap="word")
        # 使用 fill="both", expand=True 确保它占用父框架（log_area_frame）的所有空间
        self.log_box.pack(fill="both", expand=True, padx=5, pady=5)

        return log_area_frame  # 返回框架，由 __init__ 中的 grid 管理

    def create_about_tab(self):
        """创建关于标签页"""
        about_frame = ttk.Frame(self.notebook)
        self.notebook.add(about_frame, text=" 关于")

        # 尝试从外部文件加载关于信息
        about_content = self.load_about_content()

        # 使用 ScrolledText 显示内容
        self.about_box = scrolledtext.ScrolledText(about_frame, wrap="word",
                                                   font=("Microsoft YaHei", 10),
                                                   bg="#ffffff", fg="#2c3e50",
                                                   relief="flat", bd=0,
                                                   padx=15, pady=15)
        self.about_box.pack(fill="both", expand=True)

        if about_content:
            self.about_box.insert(tk.END, about_content)
        else:
            # 提示内容已简化
            self.about_box.insert(tk.END, "关于页面内容从 about.txt 文件加载。\n\n"
                                          "如果此处内容为空，请确保在程序同级目录下创建了\n"
                                          "一个名为 about.txt 的纯文本文件，并填入内容。")

        self.about_box.config(state="disabled")

    def load_about_content(self):
        """从外部文件加载关于页面内容 (仅支持纯文本)"""
        text_file = "assets/txt/about.txt"
        if os.path.exists(text_file):
            try:
                with open(text_file, "r", encoding="utf-8") as f:
                    content = f.read()
                return content
            except Exception as e:
                # 返回错误信息而不是默认内容
                return f"加载 about.txt 失败: {e}"

        # 如果外部文件不存在或加载失败，使用默认内容（空字符串）
        return self.get_default_about_content()

    def get_default_about_content(self):
        """获取默认的关于页面内容（返回空字符串，避免硬编码）"""
        return ""

    def is_first_run(self):
        """检查是否为首次运行"""
        return not os.path.exists(FIRST_RUN_FILE)

    def mark_first_run_complete(self):
        """标记首次运行完成"""
        try:
            with open(FIRST_RUN_FILE, "w", encoding="utf-8") as f:
                f.write("First run completed")
        except Exception as e:
            print(f"无法创建首次运行标记文件: {e}")

    def show_user_agreement(self):
        """显示用户协议确认弹窗"""
        # 创建协议窗口
        agreement_window = tk.Toplevel(self.root)
        agreement_window.title("📋 用户协议与免责声明")
        agreement_window.geometry("900x700")
        agreement_window.resizable(True, True)
        agreement_window.configure(bg="#f0f0f0")

        # 设置窗口居中
        agreement_window.transient(self.root)
        agreement_window.grab_set()

        # 窗口居中显示
        agreement_window.update_idletasks()
        x = (agreement_window.winfo_screenwidth() // 2) - (900 // 2)
        y = (agreement_window.winfo_screenheight() // 2) - (700 // 2)
        agreement_window.geometry(f"900x700+{x}+{y}")

        # 创建主框架
        main_frame = tk.Frame(agreement_window, bg="#f0f0f0")
        main_frame.pack(fill="both", expand=True, padx=15, pady=15)

        # 标题区域
        title_frame = tk.Frame(main_frame, bg="#2c3e50", relief="raised", bd=2)
        title_frame.pack(fill="x", pady=(0, 15))

        title_label = tk.Label(title_frame, text="📋 用户协议与免责声明",
                               font=("Microsoft YaHei", 16, "bold"),
                               fg="white", bg="#2c3e50", pady=15)
        title_label.pack()

        subtitle_label = tk.Label(title_frame,
                                  text="请仔细阅读以下协议内容，同意后方可使用本软件",
                                  font=("Microsoft YaHei", 10),
                                  fg="#ecf0f1", bg="#2c3e50")
        subtitle_label.pack(pady=(0, 15))

        # 内容区域框架
        content_frame = tk.Frame(main_frame, bg="#ffffff", relief="sunken", bd=2)
        content_frame.pack(fill="both", expand=True, pady=(0, 15))

        # 创建滚动区域
        canvas = tk.Canvas(content_frame, bg="#ffffff", highlightthickness=0)
        scrollbar = ttk.Scrollbar(content_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg="#ffffff")

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # 加载协议内容
        agreement_text = self.load_user_agreement()

        # 显示协议内容
        text_widget = tk.Text(scrollable_frame, wrap="word",
                              font=("Microsoft YaHei", 10),
                              bg="#ffffff", fg="#2c3e50",
                              relief="flat", bd=0,
                              padx=20, pady=20,
                              selectbackground="#3498db",
                              selectforeground="white")
        text_widget.pack(fill="both", expand=True)

        if agreement_text:
            text_widget.insert("1.0", agreement_text)
        else:
            text_widget.insert("1.0", "用户协议内容从 user_agreement.txt 文件加载。\n\n"
                                      "如果此处内容为空，请确保在程序同级目录下创建了\n"
                                      "一个名为 user_agreement.txt 的纯文本文件，并填入内容。")

        text_widget.config(state="disabled")

        # 配置滚动区域
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # 底部按钮区域
        button_frame = tk.Frame(main_frame, bg="#f0f0f0")
        button_frame.pack(fill="x", pady=(0, 10))

        # 重要提示
        warning_frame = tk.Frame(button_frame, bg="#fff3cd", relief="solid", bd=1)
        warning_frame.pack(fill="x", pady=(0, 15))

        warning_label = tk.Label(warning_frame,
                                 text="[Warning] 重要提示：请仔细阅读上述协议内容，同意后方可使用本软件",
                                 font=("Microsoft YaHei", 11, "bold"),
                                 fg="#856404", bg="#fff3cd", pady=10)
        warning_label.pack()

        # 按钮区域
        button_inner_frame = tk.Frame(button_frame, bg="#f0f0f0")
        button_inner_frame.pack()

        def on_disagree():
            # 创建确认对话框
            result = messagebox.askyesno("确认退出",
                                         "您选择不同意用户协议。\n\n"
                                         "这意味着您无法使用本软件。\n"
                                         "确定要退出程序吗？",
                                         icon="warning")
            if result:
                agreement_window.destroy()
                self.root.quit()

        def on_agree():
            # 创建确认对话框
            result = messagebox.askyesno("确认同意",
                                         "您确认已仔细阅读并同意用户协议吗？\n\n"
                                         "点击'是'将继续使用本软件。",
                                         icon="question")
            if result:
                self.mark_first_run_complete()
                agreement_window.destroy()

        # 按钮样式
        button_style = {
            "font": ("Microsoft YaHei", 11, "bold"),
            "relief": "raised",
            "bd": 2,
            "cursor": "hand2",
            "padx": 25,
            "pady": 8
        }

        # 不同意按钮
        disagree_btn = tk.Button(button_inner_frame,
                                 text="[Deny] /不同意",
                                 command=on_disagree,
                                 bg="#e74c3c",
                                 fg="white",
                                 activebackground="#c0392b",
                                 activeforeground="white",
                                 **button_style)
        disagree_btn.pack(side="left", padx=(0, 15))

        # 同意按钮
        agree_btn = tk.Button(button_inner_frame,
                              text="[Agree and Continue] 同意并继续",
                              command=on_agree,
                              bg="#27ae60",
                              fg="white",
                              activebackground="#229954",
                              activeforeground="white",
                              **button_style)
        agree_btn.pack(side="left", padx=(15, 0))

        # 添加按钮悬停效果
        def on_disagree_enter(e):
            disagree_btn.config(bg="#c0392b")

        def on_disagree_leave(e):
            disagree_btn.config(bg="#e74c3c")

        def on_agree_enter(e):
            agree_btn.config(bg="#229954")

        def on_agree_leave(e):
            agree_btn.config(bg="#27ae60")

        disagree_btn.bind("<Enter>", on_disagree_enter)
        disagree_btn.bind("<Leave>", on_disagree_leave)
        agree_btn.bind("<Enter>", on_agree_enter)
        agree_btn.bind("<Leave>", on_agree_leave)

        # 设置窗口关闭事件
        def on_closing():
            result = messagebox.askyesno("确认退出",
                                         "您选择关闭协议窗口。\n\n"
                                         "这意味着您无法使用本软件。\n"
                                         "确定要退出程序吗？",
                                         icon="warning")
            if result:
                agreement_window.destroy()
                self.root.quit()

        agreement_window.protocol("WM_DELETE_WINDOW", on_closing)

        # 设置焦点到同意按钮
        agree_btn.focus_set()

    def load_user_agreement(self):
        """加载用户协议内容"""
        agreement_file = "assets/txt/user_agreement.txt"

        # 如果存在外部文件，尝试加载
        if os.path.exists(agreement_file):
            try:
                with open(agreement_file, "r", encoding="utf-8") as f:
                    content = f.read()
                return content
            except Exception as e:
                # 返回错误信息而不是默认内容
                return f"加载 user_agreement.txt 失败: {e}"

        # 如果外部文件不存在或加载失败，使用默认内容（空字符串）
        return self.get_default_agreement_content()

    def get_default_agreement_content(self):
        """获取默认的用户协议内容（返回空字符串，避免硬编码）"""
        return ""

    def create_control_buttons(self, parent):
        """创建底部控制按钮区域，并返回框架"""
        control_frame = tk.Frame(parent)

        # 主要操作按钮
        main_buttons = tk.Frame(control_frame)
        main_buttons.pack(side="left")

        tk.Button(main_buttons, text="🚀 运行任务", bg="#4CAF50", fg="white",
                  font=("Arial", 11, "bold"), command=self.start_task).pack(side="left", padx=5)
        tk.Button(main_buttons, text="💾 保存配置", command=self.save_config).pack(side="left", padx=5)
        tk.Button(main_buttons, text="📁 打开输出目录", command=self.open_output_dir).pack(side="left", padx=5)

        return control_frame  # 返回框架，由 __init__ 中的 grid 管理

    # ------------------------------------------------------------
    #  文件选择区 (使用 StringVar 的 set 方法)
    # ------------------------------------------------------------
    def select_exe(self):
        path = filedialog.askopenfilename(title="选择 RePKG.exe", filetypes=[("RePKG Executable", "*.exe")])
        if path:
            self.repkg_path.set(path)

    def select_input_dir(self):
        path = filedialog.askdirectory(title="选择输入根目录")
        if path:
            self.input_entry.set(path)

    def select_output_dir(self):
        path = filedialog.askdirectory(title="选择输出根目录")
        if path:
            self.output_entry.set(path)

    def select_classify_dir(self):
        """选择分类根目录"""
        path = filedialog.askdirectory(title="选择分类根目录")
        if path:
            self.classify_dir.set(path)

    def select_unified_backup_root(self):
        """选择备份还原的统一备份根目录 """
        path = filedialog.askdirectory(title="选择统一备份根目录")
        if path:
            self.unified_backup_root.set(path)
            self.refresh_backups_list()

    def open_output_dir(self):
        """打开输出目录"""
        output_dir = self.output_entry.get().strip()
        if not output_dir:
            messagebox.showwarning("警告", "请先设置输出目录！")
            return

        if not os.path.exists(output_dir):
            messagebox.showwarning("警告", f"输出目录不存在: {output_dir}")
            return

        try:
            os.startfile(output_dir)  # Windows 打开文件夹
        except Exception as e:
            messagebox.showerror("错误", f"无法打开输出目录: {e}")

    def clear_log(self):
        """清空日志"""
        self.log_box.delete(1.0, tk.END)
        self.log_box.insert(tk.END, f"📝 [{datetime.datetime.now().strftime('%H:%M:%S')}] 日志已清空\n")

    def save_log(self):
        """保存日志到文件"""
        log_content = self.log_box.get(1.0, tk.END)
        if not log_content.strip():
            messagebox.showwarning("警告", "日志内容为空！")
            return

        filename = filedialog.asksaveasfilename(
            title="保存日志",
            defaultextension=".txt",
            initialfile=f"RePKG_Log_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")]
        )

        if filename:
            try:
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(log_content)
                messagebox.showinfo("成功", f"日志已保存到: {filename}")
            except Exception as e:
                messagebox.showerror("错误", f"保存日志失败: {e}")

    def toggle_auto_scroll(self):
        """切换自动滚动状态"""
        self.auto_scroll = not self.auto_scroll
        status = "启用" if self.auto_scroll else "禁用"
        self.auto_scroll_button.config(text=f"自动滚动: {status}")

    # ------------------------------------------------------------
    #  配置保存/加载
    # ------------------------------------------------------------
    def load_config(self):
        # 默认配置
        default_config = {
            "app_name": "RePKG 批量提取 GUI",
            "version": "v4 (Modified)",
            "platform": "Windows 版",
            "author": "by YuefChen",
            "repkg_path": os.path.join(os.getcwd(), "RePKG.exe"),
            "input_dir": "",
            "output_dir": "",
            "mode": "extract",
            "tex": True,
            "copyproject": True,
            "usename": True,
            "overwrite": True,
            "recursive": True,
            "copy_preview": True,
            "auto_backup": True,
            "classify_dir": "",
            "unified_backup_root": ""
        }

        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    loaded_config = json.load(f)

                    # 合并默认配置和加载的配置
                    for key, value in default_config.items():
                        if key not in loaded_config:
                            loaded_config[key] = value
                    # 移除旧的不需要的配置项
                    return loaded_config
            except Exception:
                return default_config
        return default_config

    def save_config(self):
        # 更新当前配置 (使用 .get() 获取 StringVar/BooleanVar 的值)
        self.config.update({
            "repkg_path": self.repkg_path.get().strip(),
            "input_dir": self.input_entry.get().strip(),
            "output_dir": self.output_entry.get().strip(),
            "mode": self.mode.get(),
            "tex": self.options["-t, --tex (转换TEX)"].get(),
            "copyproject": self.options["-c, --copyproject (复制项目文件)"].get(),
            "usename": self.options["-n, --usename (使用项目名)"].get(),
            "overwrite": self.options["--overwrite (覆盖现有文件)"].get(),
            "recursive": self.options["-r, --recursive (递归搜索)"].get(),
            "copy_preview": self.python_options["复制预览图像 (preview.*)"].get(),
            "auto_backup": self.python_options["原地替换模式自动备份"].get(),
            "classify_dir": self.classify_dir.get().strip(),
            "unified_backup_root": self.unified_backup_root.get().strip(),
        })

        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(self.config, f, ensure_ascii=False, indent=2)
        messagebox.showinfo("保存成功", f"配置已保存到 {CONFIG_FILE}")

    # ------------------------------------------------------------
    #  命令生成（确保Windows路径）
    # ------------------------------------------------------------
    def build_command(self, pkg_path):
        exe_path = self.repkg_path.get().strip()
        if not os.path.isfile(exe_path):
            raise FileNotFoundError(f"未找到 RePKG 可执行文件: {exe_path}")

        project_name = self.get_project_name(pkg_path)
        output_root = self.output_entry.get().strip() or "./output"
        output_dir = os.path.join(output_root, project_name)
        os.makedirs(output_dir, exist_ok=True)

        # 使用 Windows 路径（反斜杠 + 引号）
        cmd = [win_path(exe_path), self.mode.get()]
        for key, var in self.options.items():
            if var.get():
                # 提取选项参数
                if ',' in key:
                    option = key.split(',')[0].strip()
                else:
                    option = key.split(' (')[0].strip()
                cmd.append(option)

        cmd += ["-o", win_path(output_dir), win_path(pkg_path)]
        return cmd

    # ------------------------------------------------------------
    #  扫描 .pkg 文件
    # ------------------------------------------------------------
    def scan_pkg_files(self, root_dir):
        pkg_list = []
        # 根据 -r, --recursive 选项判断是否递归搜索
        recursive = self.options["-r, --recursive (递归搜索)"].get()

        # glob.iglob 在 Python 3.5+ 支持 recursive=True
        # 但是 os.walk 更可靠且不需要依赖版本
        for dirpath, _, filenames in os.walk(root_dir):
            for f in filenames:
                if f.lower().endswith(".pkg"):
                    pkg_list.append(os.path.join(dirpath, f))

            # 如果不递归，跳过子目录
            if not recursive:
                break  # 只处理一层目录

        return pkg_list

    def get_project_name(self, pkg_path):
        """获取项目名称（pkg文件所在目录的名称）"""
        pkg_dir = os.path.dirname(pkg_path)
        # 如果是递归搜索，项目名是相对于输入根目录的路径，但RePKG默认使用pkg所在目录名作为项目名，这里保持一致
        return os.path.basename(pkg_dir)

    def find_preview_image(self, pkg_path):
        """查找与pkg文件同级的preview图像文件"""
        pkg_dir = os.path.dirname(pkg_path)
        pkg_name = os.path.splitext(os.path.basename(pkg_path))[0]

        # 支持的图像格式
        image_extensions = ['*.png', '*.jpg', '*.jpeg', '*.gif', '*.bmp', '*.tiff', '*.webp']

        # 查找preview开头的图像文件
        for ext in image_extensions:
            pattern = os.path.join(pkg_dir, f"preview{ext}")
            matches = glob.glob(pattern, recursive=False)
            if matches:
                return matches[0]  # 返回第一个匹配的文件

        # 如果没找到preview开头的，查找与pkg同名的图像文件
        for ext in image_extensions:
            pattern = os.path.join(pkg_dir, f"{pkg_name}{ext}")
            matches = glob.glob(pattern, recursive=False)
            if matches:
                return matches[0]

        return None

    def copy_preview_image(self, pkg_path, output_dir):
        """
        拷贝预览图像到输出目录，并同步拷贝 project.json
        - 拷贝 preview 图像只有在 options 启用时发生
        - project.json 始终同步拷贝
        """
        success_preview = False

        # 拷贝 preview 图像（受选项控制）
        if self.python_options["复制预览图像 (preview.*)"].get():
            preview_path = self.find_preview_image(pkg_path)
            if preview_path:
                try:
                    os.makedirs(output_dir, exist_ok=True)
                    # 获取预览图像的文件名和扩展名
                    preview_filename = os.path.basename(preview_path)
                    preview_name, preview_ext = os.path.splitext(preview_filename)
                    # 如果预览图像不是preview开头，重命名为preview
                    if not preview_name.lower().startswith('preview'):
                        preview_filename = f"preview{preview_ext}"
                    dest_path = os.path.join(output_dir, preview_filename)
                    shutil.copy2(preview_path, dest_path)
                    success_preview = True
                except Exception as e:
                    self.log_box.insert(tk.END, f"[Error] 拷贝预览图像失败: {e}\n")

        # 无论是否拷贝preview，总是尝试同步拷贝 project.json
        try:
            pkg_dir = os.path.dirname(pkg_path)
            project_json_src = os.path.join(pkg_dir, "project.json")
            if os.path.isfile(project_json_src):
                os.makedirs(output_dir, exist_ok=True)
                dest_project_json = os.path.join(output_dir, "project.json")
                shutil.copy2(project_json_src, dest_project_json)
        except Exception as e:
            self.log_box.insert(tk.END, f"[Error] 同步拷贝 project.json 失败: {e}\n")

        return success_preview

    # ------------------------------------------------------------
    #  执行批量任务
    # ------------------------------------------------------------
    def start_task(self):
        input_dir = self.input_entry.get().strip()
        output_dir = self.output_entry.get().strip()

        if not os.path.isdir(input_dir):
            messagebox.showerror("错误", "请输入有效的输入目录！")
            return

        if not output_dir:
            messagebox.showerror("错误", "请输入有效的输出目录！")
            return

        if not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)

        pkg_files = self.scan_pkg_files(input_dir)
        if not pkg_files:
            messagebox.showinfo("提示", "未找到任何 .pkg 文件。")
            return

        self.log_box.delete(1.0, tk.END)
        self.log_box.insert(tk.END,
                            f"[{datetime.datetime.now().strftime('%H:%M:%S')}] 发现 {len(pkg_files)} 个 .pkg 文件，开始处理...\n\n")

        self.update_preview(pkg_files[0])
        threading.Thread(target=self.run_batch, args=(pkg_files,), daemon=True).start()

    def prepare_backup_environment(self, output_dir_root, is_in_place_replace):
        """准备统一备份环境 / Prepare unified backup environment"""
        if not is_in_place_replace:
            return None

        self.log_box.insert(tk.END,
                            "[Warning] ⚠️ 原地替换模式已激活：提取前将自动备份现有文件到统一备份目录 `/.unified_backup/`。\n\n")
        if self.auto_scroll:
            self.log_box.see(tk.END)

        unified_backup_root = os.path.join(output_dir_root, ".unified_backup")
        os.makedirs(unified_backup_root, exist_ok=True)
        set_file_hidden(unified_backup_root)

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        batch_backup_path = os.path.join(unified_backup_root, f"backup_{timestamp}")
        os.makedirs(batch_backup_path, exist_ok=True)

        self.log_box.insert(tk.END, f"🕒 批次备份目录已创建: {os.path.basename(batch_backup_path)}\n\n")
        if self.auto_scroll:
            self.log_box.see(tk.END)
        return batch_backup_path

    def backup_project(self, project_path, project_name, batch_backup_path):
        """备份当前项目文件到统一目录 / Backup one project into unified backup path"""
        project_backup_path = os.path.join(batch_backup_path, project_name)
        os.makedirs(project_backup_path, exist_ok=True)

        self.log_box.insert(tk.END, f"  → 正在备份项目 {project_name}...\n")
        if self.auto_scroll:
            self.log_box.see(tk.END)

        copied_count = 0
        for item in os.listdir(project_path):
            src = os.path.join(project_path, item)
            dst = os.path.join(project_backup_path, item)
            try:
                if os.path.isdir(src):
                    shutil.copytree(src, dst)
                else:
                    shutil.copy2(src, dst)
                copied_count += 1
            except Exception as e:
                self.log_box.insert(tk.END, f"  [Warning] 备份失败: {item} ({e})\n")

        if copied_count > 0:
            self.log_box.insert(tk.END, f"  ✅ 已备份 {copied_count} 个文件。\n")
        else:
            try:
                os.rmdir(project_backup_path)
            except:
                pass
            self.log_box.insert(tk.END, f"  ⚠️ 未发现可备份内容，跳过。\n")

        if self.auto_scroll:
            self.log_box.see(tk.END)

    def execute_extraction(self, pkg_path, output_dir):
        """执行 repkg 提取命令并实时输出日志 / Execute extraction command and stream logs"""
        cmd = self.build_command(pkg_path)
        self.log_box.insert(tk.END, f"  → 执行命令: {' '.join(cmd)}\n")
        if self.auto_scroll:
            self.log_box.see(tk.END)

        process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="ignore"
        )

        for line in process.stdout:
            self.log_box.insert(tk.END, line)
            if self.auto_scroll:
                self.log_box.see(tk.END)

        process.wait()

        self.log_box.insert(tk.END, f"  ✅ 完成 {os.path.basename(pkg_path)} (退出码 {process.returncode})\n")
        if self.auto_scroll:
            self.log_box.see(tk.END)

        # 拷贝预览图像 / Copy preview image if enabled
        if self.copy_preview_image(pkg_path, output_dir):
            self.log_box.insert(tk.END, f"  📷 已拷贝预览图像到 {output_dir}\n")

        self.log_box.insert(tk.END, "\n")
        if self.auto_scroll:
            self.log_box.see(tk.END)

    def run_batch(self, pkg_files):
        """批量运行主逻辑 / Main entry for batch execution"""
        input_dir_root = self.input_entry.get().strip()
        output_dir_root = self.output_entry.get().strip()

        is_in_place_replace = (win_path(input_dir_root) == win_path(output_dir_root)) and (
        self.python_options["原地替换模式自动备份"])
        batch_backup_path = self.prepare_backup_environment(output_dir_root, is_in_place_replace)

        for i, pkg_path in enumerate(pkg_files, 1):
            project_name = self.get_project_name(pkg_path)
            output_dir = os.path.join(output_dir_root, project_name)
            project_path = os.path.dirname(pkg_path)

            self.log_box.insert(tk.END, f"[{i}/{len(pkg_files)}] 📦 处理项目: {project_name}\n")
            if self.auto_scroll:
                self.log_box.see(tk.END)

            # Step 1: 备份（若启用）
            if is_in_place_replace and batch_backup_path:
                self.backup_project(project_path, project_name, batch_backup_path)

            # Step 2: 提取执行
            try:
                self.execute_extraction(pkg_path, output_dir)
            except Exception as e:
                self.log_box.insert(tk.END, f"  [Error] 执行出错: {e}\n\n")
                if self.auto_scroll:
                    self.log_box.see(tk.END)

        self.log_box.insert(tk.END, f"[{datetime.datetime.now().strftime('%H:%M:%S')}] ✅ 所有任务完成！\n")
        if self.auto_scroll:
            self.log_box.see(tk.END)

    # ------------------------------------------------------------
    #  分类功能方法 
    # ------------------------------------------------------------
    def classify_projects(self):
        """分类项目"""
        output_dir = self.classify_dir.get().strip()
        if not output_dir:
            messagebox.showwarning("警告", "请先设置分类根目录！")
            return

        if not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
            messagebox.showinfo("提示", f"分类根目录不存在，已创建: {output_dir}")

        # 确认操作
        create_mapping = self.classify_options["创建透明映射（隐藏链接）"].get()
        mapping_status = "并自动创建映射" if create_mapping else "但不创建映射"
        result = messagebox.askyesno("确认分类",
                                     f"将对分类根目录中的项目进行分类 {mapping_status}：\n{output_dir}\n\n"
                                     "此操作将移动未分类项目到分类子目录。\n"
                                     "是否继续？")
        if not result:
            return

        self.log_box.delete(1.0, tk.END)
        self.log_box.insert(tk.END,
                            f"[{datetime.datetime.now().strftime('%H:%M:%S')}]  开始分类项目 / Starting project classification...\n")
        self.log_box.insert(tk.END, f"📁 目标目录 / Target directory: {output_dir}\n\n")

        # 在后台线程中执行分类
        threading.Thread(target=self.run_classify, args=(output_dir,), daemon=True).start()

    def run_classify(self, target_dir):
        """在后台线程中执行分类"""
        try:
            # 根据用户选择决定是否创建映射
            create_mapping = self.classify_options["创建透明映射（隐藏链接）"].get()

            def log_callback(message):
                self.log_box.insert(tk.END, message)
                if self.auto_scroll:
                    self.log_box.see(tk.END)

            # 调用分类函数并传入 create_mapping 标志
            classify_projects(target_dir, log_callback, create_mapping=create_mapping)

            # 显示完成消息
            self.log_box.insert(tk.END, f"\n[{datetime.datetime.now().strftime('%H:%M:%S')}] 🎉 分类任务完成！\n")

        except Exception as e:
            self.log_box.insert(tk.END, f"[Error] 分类过程中发生错误: {e}\n")

    def create_mappings_manual(self):
        """手动增加映射 (不对项目进行分类，只对已分类结构增加映射)"""
        output_dir = self.classify_dir.get().strip()
        if not output_dir:
            messagebox.showwarning("警告", "请先设置分类根目录！")
            return

        if not os.path.exists(output_dir):
            messagebox.showwarning("警告", f"分类根目录不存在: {output_dir}")
            return

        # 确认操作
        result = messagebox.askyesno("确认创建映射",
                                     f"将为分类根目录中的已分类项目创建透明映射（隐藏链接）：\n{output_dir}\n\n"
                                     "此操作不会移动项目，只创建符号链接。\n"
                                     "是否继续？")
        if not result:
            return

        self.log_box.delete(1.0, tk.END)
        self.log_box.insert(tk.END,
                            f"[{datetime.datetime.now().strftime('%H:%M:%S')}]  开始创建透明映射 / Starting transparent mapping creation...\n")
        self.log_box.insert(tk.END, f"📁 目标目录 / Target directory: {output_dir}\n\n")

        # 在后台线程中执行创建映射
        threading.Thread(target=self.run_create_mappings, args=(output_dir,), daemon=True).start()

    def run_create_mappings(self, target_dir):
        """在后台线程中执行创建映射"""
        try:
            def log_callback(message):
                self.log_box.insert(tk.END, message)
                if self.auto_scroll:
                    self.log_box.see(tk.END)

            log_callback(f" 正在创建映射于: {target_dir}\n")
            created_links, skipped_items = create_transparent_mapping(target_dir)

            # 显示完成消息
            self.log_box.insert(tk.END, f"\n[{datetime.datetime.now().strftime('%H:%M:%S')}] 🎉 映射创建完成！\n")
            self.log_box.insert(tk.END, f"[Success] 成功创建: {len(created_links)} 个映射\n")
            self.log_box.insert(tk.END, f"[Warning]  跳过: {len(skipped_items)} 个项目 (已存在或错误)\n")

        except Exception as e:
            self.log_box.insert(tk.END, f"[Error] 创建映射过程中发生错误: {e}\n")

    def show_status(self):
        """显示当前状态"""
        output_dir = self.classify_dir.get().strip()
        if not output_dir:
            messagebox.showwarning("警告", "请先设置分类根目录！")
            return

        if not os.path.exists(output_dir):
            messagebox.showwarning("警告", f"分类根目录不存在: {output_dir}")
            return

        self.log_box.delete(1.0, tk.END)
        self.log_box.insert(tk.END,
                            f"[{datetime.datetime.now().strftime('%H:%M:%S')}] 📋 查看状态 / Checking status...\n\n")

        # 在后台线程中执行状态检查
        threading.Thread(target=self.run_status_check, args=(output_dir,), daemon=True).start()

    def run_status_check(self, target_dir):
        """在后台线程中执行状态检查"""
        try:
            def log_callback(message):
                self.log_box.insert(tk.END, message)
                if self.auto_scroll:
                    self.log_box.see(tk.END)

            list_current_status(target_dir, log_callback)

            self.log_box.insert(tk.END, f"\n[{datetime.datetime.now().strftime('%H:%M:%S')}] 🎉 状态检查完成！\n")

        except Exception as e:
            self.log_box.insert(tk.END, f"[Error] 状态检查过程中发生错误: {e}\n")

    def remove_mappings(self):
        """移除所有映射"""
        output_dir = self.classify_dir.get().strip()
        if not output_dir:
            messagebox.showwarning("警告", "请先设置分类根目录！")
            return

        if not os.path.exists(output_dir):
            messagebox.showwarning("警告", f"分类根目录不存在: {output_dir}")
            return

        # 确认操作
        result = messagebox.askyesno("确认移除",
                                     f"将移除分类根目录中的所有映射链接：\n{output_dir}\n\n"
                                     "此操作不会影响原始项目文件，只删除符号链接。\n"
                                     "是否继续？")
        if not result:
            return

        self.log_box.delete(1.0, tk.END)
        self.log_box.insert(tk.END,
                            f"[{datetime.datetime.now().strftime('%H:%M:%S')}]   开始移除映射 / Starting mapping removal...\n")
        self.log_box.insert(tk.END, f"📁 目标目录 / Target directory: {output_dir}\n\n")

        # 在后台线程中执行移除
        threading.Thread(target=self.run_remove_mappings, args=(output_dir,), daemon=True).start()

    def run_remove_mappings(self, target_dir):
        """在后台线程中执行移除映射"""
        try:
            def log_callback(message):
                self.log_box.insert(tk.END, message)
                if self.auto_scroll:
                    self.log_box.see(tk.END)

            remove_all_mappings(target_dir, log_callback)

            # 显示完成消息
            self.log_box.insert(tk.END, f"\n[{datetime.datetime.now().strftime('%H:%M:%S')}] 🎉 映射移除完成！\n")

        except Exception as e:
            self.log_box.insert(tk.END, f"[Error] 移除映射过程中发生错误: {e}\n")

    # ------------------------------------------------------------
    #  备份还原功能方法 (统一备份)
    # ------------------------------------------------------------
    def list_backups(self, unified_backup_root):
        """扫描统一备份根目录下的 .unified_backup 文件夹，返回批次备份列表"""
        unified_backup_dir = os.path.join(unified_backup_root, ".unified_backup")
        backups = []
        if os.path.isdir(unified_backup_dir):
            for item in os.listdir(unified_backup_dir):
                # 检查是否为以 'backup_' 开头且是目录
                if item.startswith("backup_") and os.path.isdir(os.path.join(unified_backup_dir, item)):
                    backups.append(item)
        return sorted(backups, reverse=True)  # 最近的备份在前

    def refresh_backups_list(self):
        """刷新备份列表"""
        unified_backup_root = self.unified_backup_root.get().strip()
        self.backup_listbox.delete(0, tk.END)

        if not unified_backup_root or not os.path.isdir(unified_backup_root):
            self.backup_listbox.insert(tk.END, "[Warning] 请先选择有效的统一备份根目录")
            return

        backups = self.list_backups(unified_backup_root)

        if not backups:
            self.backup_listbox.insert(tk.END, "[Success] 目录中未找到任何批次备份。")
        else:
            for backup in backups:
                self.backup_listbox.insert(tk.END, backup)
            self.log_box.insert(tk.END,
                                f"\n[{datetime.datetime.now().strftime('%H:%M:%S')}] 🔄 备份列表刷新完成，找到 {len(backups)} 个批次备份。\n")
            self.log_box.see(tk.END)

    def start_restore_task(self):
        """启动还原任务"""
        unified_root = self.unified_backup_root.get().strip()
        selection = self.backup_listbox.curselection()

        if not unified_root or not os.path.isdir(unified_root):
            messagebox.showwarning("警告", "请先选择有效的统一备份根目录！")
            return

        if not selection:
            messagebox.showwarning("警告", "请先在列表中选择一个要还原的批次备份！")
            return

        backup_name = self.backup_listbox.get(selection[0])

        # 确认操作
        result = messagebox.askyesno("确认还原",
                                     f"您确定要将 **整个批次备份**：\n{backup_name}\n\n"
                                     f"还原到统一根目录：\n{unified_root}\n\n"
                                     "此操作将 **删除** 批次中所有项目的当前提取内容，并将备份内容移回。操作不可逆！\n"
                                     "是否继续？",
                                     icon="error")
        if not result:
            return

        self.log_box.insert(tk.END,
                            f"\n[{datetime.datetime.now().strftime('%H:%M:%S')}] ⏪ 启动批次还原任务: {backup_name}...\n")
        self.log_box.see(tk.END)

        threading.Thread(target=self.run_restore_process, args=(unified_root, backup_name), daemon=True).start()

    def run_restore_process(self, unified_root, backup_name):
        """在后台线程中执行还原操作"""
        try:
            def log_callback(message):
                self.log_box.insert(tk.END, message)
                if self.auto_scroll:
                    self.log_box.see(tk.END)

            self.restore_selected_backup(unified_root, backup_name, log_callback)

            # 还原完成后刷新列表
            self.root.after(100, self.refresh_backups_list)

        except Exception as e:
            self.log_box.insert(tk.END, f"[Error] 还原过程中发生严重错误: {e}\n")
            self.log_box.see(tk.END)

    def restore_selected_backup(self, unified_root, backup_name, log_callback):
        """将选中的批次备份还原到统一根目录"""
        unified_backup_dir = os.path.join(unified_root, ".unified_backup")
        batch_backup_path = os.path.join(unified_backup_dir, backup_name)

        if not os.path.isdir(batch_backup_path):
            log_callback(f"[Error] 错误: 批次备份目录不存在: {batch_backup_path}\n")
            return

        log_callback(f"⚙️  开始还原批次备份: {backup_name}...\n")

        # 遍历批次备份目录中的所有项目
        projects_to_restore = [d for d in os.listdir(batch_backup_path)
                               if os.path.isdir(os.path.join(batch_backup_path, d))]

        if not projects_to_restore:
            log_callback("[Warning]  此批次备份中未找到任何项目内容，跳过还原。\n")
            try:
                os.rmdir(batch_backup_path)
                log_callback(f"    已删除空的批次备份文件夹: {backup_name}\n")
            except:
                pass
            return

        log_callback(f"[Success] 发现 {len(projects_to_restore)} 个项目需要还原。\n")

        for project_name in projects_to_restore:
            project_path = os.path.join(unified_root, project_name)
            project_backup_path = os.path.join(batch_backup_path, project_name)

            log_callback(f"\n--- 还原项目: {project_name} ---\n")

            # 1. 清理当前提取内容 (在统一根目录下的项目路径)
            if not os.path.exists(project_path):
                log_callback(f"  [Warning]  项目目录 {project_name} 不存在，跳过清理。\n")
                continue

            log_callback("🧹 清理当前提取内容...\n")
            deleted_count = 0

            # 排除 .pkg 文件
            current_files = [f for f in os.listdir(project_path)
                             if not f.lower().endswith('.pkg')]

            for item in current_files:
                item_path = os.path.join(project_path, item)
                try:
                    if os.path.isdir(item_path):
                        shutil.rmtree(item_path)
                    else:
                        os.remove(item_path)
                    deleted_count += 1
                except Exception as e:
                    log_callback(f"  [Warning]  清理 {item} 失败: {e}\n")

            log_callback(f"  [Success] 成功清理 {deleted_count} 个文件/目录\n")

            # 2. 移动备份内容到项目目录
            log_callback(f"🚚 还原备份文件...\n")
            restored_count = 0

            for item in os.listdir(project_backup_path):
                src_path = os.path.join(project_backup_path, item)
                dest_path = os.path.join(project_path, item)
                try:
                    # 使用 shutil.move
                    shutil.move(src_path, dest_path)
                    restored_count += 1
                except Exception as e:
                    log_callback(f"  [Error] 还原 {item} 失败: {e}\n")

            log_callback(f"  [Success] 成功还原 {restored_count} 个文件/目录\n")

        # 3. 删除空的批次备份目录
        log_callback(f"\n  清理批次备份目录...\n")
        try:
            shutil.rmtree(batch_backup_path)  # 递归删除
            log_callback(f"  [Success] 已删除批次备份文件夹: {backup_name}\n")
        except Exception as e:
            log_callback(f"  [Warning]  删除批次备份文件夹 {backup_name} 失败 (可能非空): {e}\n")

        # 4. 检查是否需要删除 .unified_backup 根目录
        try:
            if not os.listdir(unified_backup_dir):
                os.rmdir(unified_backup_dir)
                log_callback(f"    已删除空的统一备份根目录: .unified_backup\n")
        except:
            pass  # 忽略错误

        log_callback(f"\n🎉 批次备份还原完成！统一根目录 {unified_root} 已成功还原到 {backup_name} 批次版本。\n")

    # ------------------------------------------------------------
    #  命令预览（Windows 格式）
    # ------------------------------------------------------------
    def update_preview(self, sample_pkg=None):
        try:
            if sample_pkg:
                cmd = self.build_command(sample_pkg)
            else:
                # 尝试构建一个更有意义的预览路径
                input_dir = self.input_entry.get().strip()
                output_dir = self.output_entry.get().strip()

                if input_dir and os.path.exists(input_dir):
                    # 尝试找到第一个 .pkg 文件作为样本 (不进行递归扫描，太耗时)
                    pkg_files = [os.path.join(input_dir, f) for f in os.listdir(input_dir) if
                                 f.lower().endswith(".pkg") and os.path.isfile(os.path.join(input_dir, f))]
                    if pkg_files:
                        cmd = self.build_command(pkg_files[0])
                else:
                    # 使用默认的假路径
                    fake_pkg = r"D:\Games\Steam\steamapps\workshop\content\431960\111111111\scene.pkg"
                    cmd = self.build_command(fake_pkg)

            self.cmd_preview.delete(1.0, tk.END)
            self.cmd_preview.insert(tk.END, " ".join(cmd))
        except Exception as e:
            pass  # 静默处理预览错误，避免干扰用户


if __name__ == "__main__":
    root = tk.Tk()
    app = RePKG_GUI(root)
    root.mainloop()
