# Dockerfile for web application service
#
# Installs the web application in "edit" mode so that modifications are
# immediately reflected.
#

FROM python:3.9-slim AS base

ENV NODE_MAJOR_VERSION=18

# Install system dependencies including build tools
RUN apt-get update \
 && apt-get install -y curl wget git libmagic1 make gcc g++ python3-dev \
 && curl -fsSL https://deb.nodesource.com/setup_${NODE_MAJOR_VERSION}.x | bash - \
 && apt-get install -y nodejs \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

# Install global npm packages
RUN npm install -g less bower \
    && echo '{ "allow_root": true }' > /root/.bowerrc

# Install dockerize
ENV DOCKERIZE_VERSION v0.6.1
RUN wget https://github.com/jwilder/dockerize/releases/download/$DOCKERIZE_VERSION/dockerize-linux-amd64-$DOCKERIZE_VERSION.tar.gz \
    && tar -C /usr/local/bin -xzvf dockerize-linux-amd64-$DOCKERIZE_VERSION.tar.gz \
    && rm dockerize-linux-amd64-$DOCKERIZE_VERSION.tar.gz

ENV ENVIRONMENT "development"
ENV PYTHONUNBUFFERED 1

WORKDIR /app

# Install Python requirements
COPY ./constraints.txt ./requirements*.txt ./
RUN pip install --no-cache-dir \
    -c constraints.txt \
    -r $( [ "$ENVIRONMENT" = "development" ] && echo "requirements-develop.txt" || echo "requirements.txt" )

# Copy application code
ADD . ./

FROM base AS development
ENV PYTHONDONTWRITEBYTECODE 1
ENV ENVIRONMENT "development"
RUN pip install -e .

FROM base AS production
ENV ENVIRONMENT "production"
RUN pip install .