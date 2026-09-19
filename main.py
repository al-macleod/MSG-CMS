import mimetypes
import os
import shutil
import sys

from PyQt6.QtCore import QThread, QTimer, Qt, QUrl, pyqtSlot
from PyQt6.QtGui import QFont, QKeySequence, QPixmap, QShortcut
from PyQt6.QtWidgets import (
    QApplication, QComboBox, QDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QMessageBox, QMainWindow, QPlainTextEdit, QPushButton, QSplitter, QStackedWidget, QFileDialog,
    QTextEdit, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget, QHeaderView, QSplashScreen,
    QGroupBox
)

CATEGORIES = ["Lecture Note", "Assignment / Lab", "Exam Prep", "Reference Material", "Project Draft"]


from database import DatabaseWorker, init_db
from dialogs import AIConfigurationPage, AISetupDialog, OnboardingDialog, QuickAddDialog, ResourceDialog, SettingsDialog, TaskDialog
from ollama_client import OllamaClient
from ui_components import action_button, card, metric_card, page_heading, pill


STYLE = """
QMainWindow,QDialog{background:#16181d;color:#f4f6f8;font-family:'Segoe UI',Arial}
QWidget{color:#f4f6f8}
QFrame#Header{background:#202226;border-bottom:1px solid #3b3e45}
QFrame#NavBar{background:#202226;border-bottom:1px solid #3b3e45}
QFrame#Footer{background:#202226;border-top:1px solid #3b3e45}
QFrame#Card,QFrame#MetricCard{background:#24262b;border:1px solid #3a3d44;border-radius:12px}
QFrame#MetricCard{border-top:3px solid #31d7e8}
QLabel#Title{font-size:20px;font-weight:700;color:#ffffff}
QLabel#Sub{font-size:11px;color:#31d7e8;font-weight:700;letter-spacing:2px}
QLabel#PageTitle{font-size:29px;font-weight:600;color:#ffffff}
QLabel#PageSubtitle,QLabel#CardSubtitle{font-size:13px;color:#9ba1aa}
QLabel#CardTitle{font-size:17px;font-weight:600;color:#ffffff}
QLabel#MetricValue{font-size:28px;font-weight:700}
QLabel#MetricLabel{font-size:12px;color:#aeb4bd}
QLabel#Pill{background:#343840;border-radius:10px;padding:4px 9px;color:#dfe3e8;font-size:11px}
QLabel#PreviewTitle{font-size:17px;font-weight:700;color:#ffffff}
QLabel#PreviewMeta{color:#31d7e8;font-size:12px}
QLabel#PreviewContent{color:#c5cbd3;line-height:1.4}
QLabel#DialogTitle{font-size:22px;font-weight:700;color:#ffffff}
QLineEdit,QComboBox,QTextEdit,QPlainTextEdit,QDateEdit,QSpinBox{background:#1d1f24;border:1px solid #484c55;border-radius:7px;color:#f4f6f8;padding:9px}
QLineEdit:focus,QComboBox:focus,QTextEdit:focus,QPlainTextEdit:focus{border:1px solid #31d7e8}
QPushButton{background:#30333a;border:1px solid #50545d;border-radius:7px;color:#f4f6f8;padding:9px 15px;font-weight:600}
QPushButton:hover{background:#3d414a;border-color:#31d7e8}
QPushButton#PrimaryButton{background:#31d7e8;border:1px solid #5ee6f2;color:#101417}
QPushButton#PrimaryButton:hover{background:#6be8f2}
QPushButton#SecondaryButton{background:#30333a}
QPushButton#Danger{background:#a93845;border-color:#d05b68}
QPushButton#Nav{border:0;border-radius:0;padding:13px 18px;background:transparent;color:#b5bac2}
QPushButton#Nav:checked,QPushButton#Nav:hover{background:#2b3037;color:#31d7e8;border-bottom:2px solid #31d7e8}
QPushButton#IconButton{border:0;background:transparent;font-size:22px;color:#aeb4bd}
QPushButton#IconButton:hover{color:#31d7e8}
QListWidget,QTreeWidget{background:#1d1f24;border:1px solid #3a3d44;border-radius:9px;padding:3px}
QListWidget::item,QTreeWidget::item{padding:10px;border-radius:6px}
QListWidget::item:selected,QTreeWidget::item:selected{background:#24555d;color:#ffffff}
QGroupBox{background:#24262b;border:1px solid #3a3d44;border-radius:9px;margin-top:10px;padding:14px;font-weight:600}
QGroupBox::title{subcontrol-origin:margin;left:12px;padding:0 5px;color:#31d7e8}
QTabWidget::pane{border:1px solid #3a3d44;border-radius:8px}
QTabBar::tab{padding:10px 18px;color:#aeb4bd}
QTabBar::tab:selected{color:#31d7e8;border-bottom:2px solid #31d7e8}
QSplitter::handle{background:#363940}
"""


