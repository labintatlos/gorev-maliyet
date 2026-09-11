ARG BUILD_FROM
FROM $BUILD_FROM

# Web sitesi yalnızca Python standart kütüphanesini kullanır; pip ile kurulacak
# veya derlenecek bir paket yoktur.
RUN apk add --no-cache \
    python3 \
    tzdata \
    ca-certificates

WORKDIR /app

COPY . /app/

RUN chmod a+x /app/run.sh

ENV PYTHONUNBUFFERED=1

CMD [ "/app/run.sh" ]
