FROM python:3.10-slim

COPY requirements.txt /requirements.txt
RUN mkdir /app && pip install -r /requirements.txt && rm /requirements.txt
RUN apt-get update && apt-get -yq install exfat-fuse && rm -rf /var/lib/apt/lists/*

COPY . /mountagne/
ENTRYPOINT ["python"]
CMD ["-u", "/mountagne"]
