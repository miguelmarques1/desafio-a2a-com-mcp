import io

from agente import request_log
from agente.request_log import LogFields, RequestLogger, format_log_line


def test_send_message_line():
    line = format_log_line("SendMessage", "9c1e04aa77b2", "task-1a2b3c4d5e6f", "TASK_STATE_FAILED")
    assert line == (
        "a2a method=SendMessage id=9c1e04aa77b2 task=task-1a2b3c4d5e6f state=TASK_STATE_FAILED"
    )


def test_error_line_carries_referenced_task_and_dash_state():
    line = format_log_line("GetTask", 2, "task-000000000000", None)
    assert line == "a2a method=GetTask id=2 task=task-000000000000 state=-"


def test_unparseable_request_logs_all_dashes():
    assert format_log_line(None, None, None, None) == "a2a method=- id=- task=- state=-"


def test_values_with_whitespace_are_json_quoted():
    line = format_log_line("Send Message", "a\nb", "", None)
    assert "\n" not in line
    assert line == 'a2a method="Send Message" id="a\\nb" task="" state=-'


def test_string_and_integer_ids_unquoted():
    assert "id=7 " in format_log_line("M", 7, None, None)
    assert "id=3f1a9c0b2d4e " in format_log_line("M", "3f1a9c0b2d4e", None, None)


def test_formatting_failure_falls_back_to_dashes(monkeypatch):
    def boom(*args):
        raise RuntimeError("x")

    monkeypatch.setattr(request_log, "format_log_line", boom)
    stream = io.StringIO()
    RequestLogger(stream).log(LogFields("M", 1, "t", "s"))
    assert stream.getvalue() == "a2a method=- id=- task=- state=-\n"


def test_stream_failure_does_not_break_request():
    class Broken:
        def write(self, _):
            raise OSError

    RequestLogger(Broken()).log(LogFields("M", 1, None, None))
