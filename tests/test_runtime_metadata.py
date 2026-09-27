from importlib.metadata import PackageNotFoundError
from doculens import evaluation


def test_onnx_runtime_metadata_does_not_require_torch_backend(monkeypatch):
    def fake_version(name):
        if name == "sentence-transformers":
            raise PackageNotFoundError(name)
        return "test-version"

    monkeypatch.setattr(evaluation, "version", fake_version)
    versions = evaluation.installed_versions()
    assert "sentence-transformers" not in versions
    assert versions["onnxruntime"] == "test-version"
    assert versions["numpy"] == "test-version"
