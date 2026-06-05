import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import os
import codecs

# --- Configuration ---
IGNORE_LIST = [
    '.git', '.svn', '.idea', '.vscode', '_pycache_', 'node_modules',
    'vendor', 'target', 'build', 'dist', 'out', 'logs', 'temp',
    '.DS_Store', 'Thumbs.db', '.pyc', '.log', '*.tmp'
]

# THÊM: Danh sách các đuôi file cho phép đọc
ALLOWED_EXTENSIONS = ['.py', '.js']

MAX_TEXT_FILE_SIZE = 500 * 1024 # 500 KB

def is_ignored(path, ignore_list):
    path_parts = path.split(os.sep)
    for part in path_parts:
        if part in ignore_list:
            return True
        for pattern in ignore_list:
            if '*' in pattern:
                if partmatch_pattern(part, pattern):
                    return True
    return False

def partmatch_pattern(name, pattern):
    if pattern.startswith('*.'):
        return name.endswith(pattern[1:])
    if pattern.endswith('*'):
        return name.startswith(pattern[:-1])
    return name == pattern

def build_structure_string(directory, ignore_list, indent="", is_last=True):
    structure = []
    base_name = os.path.basename(directory) if directory not in ['.', '', os.sep] else os.path.basename(os.path.abspath(directory))
    if not base_name:
         base_name = os.path.abspath(directory)

    structure.append(indent + ("`-- " if is_last else "|-- ") + base_name + "/")

    try:
        items = os.listdir(directory)
        filtered_items = [item for item in sorted(items) if not is_ignored(os.path.join(directory, item), ignore_list)]
        
        # CHỈNH SỬA: Lọc thư mục và CHỈ lấy file .py, .js
        dirs = sorted([d for d in filtered_items if os.path.isdir(os.path.join(directory, d))])
        files = sorted([f for f in filtered_items if os.path.isfile(os.path.join(directory, f)) 
                        and any(f.endswith(ext) for ext in ALLOWED_EXTENSIONS)])
        
        sorted_filtered_items = dirs + files
    except Exception:
        return "\n".join(structure)

    num_filtered_items = len(sorted_filtered_items)
    for i, item in enumerate(sorted_filtered_items):
        path = os.path.join(directory, item)
        is_last_item_filtered = (i == num_filtered_items - 1)
        new_indent = indent + ("    " if is_last else "|   ")

        if os.path.isdir(path):
            # Nếu là thư mục, đệ quy tiếp
            subtree = build_structure_string(path, ignore_list, new_indent, is_last_item_filtered)
            # Chỉ thêm thư mục vào nếu nó không rỗng (có chứa file py/js bên trong) hoặc tùy chọn hiển thị hết
            structure.append(subtree)
        else:
             structure.append(new_indent + ("`-- " if is_last_item_filtered else "|-- ") + item)

    return "\n".join(structure)

def get_file_content_string(directory, ignore_list, max_size):
    content_string = []
    for dirpath, dirnames, filenames in os.walk(directory, topdown=True):
        dirnames[:] = [d for d in dirnames if not is_ignored(os.path.join(dirpath, d), ignore_list)]

        for filename in filenames:
            filepath = os.path.join(dirpath, filename)
            
            # CHỈNH SỬA: Kiểm tra nếu file KHÔNG thuộc danh sách cho phép thì bỏ qua
            if not any(filename.endswith(ext) for ext in ALLOWED_EXTENSIONS):
                continue
                
            if is_ignored(filepath, ignore_list):
                continue

            content_string.append(f"\n---\nFile: {filepath}\n---\n")

            try:
                file_size = os.path.getsize(filepath)
                if file_size > max_size:
                     content_string.append(f"[File too large - Content Skipped]\n")
                     continue

                with codecs.open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                     content_string.append(f.read())
            except Exception as e:
                content_string.append(f"[Error reading file: {e}]\n")

    return "".join(content_string)

# --- Các hàm GUI giữ nguyên logic, chỉ gọi các hàm core đã sửa ở trên ---

def generate_project_info(project_dir, output_filename, ignore_list=None, max_size=MAX_TEXT_FILE_SIZE):
    if ignore_list is None:
        ignore_list = IGNORE_LIST

    if not project_dir or not os.path.exists(project_dir):
        return "Error: Invalid directory."

    output_content = f"--- Project Structure (Filtered: {', '.join(ALLOWED_EXTENSIONS)}) ---\n\n"
    
    # Build structure
    output_content += build_structure_string(project_dir, ignore_list)
    
    output_content += "\n\n--- File Contents ---\n"
    output_content += get_file_content_string(project_dir, ignore_list, max_size)

    try:
        with open(output_filename, 'w', encoding='utf-8') as f:
            f.write(output_content)
        return f"Successfully generated '{output_filename}'"
    except Exception as e:
        return f"Error: {e}"

class ProjectInfoGeneratorApp:
    def __init__(self, root):
        self.root = root
        root.title("Py & Js Code Reader")
        root.geometry("600x350")

        self.style = ttk.Style()
        self.style.theme_use('clam')

        # Input
        self.frame_input = ttk.Frame(root, padding="10")
        self.frame_input.pack(fill=tk.X)
        ttk.Label(self.frame_input, text="Project Directory:").pack(side=tk.LEFT)
        self.entry_input = ttk.Entry(self.frame_input, width=40)
        self.entry_input.pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)
        ttk.Button(self.frame_input, text="Browse", command=self.browse_input_directory).pack(side=tk.LEFT)

        # Output
        self.frame_output = ttk.Frame(root, padding="10")
        self.frame_output.pack(fill=tk.X)
        ttk.Label(self.frame_output, text="Output File:").pack(side=tk.LEFT)
        self.entry_output = ttk.Entry(self.frame_output, width=40)
        self.entry_output.pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)
        ttk.Button(self.frame_output, text="Save As", command=self.browse_output_file).pack(side=tk.LEFT)

        # Generate
        self.button_generate = ttk.Button(root, text="Generate Project Info", command=self.start_processing)
        self.button_generate.pack(pady=20)

        # Status
        self.label_status = ttk.Label(root, text="Ready", foreground="blue")
        self.label_status.pack()

    def browse_input_directory(self):
        path = filedialog.askdirectory()
        if path:
            self.entry_input.delete(0, tk.END)
            self.entry_input.insert(0, path)
            if not self.entry_output.get():
                self.entry_output.insert(0, os.path.join(os.getcwd(), "project_code.txt"))

    def browse_output_file(self):
        path = filedialog.asksaveasfilename(defaultextension=".txt")
        if path:
            self.entry_output.delete(0, tk.END)
            self.entry_output.insert(0, path)

    def start_processing(self):
        project_dir = self.entry_input.get()
        output_file = self.entry_output.get()
        
        self.label_status.config(text="Processing...")
        self.root.update_idletasks()
        
        result = generate_project_info(project_dir, output_file)
        
        self.label_status.config(text=result)
        messagebox.showinfo("Result", result)

if __name__ == "__main__":
    import tkinter as tk
    root = tk.Tk()
    app = ProjectInfoGeneratorApp(root)
    root.mainloop()