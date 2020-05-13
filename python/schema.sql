;; MySQL Schema

CREATE TALBE weblog (
  id INTEGER NOT NULL AUTO_INCREMENT,
  ipaddr VARCHAR(64) NOT NULL,
  when DATETIME NOT NULL,
  request VARCHAR(255) NOT NULL,
  user VARCHAR(255),
  referrer VARCHAR(255),
  agent VARCHAR(255),
  PRIMARY KEY (id),
  INDEX (ipaddr),
  INDEX (when),
  INDEX (user),
  INDEX (referrer),
  INDEX (agent)
);
         
