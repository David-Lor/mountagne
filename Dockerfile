FROM python:3.10-slim

RUN apt-get update && apt-get -yq install exfat-fuse && rm -rf /var/lib/apt/lists/*
COPY requirements*.txt /
RUN mkdir /app && for REQUIREMENTS_FILE in /requirements*.txt; do pip install -r $REQUIREMENTS_FILE; done && rm /requirements*.txt

COPY . /mountagne/
ENTRYPOINT ["python"]
CMD ["-u", "/mountagne"]