class ChatPanel(QWidget):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.profile = None
        self.ollama = OllamaClient(self)
        self.ollama.response.connect(self.reply)
        self.ollama.error.connect(self.failure)
        layout = QVBoxLayout(self)
        self.history = QTextEdit()
        self.history.setReadOnly(True)
        layout.addWidget(self.history)
        row = QHBoxLayout()
        self.input = QLineEdit()
        self.input.setPlaceholderText("Ask your copilot about your notes...")
        self.input.returnPressed.connect(self.send)
        send = QPushButton("Send")
        send.setObjectName("Primary")
        send.clicked.connect(self.send)
        row.addWidget(self.input)
        row.addWidget(send)
        layout.addLayout(row)
        self.db.result.connect(self.handle_db)

    def set_profile(self, profile):
        self.profile = profile

    def load(self):
        self.db.request.emit("chat_history", None)

    @pyqtSlot(str, object)
    def handle_db(self, operation, data):
        if operation == "chat_history":
            self.history.clear()
            for role, content, _ in data:
                self.history.append(f"<b>{'You' if role == 'user' else 'Copilot'}:</b> {content}")

    def send(self):
        prompt = self.input.text().strip()
        if not prompt or not self.profile:
            return
        self.input.clear()
        self.history.append(f"<b>You:</b> {prompt}")
        self.db.request.emit("save_chat", ("user", prompt))
        self.ollama.ask(self.profile[12], self.profile[13], prompt, self.profile[9], self.profile[10])

    def reply(self, _, text):
        self.history.append(f"<b>Copilot:</b> {text}")
        self.db.request.emit("save_chat", ("assistant", text))

    def failure(self, message):
        self.history.append(f"<b>Copilot:</b> <span style='color:#fca5a5'>{message}</span>")


