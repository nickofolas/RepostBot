CREATE TABLE IF NOT EXISTS subreddits (
    name    VARCHAR(21) PRIMARY KEY,
    indexed BOOLEAN
);

CREATE TABLE IF NOT EXISTS indexed_submissions (
    id VARCHAR(10) PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS media_storage (
    hash          VARCHAR(32),
    submission_id VARCHAR(10),
    subname       VARCHAR(21),
    PRIMARY KEY (submission_id, hash)
);
