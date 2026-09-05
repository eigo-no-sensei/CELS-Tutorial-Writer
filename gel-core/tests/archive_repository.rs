use gel_core::{ArchiveRepository, ArchiveRevisionAvailability, ARCHIVE_SCHEMA_VERSION};
use rusqlite::Connection;
use std::fs;
use std::path::PathBuf;
use std::time::{SystemTime, UNIX_EPOCH};

const SCHEMA_SQL: &str = include_str!("../../schema/archive_v2.sql");

fn temp_path(label: &str) -> PathBuf {
    let nonce = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .as_nanos();
    std::env::temp_dir().join(format!(
        "gel-d2-public-{label}-{}-{nonce}.sqlite",
        std::process::id()
    ))
}

fn create_v2(path: &PathBuf) {
    let connection = Connection::open(path).unwrap();
    connection.execute_batch("PRAGMA foreign_keys=ON;").unwrap();
    connection.execute_batch(SCHEMA_SQL).unwrap();
    connection
        .execute(
            "INSERT INTO archive_schema_migrations(version,name,source_version,applied_at)\n             VALUES (?1,'repository_test',0,'2026-08-26T00:00:00Z')",
            [ARCHIVE_SCHEMA_VERSION],
        )
        .unwrap();
}

#[test]
fn public_repository_opens_v2_read_only_and_exposes_navigation_models() {
    let path = temp_path("navigation");
    create_v2(&path);
    let connection = Connection::open(&path).unwrap();
    connection
        .execute(
            "INSERT INTO students(uid,name,source_present,first_seen,last_seen)\n             VALUES (10,'Student',1,'a','a')",
            [],
        )
        .unwrap();
    connection
        .execute(
            "INSERT INTO classes(class_id,name,is_active,source_present,first_seen,last_seen)\n             VALUES (20,'Class',1,1,'a','a')",
            [],
        )
        .unwrap();
    connection
        .execute(
            "INSERT INTO class_memberships(\n                class_id,student_uid,source_present,first_seen,last_seen\n             ) VALUES (20,10,1,'a','a')",
            [],
        )
        .unwrap();
    connection
        .execute(
            "INSERT INTO tutorial_identities(\n                tutorial_id,student_uid,tutorial_ts,source_present,first_seen,last_seen\n             ) VALUES (100,10,111,1,'a','a')",
            [],
        )
        .unwrap();
    connection
        .execute(
            "INSERT INTO tutorial_state_associations(\n                tutorial_id,authority_status,proof_method,first_seen,last_seen\n             ) VALUES (100,'unmatched_source_state','test','a','a')",
            [],
        )
        .unwrap();
    drop(connection);

    let repository = ArchiveRepository::open_read_only(&path).unwrap();
    assert_eq!(repository.list_classes(false).unwrap().len(), 1);
    assert_eq!(
        repository.list_students_for_class(20, false).unwrap().len(),
        1
    );
    let tutorials = repository.list_tutorials_for_student(10, false).unwrap();
    assert_eq!(tutorials.len(), 1);
    assert!(!tutorials[0].revision_available);
    assert!(matches!(
        repository.revision_source(100).unwrap(),
        ArchiveRevisionAvailability::Blocked { .. }
    ));
    drop(repository);
    fs::remove_file(path).ok();
}

#[test]
fn public_repository_rejects_non_v2_database() {
    let path = temp_path("wrong-version");
    let connection = Connection::open(&path).unwrap();
    connection.execute_batch("PRAGMA user_version=1;").unwrap();
    drop(connection);
    assert!(ArchiveRepository::open_read_only(&path).is_err());
    fs::remove_file(path).ok();
}
