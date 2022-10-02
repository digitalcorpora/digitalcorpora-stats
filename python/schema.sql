-- MySQL dump 10.13  Distrib 5.7.39, for Linux (x86_64)
--
-- Host: mysql.digitalcorpora.org    Database: dcstats
-- ------------------------------------------------------
-- Server version	8.0.28-0ubuntu0.20.04.3

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `downloadable`
--

DROP TABLE IF EXISTS `downloadable`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `downloadable` (
  `id` int NOT NULL AUTO_INCREMENT,
  `s3key` varchar(768) NOT NULL,
  `modified` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `bytes` bigint DEFAULT NULL,
  `mtime` timestamp NULL DEFAULT NULL,
  `tags` json DEFAULT NULL,
  `etag` varchar(64) DEFAULT NULL,
  `sha2_256` varchar(64) DEFAULT NULL,
  `sha3_256` varchar(64) DEFAULT NULL,
  `present` tinyint(1) DEFAULT '1',
  PRIMARY KEY (`id`),
  UNIQUE KEY `s3key` (`s3key`),
  KEY `bytes` (`bytes`),
  KEY `mtime` (`mtime`),
  KEY `etag` (`etag`),
  KEY `sha2_256` (`sha2_256`),
  KEY `sha3_256` (`sha3_256`)
) ENGINE=InnoDB AUTO_INCREMENT=7618242 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `downloads`
--

DROP TABLE IF EXISTS `downloads`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `downloads` (
  `id` int NOT NULL AUTO_INCREMENT,
  `did` int NOT NULL,
  `user_agent_id` int DEFAULT NULL,
  `remote_ipaddr` varchar(64) DEFAULT NULL,
  `dtime` datetime NOT NULL,
  `bytes_sent` int DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `did` (`did`),
  KEY `ipaddr` (`remote_ipaddr`),
  KEY `dtime` (`dtime`),
  KEY `bytes_sent` (`bytes_sent`),
  KEY `user_agent_id` (`user_agent_id`),
  CONSTRAINT `downloads_ibfk_1` FOREIGN KEY (`did`) REFERENCES `downloadable` (`id`),
  CONSTRAINT `downloads_ibfk_2` FOREIGN KEY (`user_agent_id`) REFERENCES `user_agents` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=9481657 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `user_agents`
--

DROP TABLE IF EXISTS `user_agents`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `user_agents` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_agent` varchar(128) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `user_agent` (`user_agent`)
) ENGINE=InnoDB AUTO_INCREMENT=4 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2022-10-01 14:56:37
