FROM python:3.8.2-alpine

RUN apk update

RUN apk add --no-cache \
    git \
    postgresql-libs \
    jpeg-dev \
    imagemagick

RUN apk add --no-cache --virtual .build-deps \
    git \
    gcc \
    g++ \
    musl-dev \
    postgresql-dev \
    libffi-dev \
    libwebp-dev \
    zlib-dev \
    imagemagick-dev \
    msttcorefonts-installer \
    fontconfig

RUN update-ms-fonts && \
    fc-cache -f

RUN mkdir /data

RUN chmod 777 /data

RUN pip install -r https://raw.githubusercontent.com/intellivoid/HarukaAya/production/requirements.txt

RUN apk del .build-deps

CMD ["python"]
