"""First-run profile and AI configuration dialogs."""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDateEdit, QDialog, QFormLayout, QGroupBox, QHBoxLayout,
    QLabel, QLineEdit, QMessageBox, QPushButton, QTabWidget, QTextEdit, QVBoxLayout,
    QWidget,
)

from ollama_client import OllamaClient


class QuickAddDialog(QDialog):
    """Reference-inspired modal for quickly creating workspace content."""

    note_created = pyqtSignal(object)

    def __init__(self, courses, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Quick Add")
        self.resize(820, 620)
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)

        header = QHBoxLayout()
        title = QLabel("Quick Add")
        title.setObjectName("DialogTitle")
        header.addWidget(title)
        header.addStretch()
        close = QPushButton("×")
        close.setObjectName("IconButton")
        close.clicked.connect(self.reject)
        header.addWidget(close)
        root.addLayout(header)

        self.mode = QComboBox()
        self.mode.addItems(["New Note", "New Task", "New Resource"])
        self.mode.currentIndexChanged.connect(self.update_mode)
        self.mode.setObjectName("SegmentedControl")
        root.addWidget(self.mode)

        body = QHBoxLayout()
        form_frame = QGroupBox("Create content")
        form = QFormLayout(form_frame)
        self.title = QLineEdit()
        self.title.setPlaceholderText("Give this item a clear title")
        self.course = QComboBox()
        for course_id, code, name in courses:
            self.course.addItem(f"[{code}] {name}", course_id)
        self.tags = QLineEdit()
        self.tags.setPlaceholderText("lecture, exam, project")
        self.category = QComboBox()
        self.category.addItems(["Lecture Note", "Assignment / Lab", "Exam Prep", "Reference Material", "Project Draft"])
        self.content = QTextEdit()
        self.content.setPlaceholderText("Add a short content snippet...")
        self.content.setMinimumHeight(180)
        form.addRow("Title", self.title)
        form.addRow("Course", self.course)
        form.addRow("Category", self.category)
        form.addRow("Tags", self.tags)
        form.addRow("Content", self.content)
        body.addWidget(form_frame, 3)

        preview_frame = QGroupBox("Quick preview")
        preview = QVBoxLayout(preview_frame)
        self.preview_title = QLabel("Untitled note")
        self.preview_title.setObjectName("PreviewTitle")
        self.preview_course = QLabel("Choose a course")
        self.preview_course.setObjectName("PreviewMeta")
        self.preview_content = QLabel("Your content snippet will appear here.")
        self.preview_content.setWordWrap(True)
        self.preview_content.setObjectName("PreviewContent")
        preview.addWidget(self.preview_title)
        preview.addWidget(self.preview_course)
        preview.addWidget(self.preview_content)
        preview.addStretch()
        body.addWidget(preview_frame, 2)
        root.addLayout(body, 1)

        self.title.textChanged.connect(self.update_preview)
        self.course.currentTextChanged.connect(self.update_preview)
        self.content.textChanged.connect(self.update_preview)

        actions = QHBoxLayout()
        actions.addStretch()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        save = QPushButton("Save note")
        save.setObjectName("PrimaryButton")
        save.clicked.connect(self.submit)
        actions.addWidget(cancel)
        actions.addWidget(save)
        root.addLayout(actions)
        self.update_mode()

    def update_preview(self):
        self.preview_title.setText(self.title.text().strip() or "Untitled note")
        self.preview_course.setText(self.course.currentText() or "Choose a course")
        content = self.content.toPlainText().strip()
        self.preview_content.setText(content[:180] if content else "Your content snippet will appear here.")

    def update_mode(self):
        enabled = self.mode.currentIndex() == 0
        for widget in (self.course, self.category, self.tags, self.content):
            widget.setEnabled(enabled)
        self.findChild(QPushButton, "PrimaryButton").setText("Save note" if enabled else "Coming soon")

    def submit(self):
        if not self.title.text().strip() or self.course.currentData() is None:
            QMessageBox.warning(self, "Validation", "Choose a title and course.")
            return
        if self.mode.currentIndex() == 1:
            self.note_created.emit({
                "kind": "task", "course_id": self.course.currentData(), "title": self.title.text().strip(),
                "description": self.content.toPlainText().strip(), "priority": "Medium",
            })
            self.accept()
            return
        if self.mode.currentIndex() == 2:
            self.note_created.emit({
                "kind": "resource", "course_id": self.course.currentData(), "title": self.title.text().strip(),
                "description": self.content.toPlainText().strip(), "tags": self.tags.text().strip(),
            })
            self.accept()
            return
        self.note_created.emit({
            "kind": "note",
            "course_id": self.course.currentData(),
            "title": self.title.text().strip(),
            "category": self.category.currentText(),
            "tags": self.tags.text().strip(),
            "content": self.content.toPlainText().strip(),
        })
        self.accept()


