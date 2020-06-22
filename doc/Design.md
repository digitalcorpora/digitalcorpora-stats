# Goals and Design Criteria
## Overview
- Provide visitors to the digitalcorpora.org website with:
  * All files available for download (matrix view, searcahable)
  * Most popular downloads over the past week/month/year

- Ability to organize downloads by:
  * Operating system
  * Size of download
  * Kinds of artifacts present

- Automated operation.
  * Automatically parses log files and displays the results

- Analytics to include:
  * Countries from which data are downloaded?

- Analytics not to include:
  * Identities of individuals or organizations downloading information.

## Dataflow

1. Apache Combine Log File from download server is synchronized with web server using rsync.

2. Periodic (hourly?) job runs on web server and processes logfile
   line-by-line from when it previously left off.
   * Keep in a database the last ingest point so we can fseek().
   * Record hash of first 64K of file to detect file change.
   * Ingest only ingests downloads that we care about; ignores attacks.

3. Database consists of:
   * Table for each DOWNLOADABLE file (id, name, path, length, modified-date, tags as a JSON object)
   * Table for each DOWNLOAD (id, downloadid, time started, seconds, bytes downloaded, destination IP?, destination country? )
   * Table for tags (tag name, description)
   * Table for logfile containing (id, name, hash of first 64K, next point to start reading) 

4. After logfile is ingested, render statistics into JSON objects containing:
  * All downloadable objects  (perhaps a dump of the DOWNLOADABLE table)
  * Most popular DOWNLOADs (for last day, week, month, year)

  JSON objects will be stored in https://digitalcorpora.org/json/ directory

5. HTML/CSS/JS table runs in web browser, downloads JSON objects, and displays.
  * Can be seen directly.
  * Can be embedded in existing WordPress pages as an include or igrame.

## Software Quality
* GitHub Actions on every push to assure:
  - All self-tests run
  - PEP8 style guide enforced (except line length?)
* Test coverage for every method
  - Use automated test coverage tool conv 

# Roadmap and open Git issues.
## Milestone #1: Working infrastructure
1. `weblog` class can parse a CLF log file line

2. MySQL Schema.

3. `webdb` class that:
  - Can create mySql database
  - Can read N lines of logfile from a given position, create N weblog objects, and advance the pointer in database with current entry point.
  - Create DOWNLOADABLE entries for weblog objects that don't have corresponding DOWNLOADABLE entries.
  - Can insert weblog entries into database with correct normalization.

4. End-to-end tests that:
- [ ] Create a new MySQL database
- [ ] Loads a sample of log files (which have had the IP addresses changes for privacy protection)
- [ ] Verifies that database entries are created.
- [ ] Verifies that JSON objects have correct contents.

## Milestone #2: Prime-the-pump
1. Manually send a significant portion of the weblog from downloads server to wordpress server.
2. Manually run ingest
3. Manually review the MySQL database
4. Manually run the JSON generator.
5. Work on the HTML/CSS/JS pages until the results look nice.

## Milestone #3: Operational infrastructure
1. Set up periodic rsync job on downloads server.
2. Set up periodic ingest job on wordpress server.

## Milestone #4: Publicize

