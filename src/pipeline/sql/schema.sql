-- CourseIQ BigQuery schema. Tables are populated by src/pipeline/gcs_to_bq.py
-- (loaded from pandas DataFrames, so types here are documentation + a
-- reference for anyone querying directly - the Python loader is the source
-- of truth for the actual schema passed to the BigQuery client).

CREATE TABLE IF NOT EXISTS `{project}.{dataset}.courses` (
    uuid STRING NOT NULL,
    number INT64,
    name STRING,
    subject_code STRING,
    subject_name STRING,
    subject_abbreviation STRING
);

-- Grain: one row per course offering x section x instructor.
-- GPA is NOT provided directly by the /courses/{uuid}/grades endpoint -
-- it's derived from the grade counts in feature engineering (see
-- src/pipeline/features.py) using standard UW grade points.
CREATE TABLE IF NOT EXISTS `{project}.{dataset}.grade_distributions` (
    course_uuid STRING NOT NULL,
    term_code INT64,
    section_number STRING,
    instructor_name STRING,
    total INT64,
    a_count INT64,
    ab_count INT64,
    b_count INT64,
    bc_count INT64,
    c_count INT64,
    d_count INT64,
    f_count INT64,
    s_count INT64,
    u_count INT64,
    cr_count INT64,
    n_count INT64,
    p_count INT64,
    i_count INT64,
    nw_count INT64,
    nr_count INT64,
    other_count INT64
);

CREATE TABLE IF NOT EXISTS `{project}.{dataset}.rmp_ratings` (
    rmp_id STRING NOT NULL,
    first_name STRING,
    last_name STRING,
    department STRING,
    avg_rating FLOAT64,
    avg_difficulty FLOAT64,
    would_take_again_percent FLOAT64,
    num_ratings INT64
);

-- Crosswalk between Madgrades instructor names (free text, no stable ID)
-- and RMP instructor records, produced by fuzzy name matching since the
-- two sources share no common key.
CREATE TABLE IF NOT EXISTS `{project}.{dataset}.instructor_match` (
    madgrades_instructor_name STRING NOT NULL,
    rmp_id STRING,
    match_score FLOAT64
);
