"""Autocompletion for Novel-Claude CLI."""
from prompt_toolkit.completion import Completer, Completion, PathCompleter
from prompt_toolkit.document import Document

from cli.project_manager import project_manager
from utils import config


class NovelClaudeCompleter(Completer):
    """Custom completer for Novel-Claude CLI."""

    def __init__(self):
        self.path_completer = PathCompleter(
            get_paths=lambda: [str(project_manager.current_path)]
        )
        self.directory_completer = PathCompleter(
            only_directories=True,
            get_paths=lambda: [str(project_manager.current_path)],
        )
        self.commands = [
            # Built-in
            '/help', '/exit', '/clear', '/history',

            # Project management
            'projects', 'projects create', 'projects switch',
            'projects list', 'projects info', 'projects delete',

            # Novel workflow
            'init', 'expand', 'world', 'blueprint', 'plan', 'write',
            'batch build', 'batch submit', 'batch sync',
            'reindex', 'review', 'audit', 'track',

            # File operations
            'ls', 'cat', 'find', 'cd', 'pwd',

            # Skills
            'skills', 'skills list', 'skills enable',
            'skills disable', 'skills reload', 'skills build',

            # Settings
            'settings', 'settings show', 'settings set',

            # Agent
            'agent', 'agent review',
        ]

    def get_completions(self, document: Document, complete_event):
        """Generate completions based on current input."""
        text = document.text_before_cursor.lstrip()
        word = document.get_word_before_cursor()

        # Check if in project name context
        if any(
            text.startswith(prefix)
            for prefix in (
                'projects switch ',
                'projects delete ',
                'projects info ',
            )
        ):
            for proj in project_manager.list_projects():
                if proj.startswith(word):
                    yield Completion(proj, start_position=-len(word))
            return

        # Check if in path context. Complete relative to the active REPL
        # directory, not the process working directory.
        for command in ('ls', 'cat', 'cd'):
            prefix = f"{command} "
            if not text.startswith(prefix):
                continue
            argument = text[len(prefix):]
            path_document = Document(argument, cursor_position=len(argument))
            completer = (
                self.directory_completer if command == 'cd' else self.path_completer
            )
            for completion in completer.get_completions(path_document, complete_event):
                yield completion
            return

        # Complete skill directory names after commands that take one.
        if any(
            text.startswith(prefix)
            for prefix in ('skills enable ', 'skills disable ', 'skills reload ')
        ):
            skills_dir = config.PROJECT_ROOT / 'skills'
            if skills_dir.is_dir():
                for directory in sorted(skills_dir.iterdir()):
                    if directory.is_dir() and directory.name.startswith(word):
                        yield Completion(directory.name, start_position=-len(word))
            return

        # Complete against the entire command prefix. Using only the last word
        # made inputs such as `projects sw` impossible to complete.
        variants = set(self.commands)
        variants.update(
            f"/{command}" for command in self.commands if not command.startswith('/')
        )
        for command in sorted(variants):
            if command.startswith(text) and command != text:
                yield Completion(
                    command[len(text):],
                    start_position=0,
                    display=command,
                )
