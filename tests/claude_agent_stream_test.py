import io
import json
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from src.agents.claude import ClaudeAgent


class ClaudeAgentStreamTest(unittest.TestCase):
    def test_run_does_not_append_assistant_message_and_final_result_twice(self):
        events = [
            {
                "type": "assistant",
                "session_id": "session-1",
                "message": {"content": [{"type": "text", "text": "生成的文案"}]},
            },
            {"type": "result", "session_id": "session-1", "result": "生成的文案"},
        ]

        class FakeStdin:
            def write(self, _message):
                return None

            def close(self):
                return None

        class FakeProcess:
            returncode = 0

            def __init__(self):
                self.stdin = FakeStdin()
                self.stdout = io.StringIO(
                    "".join(json.dumps(event) + "\n" for event in events)
                )

            def poll(self):
                return 0

            def wait(self):
                return 0

        with patch("src.agents.claude.subprocess.Popen", return_value=FakeProcess()):
            with redirect_stdout(io.StringIO()):
                result = ClaudeAgent().run("/tmp", "生成文案")

        self.assertEqual(result.text, "生成的文案")
        self.assertEqual(result.session_id, "session-1")


if __name__ == "__main__":
    unittest.main()
