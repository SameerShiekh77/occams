#
# Sets up a development container
#

FROM postgres:12.2

# Remove problematic repository entries and install packages
RUN rm -rf /etc/apt/sources.list.d/* \
 && sed -i '/buster-pgdg/d' /etc/apt/sources.list \
 && sed -i '/buster-backports/d' /etc/apt/sources.list \
 && sed -i '/pgdg/d' /etc/apt/sources.list \
 && sed -i '/backports/d' /etc/apt/sources.list \
 && apt-get update \
 && apt-get install wget make -y \
 && apt-get clean

ENV PG_AUDIT_JSON_VERSION 1.0.2

RUN wget https://github.com/m-martinez/pg-audit-json/archive/${PG_AUDIT_JSON_VERSION}.tar.gz \
    && tar -xvf ${PG_AUDIT_JSON_VERSION}.tar.gz \
    && cd pg-audit-json-${PG_AUDIT_JSON_VERSION} \
    && make install \
    && echo "CREATE EXTENSION \"pg-audit-json\";" > /docker-entrypoint-initdb.d/000-pg-audit-json.sql