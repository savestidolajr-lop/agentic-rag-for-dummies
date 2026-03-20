import sys
import os
import warnings

warnings.filterwarnings(
    "ignore",
    message=".*PydanticSerializationUnexpectedValue.*parsed.*",
    category=UserWarning,
)
warnings.filterwarnings(
    "ignore",
    message=".*Pydantic serializer warnings.*",
    category=UserWarning,
    module="pydantic.*",
)

sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

import gradio as gr
from ui.gradio_app import create_gradio_ui, _SIDEBAR_HEAD, _enter_js, _theme
from ui.css import custom_css
import config

if __name__ == "__main__":
    print("\n🔨 Creating RAG Assistant...")
    demo = create_gradio_ui()
    print("\n🚀 Launching RAG Assistant (no auth — local dev mode)...")

    share = os.getenv("GRADIO_SHARE", "false").lower() in ("1", "true", "yes")
    port = int(os.getenv("PORT", "7860"))
    host = os.getenv("HOST", "0.0.0.0")

    demo.launch(
        share=share,
        allowed_paths=[config.DOCUMENTS_DIR],
        server_name=host,
        server_port=port,
        theme=_theme,
        css=custom_css,
        js=_enter_js,
        head=_SIDEBAR_HEAD,
        footer_links=[],
    )
