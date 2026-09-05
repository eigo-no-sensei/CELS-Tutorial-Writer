//! N1 authenticated, read-only GEL acquisition session.
//!
//! This module owns the HTTP client/cookie jar and exposes only fixed read
//! operations after the two established Learn2 login-handshake POSTs. It has
//! no generic request API and no tutorial mutation transport.

use crate::gel_fields;
use crate::models::ApiTutorial;
use anyhow::{bail, Context, Result};
use reqwest::blocking::{Client, Response};
use reqwest::header::{HeaderMap, HeaderValue, ACCEPT, CONTENT_TYPE, ORIGIN, REFERER, USER_AGENT};
use reqwest::{redirect::Policy, StatusCode};
use serde_json::Value;
use std::thread;
use std::time::Duration;

const API_BASE: &str = "https://api2.guidedelearning.net";
const LEARN2_BASE: &str = "https://learn2.guidedelearning.net";
const LOGIN_PATH: &str = "/user/login?destination=login_redirect";
const LOGIN_REFERER_PATH: &str = "/corelogin/";
const LEARN2_VERIFY_PATH: &str = "/administration/students";
const DEFAULT_DELAY: Duration = Duration::from_millis(300);
const REQUEST_TIMEOUT: Duration = Duration::from_secs(20);
const HTML_ACCEPT: &str = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8";

/// Authenticated GEL read-only session.
///
/// The cookie store lives inside the private `reqwest::Client`. User credentials
/// are accepted only by [`GelSession::login`] and are never stored in this
/// structure.
pub struct GelSession {
    client: Client,
    api_base: String,
    learn2_base: String,
    delay: Duration,
    authenticated: bool,
    request_count: u64,
}

impl GelSession {
    /// Build a production GEL session with the canonical 300 ms request delay.
    pub fn new() -> Result<Self> {
        Self::with_delay(DEFAULT_DELAY)
    }

    /// Build a production GEL session with an explicit request delay.
    pub fn with_delay(delay: Duration) -> Result<Self> {
        Self::build(API_BASE, LEARN2_BASE, delay)
    }

    fn build(api_base: &str, learn2_base: &str, delay: Duration) -> Result<Self> {
        Ok(Self {
            client: build_http_client()?,
            api_base: api_base.trim_end_matches('/').to_string(),
            learn2_base: learn2_base.trim_end_matches('/').to_string(),
            delay,
            authenticated: false,
            request_count: 0,
        })
    }

    /// True only after both api2 and Learn2 authenticated-session checks pass.
    pub(crate) fn client(&self) -> &reqwest::blocking::Client {
        &self.client
    }

    pub fn is_authenticated(&self) -> bool {
        self.authenticated
    }

    /// Number of HTTP requests made by this session, including login checks.
    pub fn request_count(&self) -> u64 {
        self.request_count
    }

    /// Establish the GEL session without retaining the supplied credentials.
    ///
    /// N1 permits exactly two HTTP POSTs, both to the canonical Learn2 login
    /// endpoint. No POST capability is exposed after authentication.
    pub fn login(&mut self, username: &str, password: &str) -> Result<()> {
        self.authenticated = false;
        self.client = build_http_client()?;
        let form = [
            ("edit[name]", username),
            ("edit[pass]", password),
            ("edit[smsCode]", ""),
            ("edit[form_id]", "user_login"),
            ("edit[class_access_code]", ""),
        ];

        self.throttle();
        let first = self
            .client
            .post(self.learn2_url(LOGIN_PATH))
            .header(CONTENT_TYPE, "application/x-www-form-urlencoded")
            .header("X-Requested-With", "XMLHttpRequest")
            .header(REFERER, self.learn2_url(LOGIN_REFERER_PATH))
            .form(&form)
            .send()
            .context("send GEL login handshake step 1")?;
        if !first.status().is_success() {
            bail!(
                "GEL login handshake step 1 failed with HTTP {}",
                first.status().as_u16()
            );
        }
        let first_json: Value = first
            .json()
            .context("decode GEL login handshake response")?;
        if first_json.get("status").and_then(Value::as_str) != Some("authNotNeeded") {
            bail!("GEL authentication rejected");
        }

        self.throttle();
        let second = self
            .client
            .post(self.learn2_url(LOGIN_PATH))
            .header(CONTENT_TYPE, "application/x-www-form-urlencoded")
            .header(REFERER, self.learn2_url(LOGIN_REFERER_PATH))
            .form(&form)
            .send()
            .context("send GEL login handshake step 2")?;
        if !second.status().is_success() {
            bail!(
                "GEL login handshake step 2 failed with HTTP {}",
                second.status().as_u16()
            );
        }

        self.throttle();
        let api_check = self
            .client
            .get(self.api_url("/staff/classes"))
            .query(&[("open", "true")])
            .send()
            .context("verify GEL api2 session")?;
        if api_check.status() != StatusCode::OK {
            bail!(
                "GEL api2 session verification failed with HTTP {}",
                api_check.status().as_u16()
            );
        }

        self.throttle();
        let learn2_check = self
            .client
            .get(self.learn2_url(LEARN2_VERIFY_PATH))
            .header(ACCEPT, HTML_ACCEPT)
            .header(REFERER, self.learn2_url(LEARN2_VERIFY_PATH))
            .send()
            .context("verify GEL Learn2 session")?;
        let status = learn2_check.status();
        let final_url = learn2_check.url().as_str().to_ascii_lowercase();
        let body = learn2_check
            .text()
            .context("read GEL Learn2 verification page")?;
        if !status.is_success() {
            bail!(
                "GEL Learn2 session verification failed with HTTP {}",
                status.as_u16()
            );
        }
        if is_login_page(&final_url, &body) || !is_authenticated_learn2_page(&final_url, &body) {
            bail!("GEL Learn2 session verification returned an unauthenticated or unexpected page");
        }

        self.authenticated = true;
        Ok(())
    }

