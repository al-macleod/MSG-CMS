"""First-run profile and AI configuration dialogs."""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDateEdit, QDialog, QFormLayout, QGroupBox, QHBoxLayout,
    QLabel, QLineEdit, QMessageBox, QPushButton, QTabWidget, QTextEdit, QVBoxLayout,
    QWidget,
)

from ollama_client import OllamaClient


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
