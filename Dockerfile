FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install deps first for better layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# The app code…
COPY app ./app

# …and everything the app READS at runtime. This image used to ship `app/`
# alone, which built and started cleanly and then failed on first contact:
# every `/tools/*` page reads `modules/`, the ideas board parses `BACKLOG.md`,
# Nama Expert indexes the markdown, and the legal counsel reads `corpus/legal`.
# A container that starts and 500s on the first page anyone opens is the worst
# kind of broken, so `tests/test_deploy.py` now asserts that every directory the
# code reads at runtime is copied here.
COPY modules ./modules
COPY data ./data
COPY docs ./docs
COPY reference ./reference
COPY corpus ./corpus
COPY BACKLOG.md CHANGELOG.md DECISIONS.md HANDOFF.md MASTER_EXECUTION_RUNBOOK.md \
     NEXT_STEP.md README.md RESOURCES.md TASKS.md VISION.md SESSION_STATE.json ./

EXPOSE 8000

# Container-side healthcheck hits the gateway's /health
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health').status==200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
