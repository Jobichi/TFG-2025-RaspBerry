FROM eclipse-mosquitto:2.0

# Copiamos configuración y credenciales
COPY mosquitto/config/mosquitto.conf /mosquitto/config/mosquitto.conf
COPY mosquitto/passwordfile /mosquitto/config/passwordfile

# Ajustamos permisos y propietario
RUN chmod 600 /mosquitto/config/passwordfile && \
    chmod 644 /mosquitto/config/mosquitto.conf && \
    chown -R mosquitto:mosquitto /mosquitto/config
