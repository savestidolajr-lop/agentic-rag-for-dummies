FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1
# Ensure Rust/Cargo build cache is writable in container environments where /usr/local is read-only
ENV CARGO_HOME=/tmp/.cargo
ENV RUSTUP_HOME=/tmp/.rustup

# Run as non-root user in the container.
RUN useradd -m -u 1000 user
USER user

WORKDIR /app

COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir --upgrade -r requirements.txt

COPY --chown=user . .

EXPOSE 7860

# Render (and other platforms) provides the HTTP port via the PORT env var.
CMD ["python", "project/app.py"]
