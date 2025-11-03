CREATE DATABASE IF NOT EXISTS devices_db;
USE devices_db;

-- === Tabla de dispositivos registrados ===
CREATE TABLE IF NOT EXISTS devices (
  device_name VARCHAR(64) PRIMARY KEY,
  last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- === Tabla de sensores ===
CREATE TABLE IF NOT EXISTS sensors (
  id INT,
  device_name VARCHAR(64),
  name VARCHAR(64),
  location VARCHAR(64),
  state VARCHAR(128),
  PRIMARY KEY (id, device_name)
);

-- === Tabla de actuadores ===
CREATE TABLE IF NOT EXISTS actuators (
  id INT,
  device_name VARCHAR(64),
  name VARCHAR(64),
  location VARCHAR(64),
  state VARCHAR(128),
  PRIMARY KEY (id, device_name)
);

-- === Tabla de alertas ===
CREATE TABLE IF NOT EXISTS alerts (
  id INT AUTO_INCREMENT PRIMARY KEY,
  device_name VARCHAR(64) NOT NULL,
  component_name VARCHAR(64) NOT NULL,
  location VARCHAR(64),
  state VARCHAR(128),
  message TEXT,
  timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
