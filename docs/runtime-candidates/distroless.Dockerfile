FROM python@sha256:09a17cad02668ae61ece136b4fd36ac3849e14f670ebedb637ea3e15580525bc AS builder
WORKDIR /build
COPY pyproject.toml README.md ./
COPY app/ ./app/
RUN python -m pip install --no-cache-dir --target=/opt/python . && mkdir /aliases && ln -s /usr/bin/python3 /aliases/python
FROM gcr.io/distroless/python3-debian13@sha256:1c32c3720dc4c7f0c7dbe998737f32c200add6511eca7cec705008be488b87d6
COPY --from=builder /opt/python /opt/python
COPY --from=builder /aliases/ /usr/local/bin/
ENV PYTHONPATH=/opt/python
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv
USER 10001:10001
EXPOSE 8000
ENTRYPOINT ["/usr/bin/python3"]
CMD ["-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
