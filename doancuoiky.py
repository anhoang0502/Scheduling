import sys
import json
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout,
    QWidget, QPushButton, QTableWidget, QTableWidgetItem,
    QMessageBox, QLabel, QLineEdit, QFormLayout, QFileDialog
)
from PyQt5.QtCore import Qt

# Cấu hình
MAX_DURATION_PER_SESSION = 5.0
MAX_STUDENTS_PER_SESSION = 8 
MAX_DAYS = 16
WEEKDAYS = ["Mon", "Tues", "Wed", "Thurs", "Fri", "Sat", "Sun"]

def ngay_cuoi_tuan(day):
    # day bắt đầu từ 0 (Mon), %7 = 5 là Sat, 6 là Sun
    return day % 7 in (5, 6)

# Chia môn thành các lượt thi <=150 SV, giữ danh sách student_ids theo từng lượt
def chia_luot_thi(ky_thi):
    luot_thi = []
    for mon in ky_thi:
        siso = mon["students"]
        # Nếu không có student_ids (ví dụ tải từ file), tạo mặc định sv1, sv2...
        student_ids = mon.get("student_ids", [f"sv{str(i+1).zfill(4)}" for i in range(siso)])
        so_luot = (siso + MAX_STUDENTS_PER_SESSION - 1) // MAX_STUDENTS_PER_SESSION
        for i in range(so_luot):
            sv_luot = student_ids[i*MAX_STUDENTS_PER_SESSION:(i+1)*MAX_STUDENTS_PER_SESSION]
            sv_count = len(sv_luot)
            luot_thi.append({
                "id": f'{mon["name"]} sess {i}',
                "name": mon["name"],
                "duration": float(mon["duration"]),
                "students": sv_count,
                "student_ids": sv_luot,
            })
    return luot_thi

# Kiểm tra xung đột student_ids trong ca thi hiện tại
def co_xung_dot(student_schedule, candidate_student_ids, day, session):
    scheduled_students = student_schedule.get((day, session), set())
    return bool(scheduled_students.intersection(candidate_student_ids))

def greedy_schedule(luot_thi):
    schedule = []
    ca_thi = {
        (day, session): 0.0
        for day in range(MAX_DAYS)
        for session in ([0, 1] if not ngay_cuoi_tuan(day) else [0])
    }
    student_schedule = {}

    missed = []

    for unit in luot_thi:
        placed = False
        for day in range(MAX_DAYS):
            if ngay_cuoi_tuan(day):
                continue
            for session in [0, 1]:
                if ca_thi[(day, session)] + unit["duration"] <= MAX_DURATION_PER_SESSION:
                    if not co_xung_dot(student_schedule, unit["student_ids"], day, session):
                        # Xếp được lượt thi
                        schedule.append((unit["id"], unit["name"], unit["duration"], day, session, unit["students"]))
                        ca_thi[(day, session)] += unit["duration"]
                        if (day, session) not in student_schedule:
                            student_schedule[(day, session)] = set()
                        student_schedule[(day, session)].update(unit["student_ids"])
                        placed = True
                        break
            if placed:
                break
        if not placed:
            missed.append(unit)

    return schedule, missed

