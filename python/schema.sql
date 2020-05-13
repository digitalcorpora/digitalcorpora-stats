;; MySQL Schema

CREATE TALBE weblog (
  id int not null auto_increment,
  ipaddr varchar(64) not null,
  when datetime not null,
  request varchar(255) not null,
  user varchar(255),
  referrer varchar(255),
  agent varchar(255),
  PRIMARY KEY (id),
  INDEX (ipaddr),
  INDEX (when),
  INDEX (user),
  INDEX (referrer),
  INDEX (agent)
)
         
