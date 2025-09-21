FROM eclipse-mosquitto:2.0

# Copiamos configuración y credenciales
COPY config/mosquitto.conf /mosquitto/config/mosquitto.conf
COPY passwordfile /mosquitto/config/passwordfile

# Ajustamos permisos y propietario
RUN chmod 600 /config/passwordfile && \
    chmod 644 /config/mosquitto.conf && \
    chown -R mosquitto:mosquitto /config
