CREATE DATABASE IF NOT EXISTS devices_db;
USE devices_db;

CREATE TABLE IF NOT EXISTS devices (
  device_name VARCHAR(64) PRIMARY KEY,
  last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sensors (
  id INT,
  device_name VARCHAR(64),
  name VARCHAR(64),
  location VARCHAR(64),
  state VARCHAR(128),
  PRIMARY KEY (id, device_name)
);

CREATE TABLE IF NOT EXISTS actuators (
  id INT,
  device_name VARCHAR(64),
  name VARCHAR(64),
  location VARCHAR(64),
  state VARCHAR(128),
  PRIMARY KEY (id, device_name)
);
