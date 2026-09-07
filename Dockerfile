FROM ghcr.io/home-assistant/base-python:3.13-alpine3.24

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip3 install --no-cache-dir -r /app/requirements.txt

COPY bot.py calculator.py market_data.py solar_time.py provinces.py /app/
COPY webapp /app/webapp
COPY run.sh /run.sh
RUN chmod a+x /run.sh

ARG BUILD_VERSION
ARG BUILD_ARCH
LABEL \
  io.hass.version="${BUILD_VERSION}" \
  io.hass.type="app" \
  io.hass.arch="${BUILD_ARCH}"

CMD ["/run.sh"]
