"""First-run profile and AI configuration dialogs."""

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QCheckBox, QComboBox, QDateEdit, QDialog, QFormLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QTextEdit, QVBoxLayout


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
