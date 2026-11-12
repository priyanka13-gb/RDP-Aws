FROM python@sha256:e064671ca452259bab50e8e2c7bd896e39e9a343bb06ca25234adf6fe18d0fc7 AS builder
WORKDIR /build
COPY pyproject.toml README.md ./
COPY app/ ./app/
RUN python -m pip install --no-cache-dir --target=/opt/python .
FROM python@sha256:e064671ca452259bab50e8e2c7bd896e39e9a343bb06ca25234adf6fe18d0fc7
RUN apk upgrade --no-cache && python -m pip uninstall -y pip
COPY --from=builder /opt/python /opt/python
ENV PYTHONPATH=/opt/python
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv
USER 10001:10001
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
