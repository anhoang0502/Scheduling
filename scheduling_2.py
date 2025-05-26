import sys
import json
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout,
    QWidget, QPushButton, QTableWidget, QTableWidgetItem,
    QMessageBox, QLabel, QLineEdit, QFormLayout, QFileDialog
)
from PyQt5.QtCore import Qt
from simpleai.search import SearchProblem, greedy

# Cấu hình chung
thoi_luong_ca_thi = 5.0  
so_sv_phong_thi = 30
so_phong_thi = 5
so_sv_mot_luot_thi = so_sv_phong_thi * so_phong_thi
WEEKDAYS = ["Mon", "Tues", "Wed", "Thurs", "Fri", "Sat", "Sun"]

# Hàm chia môn thi thành các lượt thi nhỏ
def chia_luot_thi(ky_thi):
    luot_thi = []
    for m in ky_thi:
        so_sv = m["students"]
        so_luot_thi = so_sv % so_sv_mot_luot_thi
        if so_luot_thi != 0:
            luotthi_mot_mon = (so_sv // so_sv_mot_luot_thi) + 1
        else:
            luotthi_mot_mon = so_sv // so_sv_mot_luot_thi
        for i in range(luotthi_mot_mon):
            if i < luotthi_mot_mon - 1:
                num_students = so_sv_mot_luot_thi
            else:
                num_students = so_sv - so_sv_mot_luot_thi * (luotthi_mot_mon - 1)
            luot_thi.append({
                "id": f'{m["name"]} sess {i}',
                "name": m["name"],
                "duration": float(m["duration"]),
                "students": num_students
            })
    return luot_thi

# Hàm kiểm tra ngày cuối tuần
def ngay_cuoi_tuan(days):
    return days % 7 in (5, 6)

# Bài toán xếp lịch
class Xep_Lich_Thi(SearchProblem):
    def __init__(self, luot_thi):
        self.luot_thi = luot_thi
        self.units = luot_thi
        self.max_days = 16
        super().__init__(initial_state=())

    def actions(self, state):
        da_xep_lich = {id for (id, _, _, _, _) in state}
        chua_xep = [x for x in self.units if x["id"] not in da_xep_lich]
        actions = []
        for x in chua_xep:
            for ngaythi in range(self.max_days):
                cathi = [0] if ngay_cuoi_tuan(ngaythi) else [0, 1]
                for ca in cathi:
                    actions.append((x["id"], x["name"], x["duration"], ngaythi, ca))
        return actions

    def result(self, state, action):
        unit_id, name, duration, ngaythi, ca = action
        tong_thoi_luong_hien_tai = sum(
            d for (_, _, d, dy, ss) in state if dy == ngaythi and ss == ca)
        if tong_thoi_luong_hien_tai + duration > thoi_luong_ca_thi:
            return state
        return state + ((unit_id, name, duration, ngaythi, ca),)

    def is_goal(self, state):
        return len(state) == len(self.units)

    def heuristic(self, trang_thai):
        so_luot_con_lai = len(self.units) - len(trang_thai)
        cac_ngay_da_dung = {ngay for (_, _, _, ngay, _) in trang_thai}
        so_ngay_da_dung = len(cac_ngay_da_dung)
        return so_luot_con_lai + so_ngay_da_dung  # Có thể chỉnh thành + 2 * so_ngay_da_dung để ưu tiên gom lịch hơn 
    
# Giao diện người dùng
class Giao_dien_lich_thi(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Exam Scheduler")
        self.setGeometry(100, 100, 1100, 650)

        self.exams = []
        self.exam_units = []
        self.solution = []

        self.init_ui()

    def init_ui(self):
        main_layout = QHBoxLayout()

        # Bên trái: nhập môn thi
        form_layout = QFormLayout()
        self.name_input = QLineEdit()
        self.students_input = QLineEdit()
        self.duration_input = QLineEdit()

        form_layout.addRow("Tên môn thi:", self.name_input)
        form_layout.addRow("Số sinh viên:", self.students_input)
        form_layout.addRow("Thời lượng (giờ, có thể lẻ):", self.duration_input)

        self.add_exam_btn = QPushButton("Thêm môn thi")
        self.add_exam_btn.clicked.connect(self.add_exam)
        form_layout.addRow(self.add_exam_btn)

        self.load_file_btn = QPushButton("Tải môn thi từ file")
        self.load_file_btn.clicked.connect(self.load_exams_from_file)
        form_layout.addRow(self.load_file_btn)

        self.schedule_btn = QPushButton("Xếp lịch thi")
        self.schedule_btn.clicked.connect(self.schedule_exams)
        form_layout.addRow(self.schedule_btn)

        self.status_label = QLabel("Nhập môn thi hoặc tải từ file.")
        form_layout.addRow(self.status_label)

        left_widget = QWidget()
        left_widget.setLayout(form_layout)
        main_layout.addWidget(left_widget, 1)

        # Bên phải: bảng hiển thị lịch thi
        self.table = QTableWidget(16, 10)
        headers = ["Sáng"] * 5 + ["Chiều"] * 5
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setVerticalHeaderLabels([f"{WEEKDAYS[i % 7]}" for i in range(16)])

        main_layout.addWidget(self.table, 3)

        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

    def add_exam(self):
        name = self.name_input.text().strip()
        try:
            students = int(self.students_input.text().strip())
            duration = float(self.duration_input.text().strip())
        except:
            QMessageBox.warning(self, "Lỗi nhập liệu", "Dữ liệu nhập vào không hợp lệ.")
            return

        if not name:
            QMessageBox.warning(self, "Lỗi nhập liệu", "Kiểm tra lại tên môn thi")
            return
        if students <= 0 or duration <= 0:
            QMessageBox.warning(self, "Lỗi nhập liệu", "Dữ liệu nhập vào không hợp lệ")
            return

        self.exams.append({"name": name, "students": students, "duration": duration})
        self.status_label.setText(f"Đã thêm môn: {name} ({students} sv, {duration}h)")
        self.name_input.clear()
        self.students_input.clear()
        self.duration_input.clear()

    def load_exams_from_file(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Chọn file exams.json", "", "JSON Files (*.json)")
        if not filename:
            return
        try:
            with open(filename, "r", encoding="utf-8") as f:
                data = json.load(f)
            #if not isinstance(data, list):
             #   raise ValueError("Dữ liệu không đúng định dạng danh sách.")
            for exam in data:
                if not all(k in exam for k in ("name", "students", "duration")):
                    raise ValueError("Thiếu trường name, students hoặc duration trong 1 môn.")
            self.exams = data
            self.status_label.setText(f"Đã tải {len(self.exams)} môn thi từ file.")
        except Exception as e:
            QMessageBox.warning(self, "Lỗi đọc file", f"Không thể tải file:\n{str(e)}")

    def schedule_exams(self):
        if not self.exams:
            QMessageBox.warning(self, "Chưa có môn thi", "Kiểm tra lại thông tin")
            return

        self.exam_units = chia_luot_thi(self.exams)
        problem = Xep_Lich_Thi(self.exam_units)
        result = greedy(problem)

        if result and problem.is_goal(result.state):
            self.status_label.setText("Xếp lịch thành công!")
            self.solution = result.state
        else:
            self.solution = result.state if result else ()
            unscheduled = len(self.exam_units) - len(self.solution)
            self.status_label.setText(f"Không thể xếp hết. Còn {unscheduled} lượt chưa xếp.")

        self.display_schedule()

    def display_schedule(self):
        self.table.clearContents()
        schedule_map = {}
        for _, name, duration, day, session in self.solution:
            key = (day, session)
            if key not in schedule_map:
                schedule_map[key] = []
            schedule_map[key].append((name, duration))

        for day in range(16):
            for session in [0, 1]:
                key = (day, session)
                if key in schedule_map:
                    exams_list = schedule_map[key]
                    for idx, (name, duration) in enumerate(exams_list):
                        if idx >= 5:
                            break
                        col = idx + (0 if session == 0 else 5)
                        item = QTableWidgetItem(name)  # Chỉ hiện tên môn thi
                        item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                    # Thêm tooltip
                        sv = self.get_students(name, duration)
                        item.setToolTip(f"Môn: {name}\nThời lượng: {duration} giờ\nSố SV: {sv}")
                        self.table.setItem(day, col, item)

    def get_students(self, name, duration):
        for unit in self.exam_units:
            if unit["name"] == name and unit["duration"] == duration:
                return unit["students"]
        return "?"


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = Giao_dien_lich_thi()
    window.show()
    sys.exit(app.exec_())
