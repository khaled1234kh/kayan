"""Shared markers."""

import pytest


@pytest.fixture()
def api(client):
    return client