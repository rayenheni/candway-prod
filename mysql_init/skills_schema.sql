-- Advanced Skills Storage Schema for Phase 1
-- MySQL 8 compatible

SET NAMES utf8mb4;

DROP PROCEDURE IF EXISTS GetUserSkillsFast;
DROP TABLE IF EXISTS query_profiler;
DROP TABLE IF EXISTS skill_sync_status;
DROP TABLE IF EXISTS cache_invalidation;
DROP TABLE IF EXISTS performance_metrics;
DROP TABLE IF EXISTS certifications;
DROP TABLE IF EXISTS experience_timeline;
DROP TABLE IF EXISTS candidate_skills;
DROP TABLE IF EXISTS skill_expressions;
DROP TABLE IF EXISTS skill_categories;

CREATE TABLE skill_categories (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(100) UNIQUE NOT NULL,
    parent_category_id INT NULL,
    weight_coefficient DECIMAL(4,2) DEFAULT 1.00,
    relevance_threshold DECIMAL(4,2) DEFAULT 0.70,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_category_name (name),
    INDEX idx_parent_category (parent_category_id),
    CONSTRAINT fk_skill_category_parent
        FOREIGN KEY (parent_category_id) REFERENCES skill_categories(id)
);

CREATE TABLE skill_expressions (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(255) NOT NULL,
    category_id INT NOT NULL,
    expression_pattern TEXT,
    confidence_score DECIMAL(4,2) DEFAULT 0.80,
    frequency_score INT DEFAULT 0,
    related_skills JSON,
    synonyms JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FULLTEXT INDEX idx_skill_fulltext (name, expression_pattern),
    INDEX idx_category (category_id),
    INDEX idx_confidence (confidence_score),
    INDEX idx_frequency (frequency_score),
    CONSTRAINT fk_skill_expressions_category
        FOREIGN KEY (category_id) REFERENCES skill_categories(id)
);

CREATE TABLE candidate_skills (
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_id VARCHAR(255) NOT NULL,
    skill_id INT NULL,
    skill_name VARCHAR(255) NOT NULL,
    category VARCHAR(100),
    confidence_score DECIMAL(4,2) DEFAULT 0.00,
    experience_level ENUM('beginner', 'intermediate', 'advanced', 'expert') DEFAULT 'intermediate',
    relevance_score DECIMAL(4,2) DEFAULT 0.00,
    evidence_snippets JSON,
    experience_months INT DEFAULT 0,
    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_user_id (user_id),
    INDEX idx_skill_name (skill_name),
    INDEX idx_category (category),
    INDEX idx_confidence (confidence_score),
    INDEX idx_experience_level (experience_level),
    INDEX idx_composite_search (user_id, category, experience_level),
    CONSTRAINT fk_candidate_skills_skill
        FOREIGN KEY (skill_id) REFERENCES skill_expressions(id)
);

CREATE TABLE experience_timeline (
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_id VARCHAR(255) NOT NULL,
    company_name VARCHAR(255) NOT NULL,
    role_title VARCHAR(255) NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NULL,
    duration_months INT GENERATED ALWAYS AS (
        TIMESTAMPDIFF(MONTH, start_date, COALESCE(end_date, CURDATE()))
    ) STORED,
    progression_level DECIMAL(4,2) DEFAULT 2.00,
    skills_developed JSON,
    key_achievements JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_user_timeline (user_id, start_date),
    INDEX idx_company_role (company_name, role_title),
    INDEX idx_duration (duration_months)
);

CREATE TABLE certifications (
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_id VARCHAR(255) NOT NULL,
    certification_name VARCHAR(255) NOT NULL,
    issuer VARCHAR(255) NOT NULL,
    credential_id VARCHAR(255),
    issue_date DATE,
    expiry_date DATE,
    verification_status ENUM('verified', 'unverified', 'pending', 'expired') DEFAULT 'unverified',
    certification_url VARCHAR(500),
    relevance_score DECIMAL(4,2) DEFAULT 0.50,
    industry_category VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_user_certifications (user_id),
    INDEX idx_issuer (issuer),
    INDEX idx_status (verification_status),
    INDEX idx_relevance (relevance_score),
    INDEX idx_expiry (expiry_date)
);

CREATE TABLE performance_metrics (
    id INT PRIMARY KEY AUTO_INCREMENT,
    operation_type VARCHAR(50) NOT NULL,
    execution_time_ms INT NOT NULL,
    user_id VARCHAR(255),
    cache_hit BOOLEAN DEFAULT FALSE,
    error_type VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_operation_type (operation_type),
    INDEX idx_execution_time (execution_time_ms),
    INDEX idx_user_performance (user_id, created_at),
    INDEX idx_cache_performance (cache_hit, created_at)
);

CREATE TABLE cache_invalidation (
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_id VARCHAR(255) NOT NULL,
    cache_key VARCHAR(255) NOT NULL,
    invalidated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    reason VARCHAR(50),
    INDEX idx_user_cache (user_id, cache_key),
    INDEX idx_invalidated_at (invalidated_at)
);

CREATE TABLE skill_sync_status (
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_id VARCHAR(255) UNIQUE NOT NULL,
    last_sync TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    skills_hash VARCHAR(64),
    sync_status ENUM('synced', 'dirty', 'error') DEFAULT 'synced',
    error_message TEXT,
    INDEX idx_sync_status (sync_status),
    INDEX idx_last_sync (last_sync)
);

CREATE TABLE query_profiler (
    id INT PRIMARY KEY AUTO_INCREMENT,
    query_type VARCHAR(50) NOT NULL,
    query_text TEXT,
    execution_time_ms INT NOT NULL,
    rows_examined INT DEFAULT 0,
    rows_affected INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_query_type (query_type),
    INDEX idx_execution_time (execution_time_ms),
    INDEX idx_created_at (created_at)
);

INSERT INTO skill_categories (name, weight_coefficient, relevance_threshold) VALUES
('Programming', 1.00, 0.70),
('Web Frameworks', 0.90, 0.75),
('Databases', 0.85, 0.70),
('Cloud Platforms', 1.00, 0.80),
('Data Science', 1.10, 0.75),
('DevOps', 0.95, 0.72),
('Soft Skills', 0.80, 0.65),
('Methodologies', 0.85, 0.68);

INSERT INTO skill_expressions (name, category_id, confidence_score, related_skills, synonyms) VALUES
('Python', 1, 0.95, '["Django","Flask","FastAPI"]', '["python3","py"]'),
('JavaScript', 1, 0.92, '["TypeScript","Node.js","React"]', '["js","ecmascript"]'),
('MySQL', 3, 0.90, '["SQL","PostgreSQL"]', '["mysql8"]'),
('Docker', 6, 0.90, '["Kubernetes","CI/CD"]', '["containerization"]'),
('Machine Learning', 5, 0.88, '["Deep Learning","NLP"]', '["ml"]');

DELIMITER $$
CREATE PROCEDURE GetUserSkillsFast(IN p_user_id VARCHAR(255))
BEGIN
    SELECT
        skill_name,
        category,
        confidence_score,
        experience_level,
        relevance_score,
        updated_at
    FROM candidate_skills
    WHERE user_id = p_user_id
    ORDER BY relevance_score DESC, confidence_score DESC
    LIMIT 200;
END $$
DELIMITER ;
