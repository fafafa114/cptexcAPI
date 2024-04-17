FROM python:3.11.8

RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    make \
    wget \
    automake \
    autoconf

RUN wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz \
    && tar -xzf ta-lib-0.4.0-src.tar.gz \
    && cd ta-lib \
    && wget -O config.guess http://git.savannah.gnu.org/cgit/config.git/plain/config.guess \
    && wget -O config.sub http://git.savannah.gnu.org/cgit/config.git/plain/config.sub \
    && ./configure --prefix=/usr \
    && make \
    && make install \
    && cd .. \
    && rm -rf ta-lib-0.4.0-src.tar.gz ta-lib

ENV LD_LIBRARY_PATH /usr/local/lib:$LD_LIBRARY_PATH

WORKDIR /app

COPY requirements.txt /app/

RUN pip install --no-cache-dir -r requirements.txt

COPY . /app

EXPOSE 8080

ENV FLASK_APP=main.py
ENV FLASK_RUN_HOST=0.0.0.0
ENV FLASK_RUN_PORT=8080

CMD ["flask", "run", "--host=0.0.0.0", "--port=8080"]
