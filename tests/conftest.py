import pytest
from doculens.config import Settings
from doculens.embeddings import Encoder
from doculens.store import Store
from doculens.service import Service


@pytest.fixture
def service(tmp_path):
    settings = Settings(data_dir=tmp_path, embeddings=False)
    return Service(settings, Store(tmp_path / "test.db"), Encoder(settings))
