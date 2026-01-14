FROM debian:bookworm-slim

ARG KUBECTL_VERSION=v1.31.0
ARG HELM_VERSION=v3.15.4
ARG KIND_VERSION=v0.24.0
ARG DOCKER_CLI_VERSION=27.1.1

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl bash git jq coreutils openssl \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL -o /usr/local/bin/kubectl \
      https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/linux/amd64/kubectl \
    && chmod +x /usr/local/bin/kubectl

RUN curl -fsSL https://get.helm.sh/helm-${HELM_VERSION}-linux-amd64.tar.gz \
  | tar -xz && mv linux-amd64/helm /usr/local/bin/helm && rm -rf linux-amd64

RUN curl -fsSL -o /usr/local/bin/kind \
      https://kind.sigs.k8s.io/dl/${KIND_VERSION}/kind-linux-amd64 \
    && chmod +x /usr/local/bin/kind

RUN curl -fsSL https://download.docker.com/linux/static/stable/x86_64/docker-${DOCKER_CLI_VERSION}.tgz \
  | tar -xz && mv docker/docker /usr/local/bin/docker && rm -rf docker

WORKDIR /workspace
CMD ["bash"]
