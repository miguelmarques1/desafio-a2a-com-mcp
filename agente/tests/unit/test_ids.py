import re

import pytest

from agente.ids import RandomIdFactory


@pytest.mark.parametrize(
    ("method", "prefix"),
    [("task_id", "task"), ("context_id", "ctx"), ("message_id", "msg"), ("artifact_id", "art")],
)
def test_ids_have_prefix_and_12_lowercase_hex(method, prefix):
    value = getattr(RandomIdFactory(), method)()
    assert re.fullmatch(rf"{prefix}-[0-9a-f]{{12}}", value)


def test_ids_are_unique_across_many_calls():
    ids = RandomIdFactory()
    values = {ids.task_id() for _ in range(10_000)}
    assert len(values) == 10_000
