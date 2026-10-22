"""A Textual client. Focus and rendering never advance the world."""
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Input, RichLog, Static
from .console import execute
from .protocol import Fault


class SamsaraTerminal(App):
    TITLE = 'Samsara · synthetic opening'
    CSS = """
    Screen { background: #141c22; color: #e4ddca; }
    #place { height: auto; padding: 1 2; color: #e4bd78; }
    #story { height: 1fr; margin: 0 1; border: round #506c6c; padding: 0 1; }
    #command { margin: 0 1 1 1; }
    """
    BINDINGS = [('ctrl+q', 'quit', 'Close view'), ('f5', 'refresh', 'Refresh')]

    def __init__(self, client, actor='visitor'):
        super().__init__()
        self.client, self.actor = client, actor
        self.transcript = []

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static('The Open Studio', id='place', markup=False)
        yield RichLog(id='story', min_width=1, wrap=True, markup=False, highlight=False)
        yield Input(placeholder='help · start quiet visit · show visit · act visit rest', id='command')
        yield Footer()

    def on_mount(self):
        self.action_refresh()
        self.write('You may rest, explore, practice, or work. Nothing requires a useful output. Type help for ordinary commands.')
        self.query_one('#command', Input).focus()

    def action_refresh(self):
        try:
            view = self.client.view()
            self.query_one('#place', Static).update(view['location'] + '\n' + view['description'])
            self.write(execute(self.client, 'view', self.actor))
        except Fault as exc:
            self.write(str(exc))

    def write(self, text):
        self.transcript.append(text)
        self.query_one('#story', RichLog).write(text)

    def on_resize(self):
        if list(self.query('#story')):
            self.set_timer(0.05, self.redraw_transcript)

    def redraw_transcript(self):
        log = self.query_one('#story', RichLog)
        log.clear()
        for text in self.transcript:
            log.write(text)

    def on_input_submitted(self, event: Input.Submitted):
        text = event.value.strip()
        event.input.value = ''
        if text in ('quit', '/quit'):
            self.exit(); return
        try:
            output = execute(self.client, text, self.actor)
        except (Fault, ValueError, StopIteration) as exc:
            output = exc.code if isinstance(exc, Fault) else 'INVALID'
        self.write('> ' + text + '\n' + output)
