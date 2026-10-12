# ZimaOS Wi-Fi Manager — stdlib Python backend + static frontend
# Talks to the HOST NetworkManager over the host system D-Bus (network_mode: host),
# so the container needs no NM daemon of its own — just nmcli/iw/ip client tools.
FROM debian:12-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    WM_PORT=8095 \
    WM_DATA=/DATA/wifi-manager

# python3 = backend runtime; network-manager/iw/wireless-tools/iproute2 = the
# nmcli + iw + ip CLI tools the backend shells out to; iptables = hotspot NAT;
# curl = internet-connectivity probe; dbus = talk to the host system bus.
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 \
        network-manager \
        curl \
        iw \
        wireless-tools \
        iproute2 \
        iptables \
        procps \
        ca-certificates \
        dbus \
    && rm -rf /var/lib/apt/lists/* \
    && ln -sf /usr/bin/python3 /usr/local/bin/python

# NetworkManager inside the container must NOT auto-start (we use the host's NM
# through the mounted system bus); mask it so nothing races on boot.
RUN systemctl disable NetworkManager 2>/dev/null || true; \
    mkdir -p /DATA/wifi-manager

WORKDIR /app
COPY backend/server.py /app/server.py
COPY web/ /app/web/

EXPOSE 8095
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python3 -c "import urllib.request,sys; \
        sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8095/api/ping',timeout=4).status==200 else 1)" || exit 1

CMD ["python3", "/app/server.py"]