    /// Read currently open GEL classes.
    pub fn get_classes(&mut self) -> Result<Value> {
        self.api_get_json("/staff/classes", &[("open", "true")])
    }

    /// Read students for one class, stripping email-like fields before return.
    pub fn get_students(&mut self, class_id: i64) -> Result<Value> {
        require_positive("class_id", class_id)?;
        let mut value = self.api_get_json(&format!("/staff/classes/{class_id}/students"), &[])?;
        strip_student_sensitive_fields(&mut value);
        Ok(value)
    }

    /// Read one student profile, stripping email-like fields before return.
    pub fn get_student_profile(&mut self, student_uid: i64) -> Result<Value> {
        require_positive("student_uid", student_uid)?;
        let mut value = self.api_get_json(&format!("/staff/students/{student_uid}"), &[])?;
        strip_student_sensitive_fields(&mut value);
        Ok(value)
    }

    /// Read the raw tutorial-list JSON for one student.
    pub fn get_tutorial_list_json(&mut self, student_uid: i64) -> Result<Value> {
        require_positive("student_uid", student_uid)?;
        self.api_get_json(&format!("/staff/students/{student_uid}/tutorials"), &[])
    }

    /// Read canonical tutorial-list identities as typed id/timestamp pairs.
    pub fn get_tutorial_list(&mut self, student_uid: i64) -> Result<Vec<ApiTutorial>> {
        let value = self.get_tutorial_list_json(student_uid)?;
        let rows = value
            .as_array()
            .context("GEL tutorial-list response must be a JSON array")?;
        rows.iter().map(api_tutorial_from_json).collect()
    }

    /// Read the Learn2 tutorial summary HTML.
    pub fn get_tutorial_summary_html(&mut self, student_uid: i64) -> Result<String> {
        require_positive("student_uid", student_uid)?;
        self.learn2_get_html(&format!("/study/tutorials/summary/{student_uid}"))
    }

    /// Read a historical tutorial print page by student/timestamp.
    pub fn get_tutorial_print_html(
        &mut self,
        student_uid: i64,
        tutorial_ts: i64,
    ) -> Result<String> {
        require_positive("student_uid", student_uid)?;
        require_positive("tutorial_ts", tutorial_ts)?;
        self.learn2_get_html(&format!(
            "/study/tutorials/print/{student_uid}/{tutorial_ts}"
        ))
    }

    /// Read a current GEL New-tutorial source form by student/type.
    ///
    /// GEL represents New-form acquisition on the `/add/` route with a fixed
    /// zero locator segment. This is GET-only source acquisition; it grants no
    /// tutorial creation capability.
    pub fn get_new_tutorial_form_html(
        &mut self,
        student_uid: i64,
        ttype_raw: &str,
    ) -> Result<String> {
        require_positive("student_uid", student_uid)?;
        require_ttype(ttype_raw)?;
        self.learn2_get_html(&format!("/study/tutorials/add/{student_uid}/0/{ttype_raw}"))
    }

