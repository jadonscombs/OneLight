/*
TABLE: devices
    id:
    name:
    model:
    owner:


TABLE: users
    id:
    username:
    email:
    password_hash:


Notes:
- Ownership of each smart device is indicated by 'owner' field in Devices table
*/


DROP Table IF EXISTS users;
DROP TABLE IF EXISTS devices;

CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    username VARCHAR(50) NOT NULL,
    email VARCHAR(80) NOT NULL,
    password_hash VARCHAR(255) NOT NULL
);

CREATE TABLE devices (
    id INTEGER PRIMARY KEY,
    'name' VARCHAR(75) NOT NULL,
    model VARCHAR(50) NOT NULL,
    'owner' VARCHAR(75) NOT NULL,
    FOREIGN KEY ('owner') REFERENCES users(username)
);