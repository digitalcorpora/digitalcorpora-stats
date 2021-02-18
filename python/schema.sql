SET FOREIGN_KEY_CHECKS=0;

DROP TABLE IF EXISTS downloadable;
CREATE TABLE downloadable (
        id INTEGER NOT NULL AUTO_INCREMENT,
        s3key VARCHAR(1024) NOT NULL,
        bytes INTEGER ,
        mtime DATETIME,
        tags JSON,
        etag     varchar(64),
        sha2_256 varchar(64),
        sha3_256 varchar(64),
        primary key (id),
        unique index (s3key),
        index (bytes),
        index (mtime),
        index (etag),
        index (sha2_256),
        index (sha3_256)
        );

DROP TABLE IF EXISTS downloads;
CREATE TABLE downloads (
        id INTEGER NOT NULL AUTO_INCREMENT,
        did INTEGER NOT NULL,
        ipaddr VARCHAR(64) NOT NULL,
        dtime DATETIME NOT NULL,
        PRIMARY KEY (id),
        FOREIGN KEY (did) REFERENCES downloadable(id),
        INDEX (ipaddr),
        INDEX (dtime)
        );

DROP TABLE IF EXISTS tags;
CREATE TABLE tags (
        id INTEGER NOT NULL AUTO_INCREMENT,
        tag JSON NOT NULL,
        description VARCHAR(255) NOT NULL,
        PRIMARY KEY (id)
);

DROP TABLE IF EXISTS logfile;
CREATE TABLE logfile (
        id INTEGER NOT NULL AUTO_INCREMENT,
        path varchar(255) NOT NULL,
        hash_first64k varchar(255) NOT NULL,
        offset INTEGER NOT NULL,
        PRIMARY KEY (id),
        INDEX (path)
);


SET FOREIGN_KEY_CHECKS=1;