class Giao_dien_lich_thi(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Exam Scheduler")
        self.setGeometry(100, 100, 1100, 650)
        self.exams = []
        self.exam_units = []
        self.solution = []
        self.init_ui()
        self.table.cellClicked.connect(self.show_student_ids)

    def init_ui(self):
        main_layout = QHBoxLayout()
        form_layout = QFormLayout()
        self.name_input = QLineEdit()
        self.students_input = QLineEdit()
        self.duration_input = QLineEdit()

        form_layout.addRow("Tên môn thi:", self.name_input)
        form_layout.addRow("Số sinh viên:", self.students_input)
        form_layout.addRow("Thời lượng (giờ):", self.duration_input)

        btn_add = QPushButton("Thêm môn thi")
        btn_add.clicked.connect(self.add_exam)
        form_layout.addRow(btn_add)

        btn_load = QPushButton("Tải môn thi từ file")
        btn_load.clicked.connect(self.load_exams_from_file)
        form_layout.addRow(btn_load)

        btn_schedule = QPushButton("Xếp lịch thi (Greedy)")
        btn_schedule.clicked.connect(self.schedule_exams)
        form_layout.addRow(btn_schedule)

        self.status_label = QLabel("Nhập môn thi hoặc tải từ file.")
        form_layout.addRow(self.status_label)

        left = QWidget()
        left.setLayout(form_layout)
        main_layout.addWidget(left, 1)

        self.table = QTableWidget(MAX_DAYS, 10)
        headers = ["Sáng"] * 5 + ["Chiều"] * 5
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setVerticalHeaderLabels([f"{WEEKDAYS[i % 7]}" for i in range(MAX_DAYS)])

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
            QMessageBox.warning(self, "Lỗi", "Dữ liệu không hợp lệ.")
            return
        if not name or students <= 0 or duration <= 0:
            QMessageBox.warning(self, "Lỗi", "Nhập thiếu hoặc sai.")
            return
        # Tạo danh sách student_ids cho môn mới thêm
        student_ids = [f"sv{str(i+1).zfill(4)}" for i in range(students)]
        self.exams.append({"name": name, "students": students, "duration": duration, "student_ids": student_ids})
        self.status_label.setText(f"Đã thêm môn: {name}")
        self.name_input.clear()
        self.students_input.clear()
        self.duration_input.clear()

    def load_exams_from_file(self):
        file, _ = QFileDialog.getOpenFileName(self, "Chọn file JSON", "", "JSON Files (*.json)")
        if not file:
            return
        try:
            with open(file, "r", encoding="utf-8") as f:
                data = json.load(f)
            for mon in data:
                if not all(k in mon for k in ("name", "students", "duration")):
                    raise ValueError("Thiếu dữ liệu.")
                # Nếu file không có student_ids, tự tạo
                if "student_ids" not in mon:
                    mon["student_ids"] = [f"sv{str(i+1).zfill(4)}" for i in range(mon["students"])]
            self.exams = data
            self.status_label.setText(f"Đã tải {len(data)} môn thi từ file.")
        except Exception as e:
            QMessageBox.warning(self, "Lỗi đọc file", str(e))

    def schedule_exams(self):
        self.exam_units = chia_luot_thi(self.exams)
        self.solution, missed = greedy_schedule(self.exam_units)
        if missed:
            self.status_label.setText(f"Không xếp được {len(missed)} lượt thi do xung đột hoặc thiếu ca thi.")
        else:
            self.status_label.setText("Xếp lịch thành công.")
        self.display_schedule()  # <-- thêm dòng này để hiển thị lịch lên bảng

    def display_schedule(self):
        self.table.clearContents()
        map_lich = {}
    # Mình cũng lưu student_ids ở đây theo key (day, session) để dễ truy xuất
        self.map_student_ids = {}

        for unit in self.solution:
            id_unit, name, duration, day, session, students = unit
            if (day, session) not in map_lich:
                map_lich[(day, session)] = []
                self.map_student_ids[(day, session)] = []

            map_lich[(day, session)].append((name, duration, students))
        # Lấy student_ids từ self.exam_units theo id_unit
        # exam_units = list dict {"id", "student_ids", ...}
            for eu in self.exam_units:
                if eu["id"] == id_unit:
                    self.map_student_ids[(day, session)].append(eu["student_ids"])
                    break

        for day in range(MAX_DAYS):
            for session in [0, 1]:
                key = (day, session)
                if key in map_lich:
                    for idx, (name, duration, sv) in enumerate(map_lich[key]):
                        if idx >= 5:
                            break
                        col = idx + (0 if session == 0 else 5)
                        item = QTableWidgetItem(name)
                        item.setToolTip(f"Môn: {name}\nThời lượng: {duration}h\nSV: {sv}")

                    # Gắn student_ids vào item (dạng list)
                        item.setData(Qt.UserRole, self.map_student_ids[key][idx])

                        item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                        self.table.setItem(day, col, item)
    def show_student_ids(self, row, column):
        item = self.table.item(row, column)
        if item:
            student_ids = item.data(Qt.UserRole)
            if student_ids:
                sv_text = "\n".join(student_ids)
                QMessageBox.information(self, "Danh sách sinh viên", f"Sinh viên trong lượt thi:\n{sv_text}")
            else:
                QMessageBox.information(self, "Thông báo", "Không có dữ liệu sinh viên.")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = Giao_dien_lich_thi()
    window.show()
    sys.exit(app.exec_())