    /// Read a historical tutorial edit form by student/timestamp/type.
    ///
    /// Despite the GEL route containing `/add/`, this operation is HTTP GET
    /// only and grants no submission capability.
    pub fn get_tutorial_edit_html(
        &mut self,
        student_uid: i64,
        tutorial_ts: i64,
        ttype_raw: &str,
    ) -> Result<String> {
        require_positive("student_uid", student_uid)?;
        require_positive("tutorial_ts", tutorial_ts)?;
        require_ttype(ttype_raw)?;
        self.learn2_get_html(&format!(
            "/study/tutorials/add/{student_uid}/{tutorial_ts}/{ttype_raw}"
        ))
    }

    fn api_get_json(&mut self, path: &str, query: &[(&str, &str)]) -> Result<Value> {
        self.ensure_authenticated()?;
        self.throttle();
        let response = self
            .client
            .get(self.api_url(path))
            .query(query)
            .send()
            .context("send GEL api2 read request")?;
        self.handle_authenticated_status(response.status())?;
        response.json().context("decode GEL api2 JSON response")
    }

    fn learn2_get_html(&mut self, path: &str) -> Result<String> {
        self.ensure_authenticated()?;
        self.throttle();
        let response = self
            .client
            .get(self.learn2_url(path))
            .header(ACCEPT, HTML_ACCEPT)
            .header(REFERER, self.learn2_url(LEARN2_VERIFY_PATH))
            .send()
            .context("send GEL Learn2 read request")?;
        self.read_authenticated_html(response)
    }

    fn read_authenticated_html(&mut self, response: Response) -> Result<String> {
        self.handle_authenticated_status(response.status())?;
        let final_url = response.url().as_str().to_ascii_lowercase();
        let body = response.text().context("read GEL Learn2 HTML response")?;
        if is_login_page(&final_url, &body) {
            self.authenticated = false;
            bail!("GEL session expired");
        }
        Ok(body)
    }

    fn handle_authenticated_status(&mut self, status: StatusCode) -> Result<()> {
        if status == StatusCode::UNAUTHORIZED || status == StatusCode::FORBIDDEN {
            self.authenticated = false;
            bail!("GEL session expired");
        }
        if !status.is_success() {
            bail!("GEL read request failed with HTTP {}", status.as_u16());
        }
        Ok(())
    }

    fn ensure_authenticated(&self) -> Result<()> {
        if !self.authenticated {
            bail!("GEL session is not authenticated");
        }
        Ok(())
    }

    fn throttle(&mut self) {
        if !self.delay.is_zero() {
            thread::sleep(self.delay);
        }
        self.request_count += 1;
    }

    fn api_url(&self, path: &str) -> String {
        format!("{}{}", self.api_base, path)
    }

    fn learn2_url(&self, path: &str) -> String {
        format!("{}{}", self.learn2_base, path)
    }

    #[cfg(test)]
    fn for_test(base: &str) -> Result<Self> {
        Self::build(base, base, Duration::ZERO)
    }
}

fn build_http_client() -> Result<Client> {
    let mut headers = HeaderMap::new();
    headers.insert(
        USER_AGENT,
        HeaderValue::from_static("GEL-Rust-ReadOnly-Session/1.0"),
    );
    headers.insert(
        ACCEPT,
        HeaderValue::from_static("application/json, text/plain, */*"),
    );
    headers.insert(
        ORIGIN,
        HeaderValue::from_static("https://staff2.guidedelearning.net"),
    );
    headers.insert(
        REFERER,
        HeaderValue::from_static("https://staff2.guidedelearning.net/"),
    );

    Client::builder()
        .default_headers(headers)
        .cookie_store(true)
        .redirect(Policy::limited(10))
        .timeout(REQUEST_TIMEOUT)
        .build()
        .context("build GEL read-only HTTP client")
}

fn require_positive(label: &str, value: i64) -> Result<()> {
    if value <= 0 {
        bail!("{label} must be positive");
    }
    Ok(())
}

fn require_ttype(ttype_raw: &str) -> Result<()> {
    let allowed = [
        gel_fields::TTYPE_STANDARD,
        gel_fields::TTYPE_FINAL,
        gel_fields::TTYPE_INITIAL,
    ];
    if !allowed.contains(&ttype_raw) {
        bail!("invalid GEL tutorial type code");
    }
    Ok(())
}

fn api_tutorial_from_json(value: &Value) -> Result<ApiTutorial> {
    let object = value
        .as_object()
        .context("GEL tutorial-list row must be a JSON object")?;
    let id = flexible_i64(object.get("id")).context("GEL tutorial-list row missing valid id")?;
    let timestamp = flexible_i64(object.get("timestamp"))
        .context("GEL tutorial-list row missing valid timestamp")?;
    require_positive("tutorial_id", id)?;
    require_positive("tutorial timestamp", timestamp)?;
    Ok(ApiTutorial { id, timestamp })
}

