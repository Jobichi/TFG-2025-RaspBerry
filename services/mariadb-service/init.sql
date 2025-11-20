-- ================================
--  BASE DE DATOS PRINCIPAL
-- ================================
CREATE DATABASE IF NOT EXISTS devices_db;
USE devices_db;

-- ================================
--  TABLA: devices
-- ================================
CREATE TABLE IF NOT EXISTS devices (
  device_name VARCHAR(64) PRIMARY KEY,
  last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);


-- ================================
--  TABLA: sensors
-- ================================
CREATE TABLE IF NOT EXISTS sensors (
  id INT NOT NULL,
  device_name VARCHAR(64) NOT NULL,
  name VARCHAR(64),
  location VARCHAR(64),
  value FLOAT,
  unit VARCHAR(16),
  last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

  PRIMARY KEY (id, device_name),

  FOREIGN KEY (device_name)
    REFERENCES devices(device_name)
    ON DELETE CASCADE
);

-- Índice para búsquedas rápidas
CREATE INDEX idx_sensors_device ON sensors(device_name);


-- ================================
--  TABLA: actuators
-- ================================
CREATE TABLE IF NOT EXISTS actuators (
  id INT NOT NULL,
  device_name VARCHAR(64) NOT NULL,
  name VARCHAR(64),
  location VARCHAR(64),
  state VARCHAR(128),
  last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

  PRIMARY KEY (id, device_name),

  FOREIGN KEY (device_name)
    REFERENCES devices(device_name)
    ON DELETE CASCADE
);

-- Índice para búsquedas rápidas
CREATE INDEX idx_actuators_device ON actuators(device_name);


-- ================================
--  TABLA: alerts
-- ================================
CREATE TABLE IF NOT EXISTS alerts (
  id INT AUTO_INCREMENT PRIMARY KEY,

  device_name VARCHAR(64) NOT NULL,
  component_type VARCHAR(16),    -- 'sensor' o 'actuator'
  component_id INT,              -- ID dentro del ESP32
  component_name VARCHAR(64),
  location VARCHAR(64),

  status VARCHAR(128),
  message TEXT,
  severity VARCHAR(16) DEFAULT 'medium',
  code INT,
  timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

  FOREIGN KEY (device_name)
    REFERENCES devices(device_name)
    ON DELETE CASCADE
);

-- Índices recomendados
CREATE INDEX idx_alerts_severity ON alerts(severity, timestamp);
CREATE INDEX idx_alerts_device ON alerts(device_name);


-- ================================
--  TABLA: system_logs (opcional)
-- ================================
CREATE TABLE IF NOT EXISTS system_logs (
  id INT AUTO_INCREMENT PRIMARY KEY,
  timestamp DATETIME NOT NULL,
  topic VARCHAR(255),
  event_type VARCHAR(50),
  payload JSON
);

-- Índices útiles
CREATE INDEX idx_logs_event ON system_logs(event_type);
CREATE INDEX idx_logs_topic ON system_logs(topic);
