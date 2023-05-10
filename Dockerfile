FROM python:3.11.3-slim-bullseye

# install a few things we need for running this stuff or could be used for debugging
RUN apt-get update && apt-get install -y vim procps curl
RUN pip install kubernetes psutil coloredlogs --disable-pip-version-check --no-cache-dir

RUN mkdir -p /opt/script/kube-vip-watcher/healthchecks
ADD kube-vip-watcher.py /opt/script/kube-vip-watcher/
RUN chmod +x /opt/script/kube-vip-watcher/kube-vip-watcher.py
ADD healthchecks/* /opt/script/kube-vip-watcher/healthchecks/
RUN chmod +x /opt/script/kube-vip-watcher/healthchecks/*.py
ADD lib/* /opt/script/kube-vip-watcher/lib/

# Add the user UID:1000, GID:1000, home at /app
RUN groupadd -r kube-vip-watcher -g 1000 && \
    useradd -u 1000 -r -g kube-vip-watcher -m -d /opt/script/kube-vip-watcher -s /sbin/nologin -c "kube-vip-watcher user" kube-vip-watcher && \
    chmod 755 /opt/script/kube-vip-watcher
RUN chown -R kube-vip-watcher.kube-vip-watcher /opt/script/kube-vip-watcher

# Specify the user to execute all commands below
USER kube-vip-watcher
WORKDIR /opt/script/kube-vip-watcher
# python -u ... Force the stdout and stderr streams to be unbuffered. This makes simple print messages being viewable via kubectl logs...
CMD ["/usr/local/bin/python3", "-u", "/opt/script/kube-vip-watcher/kube-vip-watcher.py"]
