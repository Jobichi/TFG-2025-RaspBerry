FROM eclipse-mosquitto:2.0

# Copiamos la configuración y el archivo de contraseñas
COPY mosquitto/passwordfile /mosquitto/config/passwordfile

# Ajustamos permisos para que solo mosquitto pueda leer el archivo
RUN chmod 600 /mosquitto/config/passwordfile