class TaskDialog(QDialog):
    saved = pyqtSignal(object)

    def __init__(self, courses, task=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Task")
        self.resize(520, 420)
        values = task or (None, "", "", "", "Medium", "Open", "")
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.title = QLineEdit(values[1])
        self.description = QTextEdit(values[2] or "")
        self.due = QDateEdit()
        self.due.setCalendarPopup(True)
        self.due.setDisplayFormat("yyyy-MM-dd")
        self.priority = QComboBox(); self.priority.addItems(["Low", "Medium", "High", "Urgent"]); self.priority.setCurrentText(values[4] or "Medium")
        self.course = QComboBox()
        for cid, code, name in courses: self.course.addItem(f"[{code}] {name}", cid)
        self.course.setCurrentIndex(max(0, self.course.findData(values[0])))
        form.addRow("Title", self.title); form.addRow("Course", self.course); form.addRow("Due date", self.due)
        form.addRow("Priority", self.priority); form.addRow("Description", self.description)
        layout.addLayout(form)
        save = QPushButton("Save task"); save.setObjectName("PrimaryButton"); save.clicked.connect(self.submit); layout.addWidget(save)

    def submit(self):
        if not self.title.text().strip() or self.course.currentData() is None:
            QMessageBox.warning(self, "Validation", "Choose a title and course."); return
        self.saved.emit((None, self.course.currentData(), self.title.text().strip(), self.description.toPlainText().strip(),
                         self.due.date().toString("yyyy-MM-dd"), self.priority.currentText(), "Open"))
        self.accept()


class ResourceDialog(QDialog):
    saved = pyqtSignal(object)

    def __init__(self, courses, resource=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Resource")
        self.resize(520, 380)
        values = resource or (None, "", "", "", "", "")
        layout = QVBoxLayout(self); form = QFormLayout()
        self.title = QLineEdit(values[1]); self.url = QLineEdit(values[2] or ""); self.description = QTextEdit(values[3] or "")
        self.tags = QLineEdit(values[4] or ""); self.course = QComboBox()
        for cid, code, name in courses: self.course.addItem(f"[{code}] {name}", cid)
        self.course.setCurrentIndex(max(0, self.course.findData(values[0])))
        form.addRow("Title", self.title); form.addRow("Course", self.course); form.addRow("URL", self.url)
        form.addRow("Description", self.description); form.addRow("Tags", self.tags); layout.addLayout(form)
        save = QPushButton("Save resource"); save.setObjectName("PrimaryButton"); save.clicked.connect(self.submit); layout.addWidget(save)

    def submit(self):
        if not self.title.text().strip() or self.course.currentData() is None:
            QMessageBox.warning(self, "Validation", "Choose a title and course."); return
        self.saved.emit((None, self.course.currentData(), self.title.text().strip(), self.url.text().strip(),
                         self.description.toPlainText().strip(), self.tags.text().strip()))
        self.accept()


class OnboardingDialog(QDialog):
    completed = pyqtSignal(object)

    def __init__(self, profile, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Welcome - personalize your workspace")
        self.resize(620, 600)
        layout = QVBoxLayout(self)
        intro = QLabel("Tell us about yourself\nThis information stays in your local database and personalizes your AI workspace.")
        intro.setObjectName("Section")
        layout.addWidget(intro)
        form = QFormLayout()
        self.first = QLineEdit()
        self.dob = QDateEdit()
        self.dob.setCalendarPopup(True)
        self.dob.setDisplayFormat("yyyy-MM-dd")
        self.email = QLineEdit()
        self.gender = QComboBox()
        self.gender.addItems(["Prefer not to say", "Woman", "Man", "Non-binary", "Other"])
        self.hobbies = QLineEdit()
        self.employment = QLineEdit()
        self.goals = QTextEdit()
        self.mental = QTextEdit()
        for label, widget in [
            ("First name", self.first), ("Date of birth", self.dob), ("Email", self.email),
            ("Gender", self.gender), ("Hobbies", self.hobbies), ("Employment", self.employment),
            ("Goals", self.goals), ("Mental health context (optional)", self.mental),
        ]:
            form.addRow(label, widget)
        layout.addLayout(form)
        privacy = QLabel("Mental-health context is optional. Do not enter crisis details or sensitive information you do not want stored locally.")
        privacy.setWordWrap(True)
        privacy.setStyleSheet("color:#94a3b8")
        layout.addWidget(privacy)
        save = QPushButton("Continue to AI setup")
        save.setObjectName("Primary")
        save.clicked.connect(self.submit)
        layout.addWidget(save)
        if profile and profile[0]:
            self.first.setText(profile[0])

    def submit(self):
        if not self.first.text().strip() or not self.email.text().strip():
            QMessageBox.warning(self, "Missing information", "Please provide your first name and email address.")
            return
        self.completed.emit({
            "first_name": self.first.text().strip(),
            "dob": self.dob.date().toString("yyyy-MM-dd"),
            "email": self.email.text().strip(),
            "gender": self.gender.currentText(),
            "hobbies": self.hobbies.text().strip(),
            "employment": self.employment.text().strip(),
            "goals": self.goals.toPlainText().strip(),
            "mental_health": self.mental.toPlainText().strip(),
        })
        self.accept()


class AISetupDialog(QDialog):
    completed = pyqtSignal(object)

    def __init__(self, profile, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configure your AI copilot")
        self.resize(620, 520)
        values = profile or (None,) * 15
        layout = QVBoxLayout(self)
        title = QLabel("Shape your copilot")
        title.setObjectName("Section")
        layout.addWidget(title)
        form = QFormLayout()
        self.name = QLineEdit(values[8] or "Atlas")
        self.url = QLineEdit(values[12] or "http://127.0.0.1:11434")
        self.model = QLineEdit(values[13] or "llama3.2")
        self.persona = QLineEdit(values[10] or "A calm, practical study partner")
        self.prompt = QTextEdit(values[9] or "You are a helpful, privacy-conscious academic copilot.")
        self.memory = QCheckBox("Enable long-term memory")
        self.memory.setChecked(bool(values[11] if values[11] is not None else 1))
        for label, widget in [
            ("Assistant name", self.name), ("Ollama URL", self.url), ("Model", self.model),
            ("Persona", self.persona), ("System prompt", self.prompt),
        ]:
            form.addRow(label, widget)
        layout.addLayout(form)
        layout.addWidget(self.memory)
        hint = QLabel("Ollama is optional. Install it separately, pull a model, then use Settings to change these values. The copilot will not assist with malware, weapons, or harming people.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#94a3b8")
        layout.addWidget(hint)
        save = QPushButton("Save AI configuration")
        save.setObjectName("Primary")
        save.clicked.connect(self.submit)
        layout.addWidget(save)

    def submit(self):
        self.completed.emit({
            "ai_name": self.name.text().strip() or "Atlas",
            "ollama_url": self.url.text().strip(),
            "ollama_model": self.model.text().strip(),
            "persona": self.persona.text().strip(),
            "system_prompt": self.prompt.toPlainText().strip(),
            "memory_enabled": int(self.memory.isChecked()),
        })
        self.accept()


class AIConfigurationPage(QWidget):
    """Full AI configuration surface used in the main screen and settings modal."""

    saved = pyqtSignal(object)

    def __init__(self, profile, parent=None):
        super().__init__(parent)
        values = profile or (None,) * 15
        self.client = OllamaClient(self)
        self.client.models.connect(self.set_models)
        self.client.error.connect(self.show_error)
        layout = QVBoxLayout(self)
        heading = QLabel("AI configuration")
        heading.setObjectName("Section")
        layout.addWidget(heading)
        subtitle = QLabel("Control how your local copilot behaves, remembers context, and connects to Ollama.")
        subtitle.setStyleSheet("color:#94a3b8")
        layout.addWidget(subtitle)

        identity = QGroupBox("Assistant identity")
        identity_form = QFormLayout(identity)
        self.name = QLineEdit(values[8] or "Atlas")
        self.persona = QLineEdit(values[10] or "A calm, practical study partner")
        identity_form.addRow("Name", self.name)
        identity_form.addRow("Persona", self.persona)
        layout.addWidget(identity)

        provider = QGroupBox("Model provider")
        provider_form = QFormLayout(provider)
        self.url = QLineEdit(values[12] or "http://127.0.0.1:11434")
        self.model = QComboBox()
        self.model.setEditable(True)
        self.model.addItem(values[13] or "llama3.2")
        provider_form.addRow("Ollama URL", self.url)
        provider_form.addRow("Model", self.model)
        provider_actions = QHBoxLayout()
        discover = QPushButton("Discover installed models")
        discover.clicked.connect(lambda: self.client.list_models(self.url.text().strip()))
        test = QPushButton("Test connection")
        test.clicked.connect(self.test_connection)
        provider_actions.addWidget(discover)
        provider_actions.addWidget(test)
        provider_actions.addStretch()
        provider_form.addRow("", provider_actions)
        self.connection_status = QLabel("Not tested")
        provider_form.addRow("", self.connection_status)
        layout.addWidget(provider)

        memory = QGroupBox("Memory and behavior")
        memory_form = QVBoxLayout(memory)
        self.memory = QCheckBox("Enable long-term memory")
        self.memory.setChecked(bool(values[11] if values[11] is not None else 1))
        memory_form.addWidget(self.memory)
        memory_form.addWidget(QLabel("Memory is stored locally as chat history. Disable it when you want stateless conversations."))
        self.prompt = QTextEdit(values[9] or "You are a helpful, privacy-conscious academic copilot.")
        self.prompt.setMinimumHeight(150)
        memory_form.addWidget(QLabel("System prompt"))
        memory_form.addWidget(self.prompt)
        layout.addWidget(memory)
        layout.addStretch()

        save = QPushButton("Save AI configuration")
        save.setObjectName("Primary")
        save.clicked.connect(self.save)
        layout.addWidget(save)

    def set_models(self, models):
        current = self.model.currentText()
        self.model.clear()
        self.model.addItems(models or [current])
        self.model.setCurrentText(current if current in models else (models[0] if models else current))
        self.connection_status.setText(f"Connected - {len(models)} model(s) found")

    def set_profile(self, profile):
        values = profile or (None,) * 15
        self.name.setText(values[8] or "Atlas")
        self.url.setText(values[12] or "http://127.0.0.1:11434")
        self.model.setCurrentText(values[13] or "llama3.2")
        self.persona.setText(values[10] or "A calm, practical study partner")
        self.prompt.setPlainText(values[9] or "You are a helpful, privacy-conscious academic copilot.")
        self.memory.setChecked(bool(values[11] if values[11] is not None else 1))

    def show_error(self, message):
        self.connection_status.setText(message)

    def test_connection(self):
        self.connection_status.setText("Testing Ollama connection...")
        self.client.list_models(self.url.text().strip())

    def save(self):
        self.saved.emit({
            "ai_name": self.name.text().strip() or "Atlas",
            "ollama_url": self.url.text().strip(),
            "ollama_model": self.model.currentText().strip() or "llama3.2",
            "persona": self.persona.text().strip(),
            "system_prompt": self.prompt.toPlainText().strip(),
            "memory_enabled": int(self.memory.isChecked()),
        })


class SettingsDialog(QDialog):
    """Maximized settings workspace for profile, appearance, data, and AI entry points."""

    profile_saved = pyqtSignal(object)
    ai_saved = pyqtSignal(object)

    def __init__(self, profile, parent=None):
        super().__init__(parent)
        self.profile = profile
        self.setWindowTitle("Workspace settings")
        self.setWindowState(self.windowState() | Qt.WindowState.WindowMaximized)
        root = QVBoxLayout(self)
        header = QHBoxLayout()
        title = QLabel("Workspace settings")
        title.setObjectName("Section")
        header.addWidget(title)
        header.addStretch()
        close = QPushButton("Close")
        close.clicked.connect(self.close)
        header.addWidget(close)
        root.addLayout(header)
        tabs = QTabWidget()
        tabs.addTab(self.profile_tab(), "Profile")
        self.ai_page = AIConfigurationPage(profile)
        self.ai_page.saved.connect(self.ai_saved)
        tabs.addTab(self.ai_page, "AI configuration")
        tabs.addTab(self.appearance_tab(), "Appearance")
        tabs.addTab(self.data_tab(), "Data and privacy")
        root.addWidget(tabs)

    def profile_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        form = QFormLayout()
        values = self.profile or (None,) * 15
        self.first = QLineEdit(values[0] or "")
        self.email = QLineEdit(values[2] or "")
        self.gender = QComboBox()
        self.gender.addItems(["Prefer not to say", "Woman", "Man", "Non-binary", "Other"])
        self.gender.setCurrentText(values[3] or "Prefer not to say")
        self.hobbies = QLineEdit(values[4] or "")
        self.employment = QLineEdit(values[5] or "")
        self.goals = QTextEdit(values[6] or "")
        for label, widget in [("First name", self.first), ("Email", self.email), ("Gender", self.gender),
                              ("Hobbies", self.hobbies), ("Employment", self.employment), ("Goals", self.goals)]:
            form.addRow(label, widget)
        layout.addLayout(form)
        save = QPushButton("Save profile")
        save.setObjectName("Primary")
        save.clicked.connect(self.save_profile)
        layout.addWidget(save)
        layout.addStretch()
        return page

    def appearance_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(QLabel("Appearance controls are ready for theme and density preferences."))
        compact = QCheckBox("Use compact navigation density")
        compact.setChecked(False)
        layout.addWidget(compact)
        layout.addStretch()
        return page

    def data_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(QLabel("Your notes, profile, and chat history are stored in the local SQLite database."))
        export_button = QPushButton("Export data")
        export_button.setEnabled(False)
        export_button.setToolTip("Export is planned for the next data portability iteration.")
        layout.addWidget(export_button)
        layout.addStretch()
        return page

    def save_profile(self):
        self.profile_saved.emit({
            "first_name": self.first.text().strip(),
            "email": self.email.text().strip(),
            "gender": self.gender.currentText(),
            "hobbies": self.hobbies.text().strip(),
            "employment": self.employment.text().strip(),
            "goals": self.goals.toPlainText().strip(),
        })
