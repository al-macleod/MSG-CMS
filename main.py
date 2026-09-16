import sys

from PyQt6.QtCore import pyqtSlot
from PyQt6.QtGui import QFont, QKeySequence, QPixmap, QShortcut
from PyQt6.QtWidgets import (
    QApplication, QComboBox, QDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QMessageBox, QMainWindow, QPlainTextEdit, QPushButton, QSplitter, QStackedWidget,
    QTextEdit, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget, QHeaderView, QSplashScreen,
    QGroupBox
)

CATEGORIES = ["Lecture Note", "Assignment / Lab", "Exam Prep", "Reference Material", "Project Draft"]


from database import DatabaseWorker, init_db
from dialogs import AISetupDialog, OnboardingDialog
from ollama_client import OllamaClient


STYLE = """
QMainWindow,QDialog{background:#0f172a;color:#e2e8f0;font-family:'Segoe UI',Arial}
QWidget{color:#e2e8f0} QFrame#Header{background:#111827;border-bottom:1px solid #334155}
QFrame#Sidebar{background:#0b1220;border-right:1px solid #334155}
QFrame#Footer{background:#0b1220;border-top:1px solid #334155}
QLabel#Title{font-size:20px;font-weight:700;color:#f8fafc} QLabel#Sub{font-size:11px;color:#7dd3fc;font-weight:700;letter-spacing:2px}
QLabel#Section{font-size:16px;font-weight:700;color:#f8fafc} QLabel#Metric{font-size:27px;font-weight:700;color:#7dd3fc}
QLineEdit,QComboBox,QTextEdit,QPlainTextEdit,QDateEdit,QSpinBox{background:#0b1220;border:1px solid #334155;border-radius:8px;color:#e2e8f0;padding:8px}
QLineEdit:focus,QComboBox:focus,QTextEdit:focus,QPlainTextEdit:focus{border:1px solid #38bdf8}
QPushButton{background:#1e293b;border:1px solid #475569;border-radius:8px;color:#f8fafc;padding:9px 14px;font-weight:600}
QPushButton:hover{background:#334155;border-color:#7dd3fc} QPushButton#Primary{background:#2563eb;border-color:#38bdf8}
QPushButton#Danger{background:#b91c1c;border-color:#f87171} QPushButton#Nav{border:0;text-align:left;padding:12px;background:transparent}
QPushButton#Nav:checked,QPushButton#Nav:hover{background:#1e3a5f;color:#7dd3fc}
QListWidget,QTreeWidget{background:#0b1220;border:1px solid #334155;border-radius:8px;padding:3px}
QListWidget::item,QTreeWidget::item{padding:9px;border-radius:6px} QListWidget::item:selected,QTreeWidget::item:selected{background:#1d4ed8}
QGroupBox{border:1px solid #334155;border-radius:8px;margin-top:10px;padding:12px;font-weight:700}
QGroupBox::title{subcontrol-origin:margin;left:12px;padding:0 5px;color:#7dd3fc}
QTabWidget::pane{border:1px solid #334155;border-radius:8px} QTabBar::tab{padding:9px 16px}
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
        db.result.connect(self.handle); db.error.connect(lambda op,msg: QMessageBox.critical(self,"Database error",msg))
        QShortcut(QKeySequence("Ctrl+S"),self,activated=self.save_note); QShortcut(QKeySequence("Ctrl+N"),self,activated=self.new_note)

    def build(self):
        root=QWidget(); self.setCentralWidget(root); outer=QVBoxLayout(root); outer.setContentsMargins(0,0,0,0)
        header=QFrame(); header.setObjectName("Header"); h=QHBoxLayout(header); title=QVBoxLayout()
        t=QLabel("MSG ACADEMIC WORKSPACE"); t.setObjectName("Title"); s=QLabel("PERSONAL KNOWLEDGE + AI COPILOT"); s.setObjectName("Sub"); title.addWidget(t); title.addWidget(s); h.addLayout(title); h.addStretch()
        self.profile_label=QLabel("Workspace"); h.addWidget(self.profile_label); outer.addWidget(header)
        body=QHBoxLayout(); sidebar=QFrame(); sidebar.setObjectName("Sidebar"); side=QVBoxLayout(sidebar); side.setContentsMargins(10,16,10,10)
        self.nav_buttons=[]
        for text,idx in [("Notes",0),("Analytics",1),("AI Copilot",2),("Settings",3)]:
            b=QPushButton(text); b.setObjectName("Nav"); b.setCheckable(True); b.clicked.connect(lambda _,i=idx:self.pages.setCurrentIndex(i)); side.addWidget(b); self.nav_buttons.append(b)
        side.addStretch(); self.quick=QPushButton("Open chat popup"); self.quick.clicked.connect(self.open_chat); side.addWidget(self.quick); body.addWidget(sidebar)
        self.pages=QStackedWidget(); self.pages.addWidget(self.notes_page()); self.pages.addWidget(self.analytics_page()); self.pages.addWidget(self.chat_page()); self.pages.addWidget(self.settings_page()); body.addWidget(self.pages,1); outer.addLayout(body,1)
        footer=QFrame(); footer.setObjectName("Footer"); fl=QHBoxLayout(footer); self.status=QLabel("Ready"); fl.addWidget(self.status); fl.addStretch(); fl.addWidget(QLabel("Local-first workspace")); outer.addWidget(footer); self.nav_buttons[0].setChecked(True)

    def notes_page(self):
        page=QWidget(); layout=QVBoxLayout(page); top=QHBoxLayout(); self.search=QLineEdit(); self.search.setPlaceholderText("Search all notes, tags, and content..."); self.search.textChanged.connect(lambda:self.db.request.emit("tree",self.search.text())); top.addWidget(self.search); new=QPushButton("+ New note"); new.setObjectName("Primary"); new.clicked.connect(self.new_note); top.addWidget(new); layout.addLayout(top)
        split=QSplitter(); self.note_list=QTreeWidget(); self.note_list.setHeaderLabels(["Title","Category","Course","Updated"]); self.note_list.header().setSectionResizeMode(0,QHeaderView.ResizeMode.Stretch); self.note_list.itemClicked.connect(self.open_tree_note); split.addWidget(self.note_list)
        editor=QWidget(); el=QVBoxLayout(editor); meta=QHBoxLayout(); self.title=QLineEdit(); self.title.setPlaceholderText("Note title"); self.course=QComboBox(); self.category=QComboBox(); self.category.addItems(CATEGORIES); meta.addWidget(self.title,3); meta.addWidget(self.course,2); meta.addWidget(self.category,2); el.addLayout(meta)
        tags=QLineEdit(); tags.setPlaceholderText("Tags, comma-separated"); self.tags=tags; el.addWidget(tags)
        toolbar=QHBoxLayout(); self.mode=QComboBox(); self.mode.addItems(["Rich Text","Code"]); self.mode.currentIndexChanged.connect(self.toggle_editor); toolbar.addWidget(QLabel("Editor:")); toolbar.addWidget(self.mode)
        self.bold_button=QPushButton("B"); self.bold_button.setToolTip("Bold"); self.bold_button.clicked.connect(lambda: self.rich.setFontWeight(QFont.Weight.Bold))
        italic=QPushButton("I"); italic.setToolTip("Italic"); italic.clicked.connect(lambda: self.rich.setFontItalic(not self.rich.fontItalic()))
        bullet=QPushButton("• List"); bullet.clicked.connect(lambda: self.rich.insertPlainText("\n• "))
        toolbar.addWidget(self.bold_button); toolbar.addWidget(italic); toolbar.addWidget(bullet); toolbar.addStretch(); el.addLayout(toolbar)
        self.rich=QTextEdit(); self.code=QPlainTextEdit(); self.code.setFont(QFont("Consolas",10)); el.addWidget(self.rich); el.addWidget(self.code); self.code.hide()
        actions=QHBoxLayout(); save=QPushButton("Save note"); save.setObjectName("Primary"); save.clicked.connect(self.save_note); delete=QPushButton("Delete note"); delete.setObjectName("Danger"); delete.clicked.connect(self.delete_note); actions.addWidget(save); actions.addWidget(delete); actions.addStretch(); el.addLayout(actions); split.addWidget(editor); split.setSizes([500,900]); layout.addWidget(split); self.db.request.emit("courses",None); return page

    def analytics_page(self):
        page=QWidget(); layout=QVBoxLayout(page); title=QLabel("Usage analytics"); title.setObjectName("Section"); layout.addWidget(title); self.metrics=QGridLayout(); layout.addLayout(self.metrics); self.breakdown=QListWidget(); layout.addWidget(QLabel("Notes by category")); layout.addWidget(self.breakdown); self.activity=QListWidget(); layout.addWidget(QLabel("Recent activity")); layout.addWidget(self.activity); return page

    def chat_page(self):
        self.chat=ChatPanel(self.db); return self.chat

    def settings_page(self):
        page=QWidget(); layout=QVBoxLayout(page); title=QLabel("Settings"); title.setObjectName("Section"); layout.addWidget(title)
        button=QPushButton("Edit profile and AI configuration"); button.setObjectName("Primary"); button.clicked.connect(self.configure); layout.addWidget(button)
        info=QLabel("Your profile, AI configuration, and conversation memory are stored locally in SQLite. Ollama must be installed and running separately."); info.setWordWrap(True); info.setStyleSheet("color:#94a3b8"); layout.addWidget(info); layout.addStretch(); return page

    def toggle_editor(self):
        is_code=self.mode.currentIndex()==1; self.rich.setVisible(not is_code); self.code.setVisible(is_code)
        self.bold_button.setEnabled(not is_code)

    def open_tree_note(self,item,_):
        self.note_id=item.data(0,Qt.ItemDataRole.UserRole); self.db.request.emit("note",self.note_id)

    def new_note(self):
        self.note_id=None; self.title.clear(); self.tags.clear(); self.rich.clear(); self.code.clear(); self.status.setText("New note draft")

    def save_note(self):
        if not self.title.text().strip() or self.course.currentData() is None:
            QMessageBox.warning(self,"Validation","Choose a title and course."); return
        content=self.code.toPlainText() if self.mode.currentIndex()==1 else self.rich.toHtml()
        self.db.request.emit("save_note",(self.note_id,self.course.currentData(),self.title.text().strip(),self.category.currentText(),content,self.tags.text().strip(),"code" if self.mode.currentIndex() else "rich"))

    def delete_note(self):
        if self.note_id and QMessageBox.question(self,"Delete note","Delete this note permanently?")==QMessageBox.StandardButton.Yes: self.db.request.emit("delete_note",self.note_id)

    def open_chat(self):
        dialog=QDialog(self); dialog.setWindowTitle("Copilot chat"); dialog.resize(620,600); lay=QVBoxLayout(dialog); panel=ChatPanel(self.db); panel.set_profile(self.profile); lay.addWidget(panel); panel.load(); dialog.exec()

    def configure(self):
        dialog=AISetupDialog(self.profile,self); dialog.completed.connect(self.save_ai); dialog.exec()

    def save_ai(self, data):
        p=list(self.profile); p[8]=data["ai_name"]; p[9]=data["system_prompt"]; p[10]=data["persona"]; p[11]=data["memory_enabled"]; p[12]=data["ollama_url"]; p[13]=data["ollama_model"]; self.profile=tuple(p); self.chat.set_profile(self.profile); self.db.request.emit("save_profile",tuple(p[:8]+p[8:14]))

    @pyqtSlot(str,object)
    def handle(self,op,data):
        if op=="initialize": self.db.request.emit("profile",None); self.db.request.emit("tree",""); self.db.request.emit("analytics",None)
        elif op=="profile":
            self.profile=data; self.profile_label.setText(f"Welcome, {data[0] or 'there'}"); self.chat.set_profile(data)
            if not data[14]:
                dialog=OnboardingDialog(data,self); dialog.completed.connect(self.save_onboarding); dialog.exec()
            else: self.chat.load()
        elif op=="save_profile": self.status.setText("Settings saved")
        elif op=="courses":
            self.course.clear()
            for cid,code,name in data: self.course.addItem(f"[{code}] {name}",cid)
        elif op=="tree":
            self.note_list.clear()
            for nid,title,cat,updated,course in data:
                item=QTreeWidgetItem([title,cat,course or "",updated or ""]); item.setData(0,Qt.ItemDataRole.UserRole,nid); self.note_list.addTopLevelItem(item)
        elif op=="note" and data:
            nid,cid,title,cat,content,tags,mode,updated,_=data; self.note_id=nid; self.title.setText(title); self.tags.setText(tags or ""); self.category.setCurrentText(cat); self.course.setCurrentIndex(self.course.findData(cid)); self.mode.setCurrentIndex(1 if mode=="code" else 0); (self.code.setPlainText(content or "") if mode=="code" else self.rich.setHtml(content or ""))
        elif op in ("save_note","delete_note"):
            self.status.setText("Note saved" if op=="save_note" else "Note deleted"); self.db.request.emit("tree",self.search.text()); self.db.request.emit("analytics",None)
            if op=="delete_note": self.new_note()
        elif op=="analytics":
            totals,categories,activity=data
            while self.metrics.count(): self.metrics.takeAt(0).widget().deleteLater()
            labels=[("Total notes",totals[0]),("Words / chars",totals[1]),("Courses used",totals[2])]
            for col,(label,value) in enumerate(labels):
                box=QGroupBox(label); lay=QVBoxLayout(box); metric=QLabel(str(value)); metric.setObjectName("Metric"); lay.addWidget(metric); self.metrics.addWidget(box,0,col)
            self.breakdown.clear(); [self.breakdown.addItem(f"{cat}: {count}") for cat,count in categories]
            self.activity.clear(); [self.activity.addItem(f"{day}: {count} note update(s)") for day,count in activity]

    def save_onboarding(self,data):
        p=list(self.profile); p[:8]=[data[k] for k in ["first_name","dob","email","gender","hobbies","employment","goals","mental_health"]]; self.profile=tuple(p); self.configure(); self.db.request.emit("save_profile",tuple(p[:8]+p[8:14]))


def main():
    app=QApplication(sys.argv); app.setStyleSheet(STYLE); init_db()
    splash=QSplashScreen(QPixmap(420,180)); splash.show(); app.processEvents()
    thread=QThread(); db=DatabaseWorker(); db.moveToThread(thread); db.request.connect(db.execute); thread.start()
    window=MainWindow(db); window.show(); db.result.connect(lambda op,_: splash.finish(window) if op=="initialize" else None)
    db.request.emit("initialize",None); app.aboutToQuit.connect(thread.quit); sys.exit(app.exec())


if __name__=="__main__": main()
