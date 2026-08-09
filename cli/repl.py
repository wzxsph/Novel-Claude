"""Interactive REPL for Novel-Claude CLI."""
from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.history import FileHistory
from prompt_toolkit.styles import Style
from prompt_toolkit.key_binding import KeyBindings

from cli.dispatcher import CommandDispatcher
from cli.project_manager import project_manager
from cli.completer import NovelClaudeCompleter
from utils import config


def get_prompt() -> FormattedText:
    """Generate the prompt string based on current context."""
    project = project_manager.current_project or "default"
    vol = project_manager.current_volume
    ch = project_manager.current_chapter

    return FormattedText([
        ('ansicyan', '[Novel: '),
        ('ansigreen bold', project),
        ('ansicyan', '] ('),
        ('ansiyellow', f'vol:{vol}'),
        ('ansicyan', ', '),
        ('ansiyellow', f'ch:{ch}'),
        ('ansicyan', ') > '),
    ])

# Key bindings for special keys
kb = KeyBindings()

@kb.add('c-c', eager=True)
def _(event):
    """Handle Ctrl-C gracefully."""
    print("\n[Use /exit to quit]", flush=True)

# REPL Style
style = Style.from_dict({
    'prompt': '#00aaaa',
    'username': '#00ff00',
    'hostname': '#ff0066',
})

class REPL:
    """Interactive read-eval-print loop for Novel-Claude."""

    def __init__(self):
        self.dispatcher = CommandDispatcher()
        history_path = config.PROJECT_ROOT / ".novel_cli_config" / "history"
        history_path.parent.mkdir(parents=True, exist_ok=True)
        self.history = FileHistory(str(history_path))
        self.completer = NovelClaudeCompleter()
        self.session = PromptSession(
            history=self.history,
            key_bindings=kb,
            style=style,
            completer=self.completer,
        )

    def print_banner(self):
        """Print welcome banner."""
        print("=" * 60)
        print("  Novel-Claude V3 Interactive CLI")
        print("  Type /help for available commands")
        print("=" * 60)

    def print_error(self, msg: str):
        """Print error message."""
        print(f"[ERROR] {msg}")

    def print_success(self, msg: str):
        """Print success message."""
        print(f"[OK] {msg}")

    def print_info(self, msg: str):
        """Print info message."""
        print(f"[INFO] {msg}")

    def run(self):
        """Main REPL loop."""
        self.print_banner()

        while True:
            try:
                user_input = self.session.prompt(get_prompt)
            except KeyboardInterrupt:
                continue
            except EOFError:
                break

            if not user_input.strip():
                continue

            # Handle built-in commands
            if user_input.strip() == '/exit':
                print("Goodbye!")
                break

            if user_input.strip() == '/help':
                self._print_help()
                continue

            if user_input.strip() == '/history':
                for i, cmd in enumerate(self.history.get_strings()):
                    print(f"  {i}: {cmd}")
                continue

            if user_input.strip() == '/clear':
                print("\033[2J\033[H", end="")
                continue

            # Dispatch command
            result = self.dispatcher.dispatch(user_input)

            if result.get('error'):
                self.print_error(result['error'])
                continue
            if result.get('message'):
                print(result['message'])
            if result.get('output'):
                print(result['output'])

        # Save state on exit
        project_manager._save_state()
        config.wait_for_background_tasks()

    def _print_help(self):
        """Print available commands."""
        help_text = """
Available Commands:
===================

Built-in:
  /help     - Show this help
  /exit     - Exit the CLI
  /clear    - Clear the screen
  /history  - Show command history

Project Management:
  projects create <name> <logline>  - Create a new project
  projects switch <name>           - Switch to a project
  projects switch default          - Return to the default workspace
  projects list                     - List all projects
  projects info                     - Show current project info
  projects delete <name>            - Delete a project

Novel Workflow (Snowflake Method):
  init <logline>                    - Run the complete world-building pipeline
  expand / world / blueprint       - Re-run one world-building stage
  plan [volume]                     - Generate volume outlines (10 volumes)
  plan --volume N                   - Generate stage outlines for volume N
  write --volume N --chapters X-Y  - Write chapters
  audit --stage N                   - Audit stage consistency
  audit --chapter N                 - Audit chapter consistency
  track --volume N --chapter M      - Track entity state changes
  reindex --volume N --chapters X-Y - Reindex chapters to RAG
  batch build --volume N --chapters X-Y
  batch submit <jsonl> / batch sync <id>

File Operations:
  ls [path]                          - List directory
  cat <file>                        - Show file contents
  find <pattern>                     - Find files
  cd <path>                          - Change directory
  pwd                               - Print working directory

Skills:
  skills list                       - List all skills
  skills enable/disable <name>      - Enable/disable a skill
  skills reload [name]               - Reload skills
  skills build <request>             - Build a new skill

Settings:
  settings show                     - Show current settings
  settings set <key> <value>         - Set a config value

Agent:
  agent review -f <file> -i <inst>  - Review files with AI

Note: Commands can also be used without '/' prefix.
        """
        print(help_text)


def start_repl():
    """Entry point to start the REPL."""
    from core.runtime import get_runtime

    get_runtime()
    repl = REPL()
    repl.run()
