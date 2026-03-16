import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

import gradio as gr
from ui.css import custom_css
from ui.gradio_app import create_gradio_ui, _SIDEBAR_HEAD
import config

if __name__ == "__main__":
    print("\n🔨 Creating RAG Assistant...")
    demo = create_gradio_ui()
    print("\n🚀 Launching RAG Assistant...")

    theme = gr.themes.Base(
        primary_hue="neutral",
        secondary_hue="neutral",
        neutral_hue="neutral",
        font=gr.themes.GoogleFont("Inter"),
    ).set(
        body_background_fill="#0d0d0d",
        body_text_color="#e8e8e8",
        block_background_fill="#161616",
        block_border_color="#2d2d2d",
        input_background_fill="#1a1a1a",
        input_border_color="#2d2d2d",
        button_primary_background_fill="#10a37f",
        button_primary_text_color="#ffffff",
        button_secondary_background_fill="#232323",
        button_secondary_text_color="#c8c8c8",
        button_secondary_border_color="#333",
    )

    share = os.getenv("GRADIO_SHARE", "false").lower() in ("1", "true", "yes")

    # Render (and other platforms) provide the HTTP port via the PORT env var.
    port = int(os.getenv("PORT", "7860"))
    host = os.getenv("HOST", "0.0.0.0")

    demo.launch(
        css=custom_css,
        theme=theme,
        share=share,
        head=_SIDEBAR_HEAD,
        allowed_paths=[config.DOCUMENTS_DIR],
        server_name=host,
        server_port=port,
    )