FROM python:3.13

ENV PYTHONUNBUFFERED=1

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
