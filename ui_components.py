"""Reusable presentation primitives for the MSG-CMS visual system."""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


def page_heading(title, subtitle=""):
    container = QWidget()
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 8)
    title_label = QLabel(title)
    title_label.setObjectName("PageTitle")
    layout.addWidget(title_label)
    if subtitle:
        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName("PageSubtitle")
        layout.addWidget(subtitle_label)
    return container


def card(title="", subtitle=""):
    frame = QFrame()
    frame.setObjectName("Card")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(18, 16, 18, 16)
    layout.setSpacing(8)
    if title:
        title_label = QLabel(title)
        title_label.setObjectName("CardTitle")
        layout.addWidget(title_label)
    if subtitle:
        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName("CardSubtitle")
        layout.addWidget(subtitle_label)
    return frame, layout


def metric_card(label, value, accent="#31d7e8"):
    frame, layout = card()
    frame.setObjectName("MetricCard")
    value_label = QLabel(str(value))
    value_label.setObjectName("MetricValue")
    value_label.setStyleSheet(f"color: {accent};")
    caption = QLabel(label)
    caption.setObjectName("MetricLabel")
    layout.addWidget(value_label)
    layout.addWidget(caption)
    return frame


def pill(text, object_name="Pill"):
    label = QLabel(text)
    label.setObjectName(object_name)
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    return label


def action_button(text, primary=False):
    button = QPushButton(text)
    button.setObjectName("PrimaryButton" if primary else "SecondaryButton")
    return button
