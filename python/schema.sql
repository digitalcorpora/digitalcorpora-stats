;; MySQL Schema for weblog

DROP TABLE IF EXISTS downloadable;
CREATE TABLE downloadable (
        id INTEGER NOT NULL AUTO_INCREMENT,
        path VARCHAR(255) NOT NULL,
        name VARCHAR(255) NOT NULL,
        size INTEGER NOT NULL,
        mtime DATETIME NOT NULL,
        tags JSON,
        primary key (id),
        unique index (path,name),
        index (name),
        index (size),
        index (mtime)
        );

DROP TABLE IF EXISTS download;
CREATE TABLE download (
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

        
