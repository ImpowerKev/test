import sys
import os
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import kevops_explore


def test_clean_org_url():
    assert kevops_explore._clean_org_url("https://example.com/") == "https://example.com"


def test_main_count(capsys):
    sample_tasks = [{"id": 1}, {"id": 2}, {"id": 3}]
    with mock.patch.object(
        kevops_explore,
        "get_open_tasks",
        return_value=sample_tasks,
    ) as mocked:
        test_args = [
            "kevops_explore.py",
            "https://example.com",
            "MyProject",
            "token",
            "--count",
            "--area",
            "Proj\\Area1",
            "--area",
            "Proj\\Area2",
        ]
        with mock.patch.object(sys, "argv", test_args):
            kevops_explore.main()
    mocked.assert_called_once_with(
        "https://example.com",
        "MyProject",
        "token",
        ["Proj\\Area1", "Proj\\Area2"],
    )
    captured = capsys.readouterr()
    assert "3 tasks" in captured.out
