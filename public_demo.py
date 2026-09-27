from public_guard import protect
from doculens.api import create_app
from doculens.config import Settings
from doculens.onnx_encoder import OnnxEncoder

settings = Settings.from_env()
app = create_app(settings=settings, encoder=OnnxEncoder(settings))
app.state.service.store.save_trace = lambda body: "ephemeral"
app = protect(app, "doculens", lambda p: p in {"/api/ask", "/api/search"}, blocked_get=("/api/traces",))