class MainWindow(QMainWindow):
    def __init__(self, db):
        super().__init__(); self.db=db; self.profile=None; self.note_id=None; self.setWindowTitle("MSG Academic Workspace"); self.resize(1400,900); self.build()
        self.smart_ai=OllamaClient(self); self.smart_ai.response.connect(self.show_smart_result); self.smart_ai.error.connect(self.show_smart_error)
        db.result.connect(self.handle); db.error.connect(self.database_error)
        QShortcut(QKeySequence("Ctrl+S"),self,activated=self.save_note); QShortcut(QKeySequence("Ctrl+N"),self,activated=self.new_note)

    def build(self):
        root=QWidget(); self.setCentralWidget(root); outer=QVBoxLayout(root); outer.setContentsMargins(0,0,0,0)
        header=QFrame(); header.setObjectName("Header"); h=QHBoxLayout(header); h.setContentsMargins(22,12,22,12); title=QVBoxLayout()
        t=QLabel("MSG ACADEMIC WORKSPACE"); t.setObjectName("Title"); s=QLabel("PERSONAL KNOWLEDGE + AI COPILOT"); s.setObjectName("Sub"); title.addWidget(t); title.addWidget(s); h.addLayout(title); h.addStretch()
        self.profile_label=QLabel("Workspace"); h.addWidget(self.profile_label); outer.addWidget(header)
        body=QVBoxLayout(); navbar=QFrame(); navbar.setObjectName("NavBar"); nav_layout=QHBoxLayout(navbar); nav_layout.setContentsMargins(18,0,18,0)
        self.nav_buttons=[]
        for text,idx in [("Dashboard",0),("Courses",1),("Notes",2),("Tasks",3),("Resources",4),("Analytics",5),("Settings",6),("AI",7)]:
            b=QPushButton(text); b.setObjectName("Nav"); b.setCheckable(True); b.clicked.connect(lambda _,i=idx:self.navigate(i)); nav_layout.addWidget(b); self.nav_buttons.append(b)
        nav_layout.addStretch()
        self.quick=action_button("+ Quick Add", True); self.quick.clicked.connect(self.open_quick_add); nav_layout.addWidget(self.quick)
        chat_button=action_button("Copilot"); chat_button.clicked.connect(lambda:self.pages.setCurrentIndex(8)); nav_layout.addWidget(chat_button)
        body.addWidget(navbar)
        self.pages=QStackedWidget()
        self.pages.addWidget(self.dashboard_page())
        self.pages.addWidget(self.courses_page())
        self.pages.addWidget(self.notes_page())
        self.pages.addWidget(self.tasks_page())
        self.pages.addWidget(self.resources_page())
        self.pages.addWidget(self.analytics_page())
        self.pages.addWidget(self.settings_page())
        self.pages.addWidget(self.ai_configuration_page())
        self.pages.addWidget(self.chat_page())
        self.pages.currentChanged.connect(self.update_navigation)
        body.addWidget(self.pages,1); outer.addLayout(body,1)
        footer=QFrame(); footer.setObjectName("Footer"); fl=QHBoxLayout(footer); self.status=QLabel("Ready"); fl.addWidget(self.status); fl.addStretch(); fl.addWidget(QLabel("Local-first workspace")); outer.addWidget(footer); self.nav_buttons[0].setChecked(True)

    def navigate(self, index):
        self.pages.setCurrentIndex(index)
        self.status.setText(f"{self.nav_buttons[index].text()} workspace ready")

    def update_navigation(self, index):
        for button in self.nav_buttons:
            button.setChecked(False)
        if 0 <= index < len(self.nav_buttons):
            self.nav_buttons[index].setChecked(True)

    def database_error(self, operation, message):
        self.status.setText(f"Could not complete {operation}: {message}")
        self.status.setStyleSheet("color:#fca5a5;font-weight:700;")
        QTimer.singleShot(7000, lambda: self.status.setStyleSheet(""))

    def dashboard_page(self):
        page=QWidget(); layout=QVBoxLayout(page); layout.setContentsMargins(28,24,28,24)
        layout.addWidget(page_heading("My Dashboard", "A calm overview of your courses, notes, and next actions."))
        toolbar=QHBoxLayout(); toolbar.addStretch(); quick=action_button("+ Quick Add Note", True); quick.clicked.connect(self.open_quick_add); toolbar.addWidget(quick); layout.addLayout(toolbar)
        metrics=QHBoxLayout(); self.dashboard_metrics=metrics
        for label,value in [("Courses","0"),("Notes","0"),("Characters","0"),("Active today","0")]:
            metrics.addWidget(metric_card(label,value))
        layout.addLayout(metrics)
        content=QHBoxLayout()
        courses_frame,courses_layout=card("My Courses","Jump back into your current learning areas")
        self.dashboard_courses=QVBoxLayout(); courses_layout.addLayout(self.dashboard_courses)
        content.addWidget(courses_frame,2)
        recent_frame,recent_layout=card("Recent Activity","Your latest note updates")
        self.dashboard_activity=QVBoxLayout(); recent_layout.addLayout(self.dashboard_activity)
        content.addWidget(recent_frame,1)
        layout.addLayout(content,1)
        bottom=QHBoxLayout()
        deadlines,_=card("Next up","Tasks and deadlines will appear here as task storage is enabled.")
        deadlines.layout().addWidget(pill("No deadlines yet"))
        bottom.addWidget(deadlines)
        tips,_=card("Workspace tip","Use Quick Add to capture a note without leaving your dashboard.")
        tips.layout().addWidget(pill("Capture momentum"))
        bottom.addWidget(tips)
        layout.addLayout(bottom)
        return page

    def tasks_page(self):
        page=QWidget(); layout=QVBoxLayout(page); layout.setContentsMargins(28,24,28,24)
        layout.addWidget(page_heading("Tasks", "Keep upcoming work visible alongside your notes."))
        toolbar=QHBoxLayout(); add=action_button("+ Add task", True); add.clicked.connect(self.add_task); toolbar.addStretch(); toolbar.addWidget(add); layout.addLayout(toolbar)
        self.tasks_list=QListWidget(); self.tasks_list.itemDoubleClicked.connect(self.toggle_task); layout.addWidget(self.tasks_list); return page

    def resources_page(self):
        page=QWidget(); layout=QVBoxLayout(page); layout.setContentsMargins(28,24,28,24)
        layout.addWidget(page_heading("Resources","Keep useful links, references, and study material close at hand."))
        toolbar=QHBoxLayout(); add=action_button("+ Add resource", True); add.clicked.connect(self.add_resource); toolbar.addStretch(); toolbar.addWidget(add); layout.addLayout(toolbar)
        self.resources_list=QListWidget(); layout.addWidget(self.resources_list); return page

    def courses_page(self):
        page=QWidget(); layout=QVBoxLayout(page); layout.setContentsMargins(28,24,28,24)
        layout.addWidget(page_heading("Courses","Organize your academic workspace by course and module."))
        self.course_cards=QVBoxLayout()
        frame,frame_layout=card("Course library","Your courses will appear here as cards.")
        frame_layout.addLayout(self.course_cards)
        layout.addWidget(frame); layout.addStretch()
        return page

    def ai_configuration_page(self):
        self.ai_config=AIConfigurationPage(self.profile); self.ai_config.saved.connect(self.save_ai); return self.ai_config

    def notes_page(self):
        page=QWidget(); layout=QVBoxLayout(page); top=QHBoxLayout(); self.search=QLineEdit(); self.search.setPlaceholderText("Search all notes, tags, and content..."); self.search.textChanged.connect(lambda:self.db.request.emit("tree",self.search.text())); top.addWidget(self.search); new=QPushButton("+ New note"); new.setObjectName("Primary"); new.clicked.connect(self.new_note); top.addWidget(new); layout.addLayout(top)
        split=QSplitter(); self.note_list=QTreeWidget(); self.note_list.setHeaderLabels(["Title","Category","Course","Updated"]); self.note_list.header().setSectionResizeMode(0,QHeaderView.ResizeMode.Stretch); self.note_list.itemClicked.connect(self.open_tree_note); split.addWidget(self.note_list)
        editor=QWidget(); el=QVBoxLayout(editor); meta=QHBoxLayout(); self.title=QLineEdit(); self.title.setPlaceholderText("Note title"); self.course=QComboBox(); self.category=QComboBox(); self.category.addItems(CATEGORIES); meta.addWidget(self.title,3); meta.addWidget(self.course,2); meta.addWidget(self.category,2); el.addLayout(meta)
        tags=QLineEdit(); tags.setPlaceholderText("Tags, comma-separated"); self.tags=tags; el.addWidget(tags)
        toolbar=QHBoxLayout(); self.mode=QComboBox(); self.mode.addItems(["Rich Text","Code"]); self.mode.currentIndexChanged.connect(self.toggle_editor); toolbar.addWidget(QLabel("Editor:")); toolbar.addWidget(self.mode)
        self.bold_button=QPushButton("B"); self.bold_button.setToolTip("Bold"); self.bold_button.clicked.connect(lambda: self.rich.setFontWeight(QFont.Weight.Bold))
        italic=QPushButton("I"); italic.setToolTip("Italic"); italic.clicked.connect(lambda: self.rich.setFontItalic(not self.rich.fontItalic()))
        bullet=QPushButton("• List"); bullet.clicked.connect(lambda: self.rich.insertPlainText("\n• "))
        favorite=QPushButton("☆ Favorite"); favorite.clicked.connect(self.toggle_favorite)
        duplicate=QPushButton("Duplicate"); duplicate.clicked.connect(lambda:self.db.request.emit("duplicate_note", self.note_id) if self.note_id else None)
        archive=QPushButton("Archive"); archive.clicked.connect(lambda:self.db.request.emit("set_note_state", ("archive", True, self.note_id)) if self.note_id else None)
        smart_summary=QPushButton("Smart summary"); smart_summary.clicked.connect(lambda:self.smart_note("summary"))
        smart_points=QPushButton("Key points"); smart_points.clicked.connect(lambda:self.smart_note("key points"))
        smart_questions=QPushButton("Study questions"); smart_questions.clicked.connect(lambda:self.smart_note("study questions"))
        smart_actions=QPushButton("Action items"); smart_actions.clicked.connect(lambda:self.smart_note("action items"))
        attach=QPushButton("Attach file"); attach.clicked.connect(self.attach_file)
        remove_attach=QPushButton("Remove attachment"); remove_attach.clicked.connect(self.remove_attachment)
        toolbar.addWidget(self.bold_button); toolbar.addWidget(italic); toolbar.addWidget(bullet); toolbar.addWidget(favorite); toolbar.addWidget(duplicate); toolbar.addWidget(archive); toolbar.addWidget(smart_summary); toolbar.addWidget(smart_points); toolbar.addWidget(smart_questions); toolbar.addWidget(smart_actions); toolbar.addWidget(attach); toolbar.addWidget(remove_attach); toolbar.addStretch(); el.addLayout(toolbar)
        self.rich=QTextEdit(); self.code=QPlainTextEdit(); self.code.setFont(QFont("Consolas",10)); el.addWidget(self.rich); el.addWidget(self.code); self.code.hide()
        self.attachments_list=QListWidget(); self.attachments_list.itemDoubleClicked.connect(self.open_attachment); el.addWidget(self.attachments_list)
        actions=QHBoxLayout(); save=QPushButton("Save note"); save.setObjectName("Primary"); save.clicked.connect(self.save_note); delete=QPushButton("Delete note"); delete.setObjectName("Danger"); delete.clicked.connect(self.delete_note); actions.addWidget(save); actions.addWidget(delete); actions.addStretch(); el.addLayout(actions); split.addWidget(editor); split.setSizes([500,900]); layout.addWidget(split); self.db.request.emit("courses",None); return page

    def analytics_page(self):
        page=QWidget(); layout=QVBoxLayout(page); layout.setContentsMargins(28,24,28,24); layout.addWidget(page_heading("Usage Analytics","See how your knowledge base is growing."))
        self.metrics=QGridLayout(); layout.addLayout(self.metrics); self.breakdown=QListWidget(); layout.addWidget(QLabel("Notes by category")); layout.addWidget(self.breakdown); self.activity=QListWidget(); layout.addWidget(QLabel("Recent activity")); layout.addWidget(self.activity); return page

    def chat_page(self):
        self.chat=ChatPanel(self.db); return self.chat

    def settings_page(self):
        page=QWidget(); layout=QVBoxLayout(page); layout.setContentsMargins(28,24,28,24); title=QLabel("Settings"); title.setObjectName("PageTitle"); layout.addWidget(title)
        button=QPushButton("Open full-screen settings"); button.setObjectName("Primary"); button.clicked.connect(self.configure); layout.addWidget(button)
        info=QLabel("Use the full-screen workspace to edit your profile, configure AI, review privacy controls, and prepare appearance preferences."); info.setWordWrap(True); info.setStyleSheet("color:#94a3b8"); layout.addWidget(info)
        data_frame,data_layout=card("Data portability","Move or protect your local workspace.")
        export=QPushButton("Export workspace JSON"); export.clicked.connect(self.export_data)
        import_button=QPushButton("Import workspace JSON"); import_button.clicked.connect(self.import_data)
        backup=QPushButton("Create database backup"); backup.clicked.connect(self.backup_data)
        data_layout.addWidget(export); data_layout.addWidget(import_button); data_layout.addWidget(backup); layout.addWidget(data_frame); layout.addStretch(); return page

    def toggle_editor(self):
        is_code=self.mode.currentIndex()==1; self.rich.setVisible(not is_code); self.code.setVisible(is_code)
        self.bold_button.setEnabled(not is_code)

    def open_tree_note(self,item,_):
        self.note_id=item.data(0,Qt.ItemDataRole.UserRole); self.db.request.emit("note",self.note_id); self.db.request.emit("attachments",self.note_id)

    def new_note(self):
        self.note_id=None; self.title.clear(); self.tags.clear(); self.rich.clear(); self.code.clear(); self.attachments_list.clear(); self.status.setText("New note draft")

    def save_note(self):
        if not self.title.text().strip() or self.course.currentData() is None:
            QMessageBox.warning(self,"Validation","Choose a title and course."); return
        content=self.code.toPlainText() if self.mode.currentIndex()==1 else self.rich.toHtml()
        self.db.request.emit("save_note",(self.note_id,self.course.currentData(),self.title.text().strip(),self.category.currentText(),content,self.tags.text().strip(),"code" if self.mode.currentIndex() else "rich"))

    def open_course(self, course_id):
        self.pages.setCurrentIndex(2)
        self.db.request.emit("tree", {"query": self.search.text(), "course_id": course_id})

    def smart_note(self, action):
        content = self.code.toPlainText() if self.mode.currentIndex() else self.rich.toPlainText()
        if not content.strip():
            QMessageBox.information(self, "Smart notes", "Add some note content first.")
            return
        prompts = {
            "summary": "Summarize this academic note in five concise bullets and include a one-sentence takeaway.",
            "key points": "Extract the most important concepts, definitions, and likely exam topics from this academic note.",
            "study questions": "Create 6 study questions from this academic note, mixing recall and application. Include short answer keys.",
            "action items": "Extract concrete action items from this note. Return a checklist with an owner or deadline only when explicitly present.",
        }
        self.smart_action = action
        self.smart_ai.ask(self.profile[12], self.profile[13], f"{prompts[action]}\n\nNOTE:\n{content}", self.profile[9], self.profile[10])
        self.status.setText("Smart notes is thinking...")

    def show_smart_result(self, _, text):
        self.status.setText("Smart notes ready")
        self.status.setStyleSheet("color:#86efac;font-weight:700;")
        QMessageBox.information(self, f"Smart {self.smart_action}", text)

    def show_smart_error(self, message):
        self.status.setText("Smart notes unavailable")
        self.status.setStyleSheet("color:#fca5a5;font-weight:700;")
        QMessageBox.warning(self, "Smart notes", message)

    def attach_file(self):
        if not self.note_id:
            QMessageBox.information(self, "Attachments", "Save the note before attaching a file.")
            return
        source, _ = QFileDialog.getOpenFileName(self, "Attach document", "", "Documents (*.pdf *.doc *.docx *.txt *.md *.png *.jpg *.jpeg *.ppt *.pptx *.xls *.xlsx);;All files (*)")
        if not source:
            return
        target_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "attachments")
        os.makedirs(target_dir, exist_ok=True)
        target = os.path.join(target_dir, f"{self.note_id}_{os.path.basename(source)}")
        shutil.copy2(source, target)
        self.db.request.emit("save_attachment", (self.note_id, os.path.basename(source), target,
                                                  mimetypes.guess_type(source)[0] or "application/octet-stream",
                                                  os.path.getsize(target)))

    def open_attachment(self, item):
        path = item.data(Qt.ItemDataRole.UserRole)
        if path and os.path.exists(path):
            from PyQt6.QtGui import QDesktopServices
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def remove_attachment(self):
        item = self.attachments_list.currentItem()
        if not item:
            return
        attachment_id = item.data(Qt.ItemDataRole.UserRole + 1)
        path = item.data(Qt.ItemDataRole.UserRole)
        self.db.request.emit("delete_attachment", attachment_id)
        if path and os.path.exists(path):
            os.remove(path)
        self.attachments_list.takeItem(self.attachments_list.row(item))

    def toggle_favorite(self):
        if self.note_id:
            self.db.request.emit("set_note_state", ("favorite", True, self.note_id))

    def export_data(self):
        path,_=QFileDialog.getSaveFileName(self,"Export workspace","","JSON files (*.json)")
        if path: self.db.request.emit("export_data",path)

    def import_data(self):
        path,_=QFileDialog.getOpenFileName(self,"Import workspace","","JSON files (*.json)")
        if path: self.db.request.emit("import_data",path)

    def backup_data(self):
        path,_=QFileDialog.getSaveFileName(self,"Backup database","","SQLite files (*.db)")
        if path: self.db.request.emit("backup",path)

    def delete_note(self):
        if self.note_id and QMessageBox.question(self,"Delete note","Delete this note permanently?")==QMessageBox.StandardButton.Yes: self.db.request.emit("delete_note",self.note_id)

    def open_chat(self):
        dialog=QDialog(self); dialog.setWindowTitle("Copilot chat"); dialog.resize(620,600); lay=QVBoxLayout(dialog); panel=ChatPanel(self.db); panel.set_profile(self.profile); lay.addWidget(panel); panel.load(); dialog.exec()

    def open_quick_add(self):
        self.db.request.emit("courses_for_quick_add", None)

    def save_quick_note(self, data):
        if data["kind"] == "note":
            self.db.request.emit("save_note", (None, data["course_id"], data["title"], data["category"], data["content"], data["tags"], "rich"))
        elif data["kind"] == "task":
            self.db.request.emit("save_task", (None, data["course_id"], data["title"], data["description"], "", data["priority"], "Open"))
        else:
            self.db.request.emit("save_resource", (None, data["course_id"], data["title"], "", data["description"], data["tags"]))

    def add_task(self):
        dialog=TaskDialog(getattr(self, "quick_add_courses", []), self)
        dialog.saved.connect(lambda data: self.db.request.emit("save_task", data))
        dialog.exec()

    def toggle_task(self, item):
        task_id=item.data(Qt.ItemDataRole.UserRole)
        completed=item.text().startswith("✓")
        self.db.request.emit("toggle_task", (task_id, not completed))

    def add_resource(self):
        dialog=ResourceDialog(getattr(self, "quick_add_courses", []), parent=self)
        dialog.saved.connect(lambda data: self.db.request.emit("save_resource", data))
        dialog.exec()

    def configure(self):
        dialog=SettingsDialog(self.profile,self)
        dialog.profile_saved.connect(self.save_profile)
        dialog.ai_saved.connect(self.save_ai)
        dialog.exec()

    def save_ai(self, data):
        p=list(self.profile); p[8]=data["ai_name"]; p[9]=data["system_prompt"]; p[10]=data["persona"]; p[11]=data["memory_enabled"]; p[12]=data["ollama_url"]; p[13]=data["ollama_model"]; self.profile=tuple(p); self.chat.set_profile(self.profile); self.ai_config = getattr(self, "ai_config", None); self.db.request.emit("save_profile",tuple(p[:8]+p[8:14]))

    def save_profile(self, data):
        p=list(self.profile)
        for index, key in [(0, "first_name"), (2, "email"), (3, "gender"), (4, "hobbies"), (5, "employment"), (6, "goals")]:
            p[index]=data[key]
        self.profile=tuple(p)
        self.profile_label.setText(f"Welcome, {p[0] or 'there'}")
        self.db.request.emit("save_profile",tuple(p[:8]+p[8:14]))

    @pyqtSlot(str,object)
    def handle(self,op,data):
        if op=="initialize": self.db.request.emit("profile",None); self.db.request.emit("tree",""); self.db.request.emit("analytics",None); self.db.request.emit("courses",None); self.db.request.emit("tasks",None); self.db.request.emit("resources",None)
        elif op=="profile":
            self.profile=data; self.profile_label.setText(f"Welcome, {data[0] or 'there'}"); self.chat.set_profile(data); self.ai_config.set_profile(data)
            if not data[14]:
                dialog=OnboardingDialog(data,self); dialog.completed.connect(self.save_onboarding); dialog.exec()
            else: self.chat.load()
        elif op=="save_profile": self.status.setText("Settings saved")
        elif op=="courses":
            self.course.clear()
            for cid,code,name in data: self.course.addItem(f"[{code}] {name}",cid)
            while self.course_cards.count():
                item=self.course_cards.takeAt(0)
                if item.widget(): item.widget().deleteLater()
            for cid,code,name in data:
                frame,frame_layout=card(f"[{code}] {name}", "Course workspace")
                open_notes=QPushButton("Open notes"); open_notes.clicked.connect(lambda _,course_id=cid:self.open_course(course_id))
                frame_layout.addWidget(open_notes)
                self.course_cards.addWidget(frame)
            self.quick_add_courses=data
        elif op=="courses_for_quick_add":
            dialog=QuickAddDialog(data if data is not None else getattr(self, "quick_add_courses", []), self)
            dialog.note_created.connect(self.save_quick_note)
            dialog.exec()
        elif op=="tasks":
            self.tasks_list.clear()
            for task_id,title,description,due,priority,status,course in data:
                item=QListWidgetItem(f"{'✓ ' if status == 'Completed' else ''}{title}  •  {course}  •  {due or 'No due date'}  •  {priority}")
                item.setData(Qt.ItemDataRole.UserRole, task_id); self.tasks_list.addItem(item)
        elif op=="resources":
            self.resources_list.clear()
            for resource_id,title,url,description,tags,course in data:
                item=QListWidgetItem(f"{title}  •  {course}  •  {url or 'No URL'}")
                item.setData(Qt.ItemDataRole.UserRole, resource_id); self.resources_list.addItem(item)
        elif op=="tree":
            self.note_list.clear()
            for nid,title,cat,updated,course in data:
                item=QTreeWidgetItem([title,cat,course or "",updated or ""]); item.setData(0,Qt.ItemDataRole.UserRole,nid); self.note_list.addTopLevelItem(item)
        elif op=="note" and data:
            nid,cid,title,cat,content,tags,mode,updated,_=data; self.note_id=nid; self.title.setText(title); self.tags.setText(tags or ""); self.category.setCurrentText(cat); self.course.setCurrentIndex(self.course.findData(cid)); self.mode.setCurrentIndex(1 if mode=="code" else 0); (self.code.setPlainText(content or "") if mode=="code" else self.rich.setHtml(content or ""))
        elif op=="attachments":
            self.attachments_list.clear()
            for attachment_id,name,path,mime,size,created in data:
                item=QListWidgetItem(f"{name}  •  {size // 1024} KB")
                item.setData(Qt.ItemDataRole.UserRole, path); item.setData(Qt.ItemDataRole.UserRole + 1, attachment_id); self.attachments_list.addItem(item)
        elif op=="course_overview":
            if data:
                self.status.setText(f"{data[1]}: {data[3]} notes, {data[4]} tasks, {data[5]} resources")
        elif op in ("save_note","delete_note","save_task","save_resource","toggle_task","duplicate_note","set_note_state"):
            self.status.setText("Note saved" if op=="save_note" else "Note deleted"); self.db.request.emit("tree",self.search.text()); self.db.request.emit("analytics",None)
            self.db.request.emit("tasks",None); self.db.request.emit("resources",None)
            if op=="delete_note": self.new_note()
        elif op=="analytics":
            totals,categories,activity,open_tasks,completed_tasks,resources,favorites=data
            while self.metrics.count():
                item=self.metrics.takeAt(0)
                if item.widget(): item.widget().deleteLater()
            labels=[("Total notes",totals[0]),("Words / chars",totals[1]),("Courses used",totals[2])]
            for col,(label,value) in enumerate(labels):
                box=QGroupBox(label); lay=QVBoxLayout(box); value_label=QLabel(str(value)); value_label.setObjectName("MetricValue"); lay.addWidget(value_label); self.metrics.addWidget(box,0,col)
            if hasattr(self, "dashboard_metrics"):
                dashboard_values=[totals[2], totals[0], totals[1], len(activity)]
                for index,value in enumerate(dashboard_values):
                    metric=self.dashboard_metrics.itemAt(index).widget().findChild(QLabel, "MetricValue")
                    if metric: metric.setText(str(value))
            while self.dashboard_activity.count():
                item=self.dashboard_activity.takeAt(0)
                if item.widget(): item.widget().deleteLater()
            for day,count in activity[:4]:
                self.dashboard_activity.addWidget(QLabel(f"{day}  •  {count} note update(s)"))
            self.breakdown.clear(); [self.breakdown.addItem(f"{cat}: {count}") for cat,count in categories]
            self.breakdown.addItem(f"Open tasks: {open_tasks}")
            self.breakdown.addItem(f"Completed tasks: {completed_tasks}")
            self.breakdown.addItem(f"Resources: {resources}")
            self.breakdown.addItem(f"Favorite notes: {favorites}")
            self.activity.clear(); [self.activity.addItem(f"{day}: {count} note update(s)") for day,count in activity]

    def save_onboarding(self,data):
        p=list(self.profile); p[:8]=[data[k] for k in ["first_name","dob","email","gender","hobbies","employment","goals","mental_health"]]; self.profile=tuple(p); self.ai_config.set_profile(self.profile); self.configure(); self.db.request.emit("save_profile",tuple(p[:8]+p[8:14]))


def main():
    app=QApplication(sys.argv); app.setStyleSheet(STYLE); init_db()
    splash=QSplashScreen(QPixmap(420,180)); splash.show(); app.processEvents()
    thread=QThread(); db=DatabaseWorker(); db.moveToThread(thread); db.request.connect(db.execute); thread.start()
    window=MainWindow(db); window.show(); db.result.connect(lambda op,_: splash.finish(window) if op=="initialize" else None)
    db.request.emit("initialize",None); app.aboutToQuit.connect(thread.quit); sys.exit(app.exec())


if __name__=="__main__": main()
