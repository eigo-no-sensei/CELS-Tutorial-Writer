-- GEL Tutorial Writer archive schema v2.
-- Executable schema authority for D1. Lower-authority prose must not contradict this file.
-- Runtime writers must enable PRAGMA foreign_keys=ON on every connection.

CREATE TABLE archive_schema_migrations (
    version         INTEGER PRIMARY KEY CHECK (version > 0),
    name            TEXT NOT NULL,
    source_version  INTEGER NOT NULL CHECK (source_version >= 0),
    applied_at      TEXT NOT NULL
);

CREATE TABLE archive_sync_runs (
    run_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    source          TEXT NOT NULL DEFAULT 'gel',
    scope           TEXT NOT NULL DEFAULT 'full',
    status          TEXT NOT NULL CHECK (status IN ('running', 'complete', 'failed')),
    started_at      TEXT NOT NULL,
    completed_at    TEXT,
    CHECK ((status = 'running' AND completed_at IS NULL) OR status IN ('complete', 'failed'))
);

CREATE TABLE classes (
    class_id          INTEGER PRIMARY KEY,
    name              TEXT,
    course_code       TEXT,
    start_date        TEXT,
    end_date          TEXT,
    is_active         INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    source_present    INTEGER NOT NULL DEFAULT 1 CHECK (source_present IN (0, 1)),
    first_seen        TEXT NOT NULL,
    last_seen         TEXT NOT NULL,
    last_seen_run_id  INTEGER,
    presence_checked_run_id INTEGER,
    FOREIGN KEY (last_seen_run_id) REFERENCES archive_sync_runs(run_id) ON DELETE RESTRICT,
    FOREIGN KEY (presence_checked_run_id) REFERENCES archive_sync_runs(run_id) ON DELETE RESTRICT
);

CREATE TABLE students (
    uid                 INTEGER PRIMARY KEY,
    name                TEXT,
    cefr_level          INTEGER,
    school_name         TEXT,
    start_date          TEXT,
    end_date            TEXT,
    source_present      INTEGER NOT NULL DEFAULT 1 CHECK (source_present IN (0, 1)),
    first_seen          TEXT NOT NULL,
    last_seen           TEXT NOT NULL,
    last_seen_run_id    INTEGER,
    presence_checked_run_id INTEGER,
    FOREIGN KEY (last_seen_run_id) REFERENCES archive_sync_runs(run_id) ON DELETE RESTRICT,
    FOREIGN KEY (presence_checked_run_id) REFERENCES archive_sync_runs(run_id) ON DELETE RESTRICT
);

CREATE TABLE class_memberships (
    class_id              INTEGER NOT NULL,
    student_uid           INTEGER NOT NULL,
    attendance            INTEGER,
    tutorial_late         INTEGER CHECK (tutorial_late IN (0, 1) OR tutorial_late IS NULL),
    last_tutorial_ts      INTEGER,
    test_type             TEXT,
    last_test_ts          INTEGER,
    unmarked_exit_test    INTEGER CHECK (unmarked_exit_test IN (0, 1) OR unmarked_exit_test IS NULL),
    source_present        INTEGER NOT NULL DEFAULT 1 CHECK (source_present IN (0, 1)),
    first_seen            TEXT NOT NULL,
    last_seen             TEXT NOT NULL,
    last_seen_run_id      INTEGER,
    presence_checked_run_id INTEGER,
    PRIMARY KEY (class_id, student_uid),
    FOREIGN KEY (class_id) REFERENCES classes(class_id) ON DELETE RESTRICT,
    FOREIGN KEY (student_uid) REFERENCES students(uid) ON DELETE RESTRICT,
    FOREIGN KEY (last_seen_run_id) REFERENCES archive_sync_runs(run_id) ON DELETE RESTRICT,
    FOREIGN KEY (presence_checked_run_id) REFERENCES archive_sync_runs(run_id) ON DELETE RESTRICT
);

