# MSG-CMS
A local-first academic workspace for organizing notes, understanding usage patterns, and working with an optional Ollama copilot.

## Features
- Full note history with open, edit, search, and delete workflows
- Rich text and code editor modes, switchable per note
- Analytics dashboard for note volume, content size, courses, categories, and activity
- First-run profile onboarding and AI copilot configuration
- Dedicated copilot screen plus a chat popup available from every screen
- Optional Ollama integration with configurable URL, model, system prompt, persona, and memory
- Keyboard shortcuts: Ctrl+S to save and Ctrl+N to create a new note

Profile and conversation data stay in the local SQLite database. Mental-health context is optional.
The copilot configuration includes a safety boundary and does not support malware, weapons, or harm.

## Run locally
1. Create a virtual environment if desired.
2. Install dependencies:
   pip install -r requirements.txt
3. Launch the app:
   python main.py

The app stores data in a local SQLite file named `school_cms_data.db` in the project folder.

## Ollama
Install Ollama separately, start its local service, and pull a model such as `llama3.2`.
The default endpoint is `http://127.0.0.1:11434`. If Ollama is unavailable, notes and analytics
remain fully usable and the chat screen reports the connection error.

## Module layout
- `main.py` owns the application shell, note editor, analytics view, and navigation.
- `database.py` owns SQLite schema initialization and background persistence operations.
- `ollama_client.py` owns Ollama HTTP transport, prompt construction, and async lifecycle.
- `dialogs.py` owns first-run profile and AI configuration dialogs.

This separation keeps provider-specific AI changes out of the application shell and makes it
possible to add another model provider without rewriting note management or onboarding.
