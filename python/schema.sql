SET FOREIGN_KEY_CHECKS=0;

DROP TABLE IF EXISTS downloadable;
CREATE TABLE downloadable (
        id INTEGER NOT NULL AUTO_INCREMENT,
        dirname VARCHAR(255) NOT NULL,
        basename VARCHAR(255) NOT NULL,
        size INTEGER ,
        mtime DATETIME,
        tags JSON,
        primary key (id),
        unique index (dirname,basename),
        index (basename),
        index (size),
        index (mtime)
        );

DROP TABLE IF EXISTS downloads;
CREATE TABLE downloads (
        id INTEGER NOT NULL AUTO_INCREMENT,
        did INTEGER NOT NULL,
        ipaddr VARCHAR(64) NOT NULL,
        dtime DATETIME NOT NULL,
        request VARCHAR(255) NOT NULL,
        user VARCHAR(255),
        referrer VARCHAR(255),
        agent VARCHAR(255),
        PRIMARY KEY (id),
        FOREIGN KEY (did) REFERENCES downloadable(id),
        INDEX (ipaddr),
        INDEX (dtime),
        INDEX (user),
        INDEX (referrer),
        INDEX (agent)
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