CREATE TABLE tutorial_identities (
    tutorial_id        INTEGER PRIMARY KEY,
    student_uid        INTEGER NOT NULL,
    tutorial_ts        INTEGER NOT NULL CHECK (tutorial_ts >= 0),
    source_present     INTEGER NOT NULL DEFAULT 1 CHECK (source_present IN (0, 1)),
    first_seen         TEXT NOT NULL,
    last_seen          TEXT NOT NULL,
    last_seen_run_id   INTEGER,
    presence_checked_run_id INTEGER,
    FOREIGN KEY (student_uid) REFERENCES students(uid) ON DELETE RESTRICT,
    FOREIGN KEY (last_seen_run_id) REFERENCES archive_sync_runs(run_id) ON DELETE RESTRICT,
    FOREIGN KEY (presence_checked_run_id) REFERENCES archive_sync_runs(run_id) ON DELETE RESTRICT
);

CREATE TABLE tutorial_source_states (
    source_state_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    student_uid           INTEGER NOT NULL,
    tutorial_ts           INTEGER NOT NULL CHECK (tutorial_ts >= 0),
    state_fingerprint     TEXT NOT NULL,
    tutorial_type         TEXT CHECK (tutorial_type IN ('Initial', 'Standard', 'Final') OR tutorial_type IS NULL),
    ttype_raw             TEXT,
    teacher_id            INTEGER,
    teacher_id_source     TEXT,
    teacher_name          TEXT,
    custom_date           TEXT,
    absent                INTEGER CHECK (absent IN (0, 1) OR absent IS NULL),
    overall_level         TEXT,
    speaking              TEXT,
    use_of_english        TEXT,
    writing               TEXT,
    listening             TEXT,
    reading               TEXT,
    speaking_before       TEXT,
    uoe_before            TEXT,
    writing_before        TEXT,
    listening_before      TEXT,
    exam_want             TEXT,
    exam_which            TEXT,
    exam_when             TEXT,
    self_listening        TEXT,
    self_reading          TEXT,
    self_writing          TEXT,
    self_speaking         TEXT,
    self_vocabulary       TEXT,
    self_grammar          TEXT,
    self_pronunciation    TEXT,
    aims                  TEXT,
    teacher_comments      TEXT,
    additional_comments   TEXT,
    source_method         TEXT,
    summary_url           TEXT,
    print_url             TEXT,
    edit_url              TEXT,
    summary_match_method  TEXT,
    source_present        INTEGER NOT NULL DEFAULT 1 CHECK (source_present IN (0, 1)),
    first_seen            TEXT NOT NULL,
    last_seen             TEXT NOT NULL,
    last_seen_run_id      INTEGER,
    presence_checked_run_id INTEGER,
    UNIQUE (student_uid, tutorial_ts, state_fingerprint),
    FOREIGN KEY (student_uid) REFERENCES students(uid) ON DELETE RESTRICT,
    FOREIGN KEY (last_seen_run_id) REFERENCES archive_sync_runs(run_id) ON DELETE RESTRICT,
    FOREIGN KEY (presence_checked_run_id) REFERENCES archive_sync_runs(run_id) ON DELETE RESTRICT
);

CREATE TABLE tutorial_source_field_evidence (
    source_state_id  INTEGER NOT NULL,
    field_name       TEXT NOT NULL CHECK (length(field_name) > 0),
    source_kind      TEXT NOT NULL CHECK (source_kind IN ('api', 'summary', 'edit', 'print', 'legacy')),
    presence         TEXT NOT NULL CHECK (presence IN ('present', 'present_blank', 'missing')),
    PRIMARY KEY (source_state_id, field_name, source_kind),
    FOREIGN KEY (source_state_id) REFERENCES tutorial_source_states(source_state_id) ON DELETE CASCADE
);