fn flexible_i64(value: Option<&Value>) -> Option<i64> {
    value.and_then(|value| {
        value
            .as_i64()
            .or_else(|| value.as_u64().and_then(|n| i64::try_from(n).ok()))
            .or_else(|| value.as_str().and_then(|s| s.parse::<i64>().ok()))
    })
}

fn strip_student_sensitive_fields(value: &mut Value) {
    match value {
        Value::Object(object) => {
            object.retain(|key, child| {
                let blocked = matches!(
                    key.to_ascii_lowercase().as_str(),
                    "email" | "mail" | "email_address" | "emailaddress"
                );
                if !blocked {
                    strip_student_sensitive_fields(child);
                }
                !blocked
            });
        }
        Value::Array(items) => {
            for item in items {
                strip_student_sensitive_fields(item);
            }
        }
        _ => {}
    }
}

fn is_login_page(final_url: &str, body: &str) -> bool {
    let body = body.to_ascii_lowercase();
    final_url.contains("/user/login")
        || final_url.contains("corelogin")
        || body.contains("user-login")
        || body.contains("name=\"form_build_id\"")
        || body.contains("name=\"form_token\"")
        || body.contains("name=\"edit[pass]\"")
        || body.contains("name=\"edit[name]\"")
}

fn is_authenticated_learn2_page(final_url: &str, body: &str) -> bool {
    let body = body.to_ascii_lowercase();
    final_url.contains("/administration/students")
        || final_url.contains("/administration/students/search")
        || body.contains("id=\"student-management\"")
        || body.contains("id=\"csvform\"")
        || body.contains("id=\"studeamanagementform\"")
        || body.contains("download list")
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::{Read, Write};
    use std::net::{TcpListener, TcpStream};
    use std::sync::{Arc, Mutex};
    use std::thread;

    #[derive(Debug, Clone)]
    struct SeenRequest {
        method: String,
        target: String,
        body: String,
    }

    fn read_request(stream: &mut TcpStream) -> SeenRequest {
        let mut bytes = Vec::new();
        let mut buf = [0_u8; 4096];
        loop {
            let read = stream.read(&mut buf).unwrap();
            if read == 0 {
                break;
            }
            bytes.extend_from_slice(&buf[..read]);
            if let Some(header_end) = bytes.windows(4).position(|w| w == b"\r\n\r\n") {
                let headers = String::from_utf8_lossy(&bytes[..header_end + 4]);
                let content_length = headers
                    .lines()
                    .find_map(|line| {
                        line.strip_prefix("Content-Length: ")
                            .or_else(|| line.strip_prefix("content-length: "))
                    })
                    .and_then(|value| value.trim().parse::<usize>().ok())
                    .unwrap_or(0);
                let total = header_end + 4 + content_length;
                if bytes.len() >= total {
                    break;
                }
            }
        }
        let text = String::from_utf8(bytes).unwrap();
        let (head, body) = text.split_once("\r\n\r\n").unwrap_or((&text, ""));
        let first = head.lines().next().unwrap();
        let mut parts = first.split_whitespace();
        SeenRequest {
            method: parts.next().unwrap().to_string(),
            target: parts.next().unwrap().to_string(),
            body: body.to_string(),
        }
    }

    fn response_for(index: usize) -> (&'static str, &'static str, &'static str) {
        match index {
            0 => (
                "200 OK",
                "application/json",
                r#"{"status":"authNotNeeded"}"#,
            ),
            1 => ("200 OK", "text/html", "ok"),
            2 => ("200 OK", "application/json", "[]"),
            3 => (
                "200 OK",
                "text/html",
                r#"<html><div id="student-management">authenticated</div></html>"#,
            ),
            4 => (
                "200 OK",
                "application/json",
                r#"[{"id":"1001","timestamp":1785931249}]"#,
            ),
            5 => ("200 OK", "text/html", "<html>summary</html>"),
            6 => ("200 OK", "text/html", "<html>print</html>"),
            7 => ("200 OK", "text/html", "<html>edit</html>"),
            8 => ("200 OK", "text/html", "<html>new</html>"),
            _ => panic!("unexpected request index {index}"),
        }
    }

    fn spawn_server(
        expected_requests: usize,
    ) -> (String, Arc<Mutex<Vec<SeenRequest>>>, thread::JoinHandle<()>) {
        let listener = TcpListener::bind("127.0.0.1:0").unwrap();
        let address = listener.local_addr().unwrap();
        let seen = Arc::new(Mutex::new(Vec::new()));
        let seen_thread = Arc::clone(&seen);
        let handle = thread::spawn(move || {
            for (index, incoming) in listener.incoming().take(expected_requests).enumerate() {
                let mut stream = incoming.unwrap();
                let request = read_request(&mut stream);
                seen_thread.lock().unwrap().push(request);
                let (status, content_type, body) = response_for(index);
                let cookie = if index == 0 {
                    "Set-Cookie: gel_session=test; Path=/\r\n"
                } else {
                    ""
                };
                let response = format!(
                    "HTTP/1.1 {}\r\nContent-Type: {}\r\n{}Content-Length: {}\r\nConnection: close\r\n\r\n{}",
                    status,
                    content_type,
                    cookie,
                    body.len(),
                    body
                );
                stream.write_all(response.as_bytes()).unwrap();
            }
        });
        (format!("http://{address}"), seen, handle)
    }

    #[test]
    fn login_posts_only_to_login_then_read_surface_uses_get() {
        let (base, seen, server) = spawn_server(9);
        let mut session = GelSession::for_test(&base).unwrap();
        session.login("teacher", "secret-password").unwrap();
        let list = session.get_tutorial_list(42).unwrap();
        assert_eq!(
            list,
            vec![ApiTutorial {
                id: 1001,
                timestamp: 1_785_931_249,
            }]
        );
        assert_eq!(
            session.get_tutorial_summary_html(42).unwrap(),
            "<html>summary</html>"
        );
        assert_eq!(
            session.get_tutorial_print_html(42, 1_785_931_249).unwrap(),
            "<html>print</html>"
        );
        assert_eq!(
            session
                .get_tutorial_edit_html(42, 1_785_931_249, gel_fields::TTYPE_FINAL)
                .unwrap(),
            "<html>edit</html>"
        );
        assert_eq!(
            session
                .get_new_tutorial_form_html(42, gel_fields::TTYPE_FINAL)
                .unwrap(),
            "<html>new</html>"
        );
        server.join().unwrap();

        let requests = seen.lock().unwrap();
        assert_eq!(requests.len(), 9);
        assert_eq!(
            requests
                .iter()
                .filter(|request| request.method == "POST")
                .count(),
            2
        );
        for request in requests.iter().filter(|request| request.method == "POST") {
            assert!(request.target.starts_with(LOGIN_PATH));
            assert!(request.body.contains("edit%5Bpass%5D=secret-password"));
        }
        for request in requests.iter().skip(2) {
            assert_eq!(request.method, "GET");
            assert!(!request.body.contains("secret-password"));
        }
        assert_eq!(
            requests.last().unwrap().target,
            "/study/tutorials/add/42/0/1"
        );
        assert!(session.is_authenticated());
        assert_eq!(session.request_count(), 9);
    }

    #[test]
    fn student_privacy_filter_removes_email_like_fields_recursively() {
        let mut value = serde_json::json!({
            "uid": 42,
            "email": "student@example.invalid",
            "nested": {
                "mail": "nested@example.invalid",
                "name": "Student"
            },
            "items": [
                {"email_address": "a@example.invalid", "ok": 1},
                {"emailaddress": "b@example.invalid", "ok": 2}
            ]
        });
        strip_student_sensitive_fields(&mut value);
        let serialized = value.to_string();
        assert!(!serialized.contains("example.invalid"));
        assert!(!serialized.contains("email"));
        assert_eq!(value["nested"]["name"], "Student");
        assert_eq!(value["items"][0]["ok"], 1);
    }

    #[test]
    fn tutorial_identity_projection_fails_closed_on_missing_or_nonpositive_values() {
        assert!(api_tutorial_from_json(&serde_json::json!({"id": 1})).is_err());
        assert!(api_tutorial_from_json(&serde_json::json!({"id": 0, "timestamp": 2})).is_err());
        assert!(api_tutorial_from_json(&serde_json::json!({"id": 1, "timestamp": "x"})).is_err());
    }

    #[test]
    fn authenticated_status_expiry_clears_session_capability() {
        let mut session = GelSession::for_test("http://127.0.0.1:9").unwrap();
        session.authenticated = true;
        assert!(session
            .handle_authenticated_status(StatusCode::UNAUTHORIZED)
            .is_err());
        assert!(!session.is_authenticated());
    }

    #[test]
    fn login_page_detection_invalidates_even_when_http_status_would_be_success() {
        assert!(is_login_page(
            "https://learn2.guidedelearning.net/user/login",
            r#"<input name="edit[pass]">"#
        ));
    }
}
