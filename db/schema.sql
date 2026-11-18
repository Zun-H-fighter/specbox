CREATE TABLE users (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  email VARCHAR(255) NOT NULL UNIQUE,
  name VARCHAR(100) NOT NULL,
  major VARCHAR(100),
  desired_fields JSON,
  skills JSON,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) DEFAULT CHARSET = utf8mb4;

CREATE TABLE postings (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  source ENUM('worknet', 'sample') NOT NULL,
  source_id VARCHAR(100) NOT NULL,
  company VARCHAR(200) NOT NULL,
  title VARCHAR(300) NOT NULL,
  deadline DATE,
  deadline_raw VARCHAR(50),
  jobs_cd VARCHAR(20),
  enter_tp_cd CHAR(1),
  requirements_text TEXT,
  preferred_text TEXT,
  submit_doc_raw TEXT,
  required_docs JSON,
  keywords JSON,
  url VARCHAR(500),
  collected_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_postings_source (source, source_id)
) DEFAULT CHARSET = utf8mb4;

CREATE TABLE recommendations (
  user_id BIGINT NOT NULL,
  posting_id BIGINT NOT NULL,
  score DECIMAL(5, 4) NOT NULL,
  matched_keywords JSON,
  computed_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (user_id, posting_id),
  FOREIGN KEY (user_id) REFERENCES users (id),
  FOREIGN KEY (posting_id) REFERENCES postings (id)
) DEFAULT CHARSET = utf8mb4;

CREATE TABLE documents (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  user_id BIGINT NOT NULL,
  doc_type ENUM('resume', 'enrollment', 'graduation', 'graduation_expected', 'transcript',
                'english_score', 'english_speaking', 'certificate', 'portfolio', 'other') NOT NULL,
  title VARCHAR(200) NOT NULL,
  issued_on DATE,
  expires_on DATE,
  score_value VARCHAR(20),
  s3_key VARCHAR(500),
  link_url VARCHAR(500),
  uploaded_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users (id)
) DEFAULT CHARSET = utf8mb4;

CREATE TABLE applications (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  user_id BIGINT NOT NULL,
  posting_id BIGINT NOT NULL,
  status ENUM('active', 'submitted', 'closed') NOT NULL DEFAULT 'active',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_applications (user_id, posting_id),
  FOREIGN KEY (user_id) REFERENCES users (id),
  FOREIGN KEY (posting_id) REFERENCES postings (id)
) DEFAULT CHARSET = utf8mb4;

CREATE TABLE checklist_items (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  application_id BIGINT NOT NULL,
  doc_type ENUM('resume', 'enrollment', 'graduation', 'graduation_expected', 'transcript',
                'english_score', 'english_speaking', 'certificate', 'portfolio', 'other') NOT NULL,
  `rule` JSON,
  document_id BIGINT,
  state ENUM('ready', 'missing', 'reissue_needed', 'retest_needed') NOT NULL DEFAULT 'missing',
  FOREIGN KEY (application_id) REFERENCES applications (id),
  FOREIGN KEY (document_id) REFERENCES documents (id)
) DEFAULT CHARSET = utf8mb4;

CREATE TABLE notifications (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  user_id BIGINT NOT NULL,
  application_id BIGINT NOT NULL,
  kind ENUM('deadline_d3', 'deadline_d1', 'reissue_reminder', 'retest_reminder') NOT NULL,
  send_on DATE NOT NULL,
  sent_at DATETIME,
  dedup_key VARCHAR(100) NOT NULL UNIQUE,
  FOREIGN KEY (user_id) REFERENCES users (id),
  FOREIGN KEY (application_id) REFERENCES applications (id)
) DEFAULT CHARSET = utf8mb4;