CREATE TABLE tutorial_collision_groups (
    collision_group_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    student_uid         INTEGER NOT NULL,
    tutorial_ts         INTEGER NOT NULL CHECK (tutorial_ts >= 0),
    collision_kind      TEXT NOT NULL CHECK (
        collision_kind IN ('identical_state', 'divergent_state', 'incomplete_evidence', 'ambiguous_unknown')
    ),
    source_present      INTEGER NOT NULL DEFAULT 1 CHECK (source_present IN (0, 1)),
    first_seen          TEXT NOT NULL,
    last_seen           TEXT NOT NULL,
    last_seen_run_id    INTEGER,
    presence_checked_run_id INTEGER,
    UNIQUE (student_uid, tutorial_ts),
    FOREIGN KEY (student_uid) REFERENCES students(uid) ON DELETE RESTRICT,
    FOREIGN KEY (last_seen_run_id) REFERENCES archive_sync_runs(run_id) ON DELETE RESTRICT,
    FOREIGN KEY (presence_checked_run_id) REFERENCES archive_sync_runs(run_id) ON DELETE RESTRICT
);

CREATE TABLE tutorial_collision_identities (
    collision_group_id  INTEGER NOT NULL,
    tutorial_id         INTEGER NOT NULL,
    PRIMARY KEY (collision_group_id, tutorial_id),
    FOREIGN KEY (collision_group_id) REFERENCES tutorial_collision_groups(collision_group_id) ON DELETE CASCADE,
    FOREIGN KEY (tutorial_id) REFERENCES tutorial_identities(tutorial_id) ON DELETE RESTRICT
);

CREATE TABLE tutorial_collision_states (
    collision_group_id  INTEGER NOT NULL,
    source_state_id     INTEGER NOT NULL,
    PRIMARY KEY (collision_group_id, source_state_id),
    FOREIGN KEY (collision_group_id) REFERENCES tutorial_collision_groups(collision_group_id) ON DELETE CASCADE,
    FOREIGN KEY (source_state_id) REFERENCES tutorial_source_states(source_state_id) ON DELETE RESTRICT
);

CREATE TABLE tutorial_state_associations (
    tutorial_id         INTEGER PRIMARY KEY,
    authority_status    TEXT NOT NULL CHECK (
        authority_status IN (
            'proven_per_tutorial',
            'shared_identical_collision',
            'ambiguous_divergent_collision',
            'incomplete_collision_evidence',
            'ambiguous_collision_unknown',
            'unmatched_source_state'
        )
    ),
    source_state_id     INTEGER,
    collision_group_id  INTEGER,
    proof_method        TEXT NOT NULL,
    first_seen          TEXT NOT NULL,
    last_seen           TEXT NOT NULL,
    CHECK (
        (authority_status IN ('proven_per_tutorial', 'shared_identical_collision') AND source_state_id IS NOT NULL)
        OR
        (authority_status IN (
            'ambiguous_divergent_collision',
            'incomplete_collision_evidence',
            'ambiguous_collision_unknown',
            'unmatched_source_state'
        ) AND source_state_id IS NULL)
    ),
    CHECK (
        (authority_status IN (
            'shared_identical_collision',
            'ambiguous_divergent_collision',
            'incomplete_collision_evidence',
            'ambiguous_collision_unknown'
        ) AND collision_group_id IS NOT NULL)
        OR
        (authority_status IN ('proven_per_tutorial', 'unmatched_source_state') AND collision_group_id IS NULL)
    ),
    FOREIGN KEY (tutorial_id) REFERENCES tutorial_identities(tutorial_id) ON DELETE CASCADE,
    FOREIGN KEY (source_state_id) REFERENCES tutorial_source_states(source_state_id) ON DELETE RESTRICT,
    FOREIGN KEY (collision_group_id) REFERENCES tutorial_collision_groups(collision_group_id) ON DELETE RESTRICT
);

CREATE TABLE scrape_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    action      TEXT,
    target      TEXT,
    status      TEXT,
    message     TEXT,
    timestamp   TEXT
);

-- Source-presence invalidation is allowed only against a completed sync run.
-- This prevents a failed/partial acquisition from marking preserved source rows absent.
CREATE TRIGGER classes_presence_insert_guard
BEFORE INSERT ON classes
WHEN NEW.source_present = 0 AND (
    NEW.presence_checked_run_id IS NULL OR NOT EXISTS (
        SELECT 1 FROM archive_sync_runs WHERE run_id=NEW.presence_checked_run_id AND status='complete'
    )
)
BEGIN
    SELECT RAISE(ABORT, 'classes source_present=0 requires a completed sync run');
END;
CREATE TRIGGER classes_presence_update_guard
BEFORE UPDATE OF source_present, presence_checked_run_id ON classes
WHEN NEW.source_present = 0 AND (
    NEW.presence_checked_run_id IS NULL OR NOT EXISTS (
        SELECT 1 FROM archive_sync_runs WHERE run_id=NEW.presence_checked_run_id AND status='complete'
    )
)
BEGIN
    SELECT RAISE(ABORT, 'classes source_present=0 requires a completed sync run');
END;

CREATE TRIGGER students_presence_insert_guard
BEFORE INSERT ON students
WHEN NEW.source_present = 0 AND (
    NEW.presence_checked_run_id IS NULL OR NOT EXISTS (
        SELECT 1 FROM archive_sync_runs WHERE run_id=NEW.presence_checked_run_id AND status='complete'
    )
)
BEGIN
    SELECT RAISE(ABORT, 'students source_present=0 requires a completed sync run');
END;
CREATE TRIGGER students_presence_update_guard
BEFORE UPDATE OF source_present, presence_checked_run_id ON students
WHEN NEW.source_present = 0 AND (
    NEW.presence_checked_run_id IS NULL OR NOT EXISTS (
        SELECT 1 FROM archive_sync_runs WHERE run_id=NEW.presence_checked_run_id AND status='complete'
    )
)
BEGIN
    SELECT RAISE(ABORT, 'students source_present=0 requires a completed sync run');
END;

CREATE TRIGGER class_memberships_presence_insert_guard
BEFORE INSERT ON class_memberships
WHEN NEW.source_present = 0 AND (
    NEW.presence_checked_run_id IS NULL OR NOT EXISTS (
        SELECT 1 FROM archive_sync_runs WHERE run_id=NEW.presence_checked_run_id AND status='complete'
    )
)
BEGIN
    SELECT RAISE(ABORT, 'class_memberships source_present=0 requires a completed sync run');
END;
CREATE TRIGGER class_memberships_presence_update_guard
BEFORE UPDATE OF source_present, presence_checked_run_id ON class_memberships
WHEN NEW.source_present = 0 AND (
    NEW.presence_checked_run_id IS NULL OR NOT EXISTS (
        SELECT 1 FROM archive_sync_runs WHERE run_id=NEW.presence_checked_run_id AND status='complete'
    )
)
BEGIN
    SELECT RAISE(ABORT, 'class_memberships source_present=0 requires a completed sync run');
END;

CREATE TRIGGER tutorial_identities_presence_insert_guard
BEFORE INSERT ON tutorial_identities
WHEN NEW.source_present = 0 AND (
    NEW.presence_checked_run_id IS NULL OR NOT EXISTS (
        SELECT 1 FROM archive_sync_runs WHERE run_id=NEW.presence_checked_run_id AND status='complete'
    )
)
BEGIN
    SELECT RAISE(ABORT, 'tutorial_identities source_present=0 requires a completed sync run');
END;
CREATE TRIGGER tutorial_identities_presence_update_guard
BEFORE UPDATE OF source_present, presence_checked_run_id ON tutorial_identities
WHEN NEW.source_present = 0 AND (
    NEW.presence_checked_run_id IS NULL OR NOT EXISTS (
        SELECT 1 FROM archive_sync_runs WHERE run_id=NEW.presence_checked_run_id AND status='complete'
    )
)
BEGIN
    SELECT RAISE(ABORT, 'tutorial_identities source_present=0 requires a completed sync run');
END;

CREATE TRIGGER tutorial_source_states_presence_insert_guard
BEFORE INSERT ON tutorial_source_states
WHEN NEW.source_present = 0 AND (
    NEW.presence_checked_run_id IS NULL OR NOT EXISTS (
        SELECT 1 FROM archive_sync_runs WHERE run_id=NEW.presence_checked_run_id AND status='complete'
    )
)
BEGIN
    SELECT RAISE(ABORT, 'tutorial_source_states source_present=0 requires a completed sync run');
END;
CREATE TRIGGER tutorial_source_states_presence_update_guard
BEFORE UPDATE OF source_present, presence_checked_run_id ON tutorial_source_states
WHEN NEW.source_present = 0 AND (
    NEW.presence_checked_run_id IS NULL OR NOT EXISTS (
        SELECT 1 FROM archive_sync_runs WHERE run_id=NEW.presence_checked_run_id AND status='complete'
    )
)
BEGIN
    SELECT RAISE(ABORT, 'tutorial_source_states source_present=0 requires a completed sync run');
END;

CREATE TRIGGER tutorial_collision_groups_presence_insert_guard
BEFORE INSERT ON tutorial_collision_groups
WHEN NEW.source_present = 0 AND (
    NEW.presence_checked_run_id IS NULL OR NOT EXISTS (
        SELECT 1 FROM archive_sync_runs WHERE run_id=NEW.presence_checked_run_id AND status='complete'
    )
)
BEGIN
    SELECT RAISE(ABORT, 'tutorial_collision_groups source_present=0 requires a completed sync run');
END;
CREATE TRIGGER tutorial_collision_groups_presence_update_guard
BEFORE UPDATE OF source_present, presence_checked_run_id ON tutorial_collision_groups
WHEN NEW.source_present = 0 AND (
    NEW.presence_checked_run_id IS NULL OR NOT EXISTS (
        SELECT 1 FROM archive_sync_runs WHERE run_id=NEW.presence_checked_run_id AND status='complete'
    )
)
BEGIN
    SELECT RAISE(ABORT, 'tutorial_collision_groups source_present=0 requires a completed sync run');
END;

-- Collision membership and authoritative association rows must stay within the
-- same student/timestamp reconciliation key.
CREATE TRIGGER collision_identity_key_guard
BEFORE INSERT ON tutorial_collision_identities
WHEN NOT EXISTS (
    SELECT 1
    FROM tutorial_collision_groups AS g
    JOIN tutorial_identities AS i
      ON i.student_uid = g.student_uid AND i.tutorial_ts = g.tutorial_ts
    WHERE g.collision_group_id = NEW.collision_group_id
      AND i.tutorial_id = NEW.tutorial_id
)
BEGIN
    SELECT RAISE(ABORT, 'collision identity must match collision group student/timestamp');
END;

CREATE TRIGGER collision_state_key_guard
BEFORE INSERT ON tutorial_collision_states
WHEN NOT EXISTS (
    SELECT 1
    FROM tutorial_collision_groups AS g
    JOIN tutorial_source_states AS s
      ON s.student_uid = g.student_uid AND s.tutorial_ts = g.tutorial_ts
    WHERE g.collision_group_id = NEW.collision_group_id
      AND s.source_state_id = NEW.source_state_id
)
BEGIN
    SELECT RAISE(ABORT, 'collision state must match collision group student/timestamp');
END;

CREATE TRIGGER tutorial_state_association_key_guard
BEFORE INSERT ON tutorial_state_associations
WHEN (
    NEW.source_state_id IS NOT NULL AND NOT EXISTS (
        SELECT 1
        FROM tutorial_identities AS i
        JOIN tutorial_source_states AS s
          ON s.student_uid = i.student_uid AND s.tutorial_ts = i.tutorial_ts
        WHERE i.tutorial_id = NEW.tutorial_id
          AND s.source_state_id = NEW.source_state_id
    )
) OR (
    NEW.collision_group_id IS NOT NULL AND NOT EXISTS (
        SELECT 1
        FROM tutorial_identities AS i
        JOIN tutorial_collision_groups AS g
          ON g.student_uid = i.student_uid AND g.tutorial_ts = i.tutorial_ts
        WHERE i.tutorial_id = NEW.tutorial_id
          AND g.collision_group_id = NEW.collision_group_id
    )
)
BEGIN
    SELECT RAISE(ABORT, 'tutorial association must match identity student/timestamp');
END;

CREATE TRIGGER tutorial_state_association_update_key_guard
BEFORE UPDATE OF source_state_id, collision_group_id, tutorial_id ON tutorial_state_associations
WHEN (
    NEW.source_state_id IS NOT NULL AND NOT EXISTS (
        SELECT 1
        FROM tutorial_identities AS i
        JOIN tutorial_source_states AS s
          ON s.student_uid = i.student_uid AND s.tutorial_ts = i.tutorial_ts
        WHERE i.tutorial_id = NEW.tutorial_id
          AND s.source_state_id = NEW.source_state_id
    )
) OR (
    NEW.collision_group_id IS NOT NULL AND NOT EXISTS (
        SELECT 1
        FROM tutorial_identities AS i
        JOIN tutorial_collision_groups AS g
          ON g.student_uid = i.student_uid AND g.tutorial_ts = i.tutorial_ts
        WHERE i.tutorial_id = NEW.tutorial_id
          AND g.collision_group_id = NEW.collision_group_id
    )
)
BEGIN
    SELECT RAISE(ABORT, 'tutorial association must match identity student/timestamp');
END;

CREATE INDEX idx_class_memberships_student
    ON class_memberships(student_uid);
CREATE INDEX idx_tutorial_identities_student_ts
    ON tutorial_identities(student_uid, tutorial_ts);
CREATE INDEX idx_tutorial_identities_present
    ON tutorial_identities(source_present, student_uid);
CREATE INDEX idx_tutorial_source_states_student_ts
    ON tutorial_source_states(student_uid, tutorial_ts);
CREATE INDEX idx_tutorial_source_states_present
    ON tutorial_source_states(source_present, student_uid);
CREATE INDEX idx_collision_groups_student_ts
    ON tutorial_collision_groups(student_uid, tutorial_ts);
CREATE INDEX idx_collision_identities_tutorial
    ON tutorial_collision_identities(tutorial_id);
CREATE INDEX idx_collision_states_state
    ON tutorial_collision_states(source_state_id);
CREATE INDEX idx_state_associations_source
    ON tutorial_state_associations(source_state_id);

CREATE VIEW tutorial_revision_state AS
SELECT
    i.tutorial_id,
    i.student_uid,
    i.tutorial_ts,
    i.source_present AS identity_source_present,
    a.authority_status,
    a.collision_group_id,
    a.source_state_id,
    s.tutorial_type,
    s.ttype_raw,
    s.teacher_id,
    s.teacher_id_source,
    s.teacher_name,
    s.custom_date,
    s.absent,
    s.overall_level,
    s.speaking,
    s.use_of_english,
    s.writing,
    s.listening,
    s.reading,
    s.speaking_before,
    s.uoe_before,
    s.writing_before,
    s.listening_before,
    s.exam_want,
    s.exam_which,
    s.exam_when,
    s.self_listening,
    s.self_reading,
    s.self_writing,
    s.self_speaking,
    s.self_vocabulary,
    s.self_grammar,
    s.self_pronunciation,
    s.aims,
    s.teacher_comments,
    s.additional_comments
FROM tutorial_identities AS i
LEFT JOIN tutorial_state_associations AS a ON a.tutorial_id = i.tutorial_id
LEFT JOIN tutorial_source_states AS s ON s.source_state_id = a.source_state_id;

PRAGMA user_version = 2;
