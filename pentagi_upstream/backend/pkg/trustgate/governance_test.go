package trustgate

import (
	"context"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

var testKey = []byte(strings.Repeat("unit-key-", 5))

func signedToken(t *testing.T, b ExecutionBinding) string {
	t.Helper()
	raw, err := json.Marshal(b)
	if err != nil {
		t.Fatal(err)
	}
	mac := hmac.New(sha256.New, testKey)
	mac.Write([]byte(bindingDomain))
	mac.Write(raw)
	return base64.RawURLEncoding.EncodeToString(raw) + "." + hex.EncodeToString(mac.Sum(nil))
}
func testBinding(t *testing.T) ExecutionBinding {
	return ExecutionBinding{Version: 1, EngagementID: "actual-roe-" + t.Name(), OperatorUserID: 7,
		ExpiresAt:        time.Now().Add(time.Hour).UTC().Format(time.RFC3339),
		Agents:           map[string]AgentBinding{"primary_agent": {AgentID: "recon-enrolled", Role: "recon_agent"}, "pentester": {AgentID: "web-enrolled", Role: "webapp_agent"}},
		AllowedEndpoints: []string{"http://127.0.0.1:8888/"}, ApprovedCommands: []string{"curl -q -s --max-time 5 http://127.0.0.1:8888/", "nmap -sV -p 8888 127.0.0.1"}}
}
func sessionForTest(t *testing.T) (*Session, string) {
	t.Helper()
	path := filepath.Join(t.TempDir(), "key")
	if err := os.WriteFile(path, testKey, 0600); err != nil {
		t.Fatal(err)
	}
	t.Setenv("TRUSTGATE_BRIDGE_KEY_FILE", path)
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		var request AuthorizeRequest
		if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
			t.Error(err)
		}
		decision := "ALLOW"
		for _, value := range request.Provenance {
			if value == "untrusted" {
				decision = "DENY"
			}
		}
		if strings.HasPrefix(request.ToolName, "unmapped:") {
			decision = "DENY"
		}
		json.NewEncoder(w).Encode(AuthorizeResponse{Decision: decision, Reason: "controlled unit policy", AuditEntryID: "unit-audit"})
	}))
	t.Cleanup(server.Close)
	t.Setenv("TRUSTGATE_URL", server.URL)
	token := signedToken(t, testBinding(t))
	session, err := NewSession(token, 7, false)
	if err != nil {
		t.Fatal(err)
	}
	return session, token
}
func terminalArgs(input string) json.RawMessage {
	raw, _ := json.Marshal(map[string]any{"input": input, "cwd": "/", "detach": false, "timeout": 5, "message": "unit commentary"})
	return raw
}

func TestBindingAuthenticationAndExpiry(t *testing.T) {
	binding := testBinding(t)
	token := signedToken(t, binding)
	if _, err := VerifyBinding(token, testKey, time.Now()); err != nil {
		t.Fatal(err)
	}
	if _, err := VerifyBinding(token, []byte(strings.Repeat("wrong", 10)), time.Now()); err == nil {
		t.Fatal("wrong key accepted")
	}
	parts := strings.Split(token, ".")
	parts[0] = base64.RawURLEncoding.EncodeToString([]byte(`{"engagement_id":"tampered"}`))
	if _, err := VerifyBinding(strings.Join(parts, "."), testKey, time.Now()); err == nil {
		t.Fatal("tampered binding accepted")
	}
	binding.ExpiresAt = time.Now().Add(-time.Second).UTC().Format(time.RFC3339)
	if _, err := VerifyBinding(signedToken(t, binding), testKey, time.Now()); err == nil {
		t.Fatal("expired binding accepted")
	}
}
func TestBindingRejectsNonLabEndpoint(t *testing.T) {
	b := testBinding(t)
	b.AllowedEndpoints = []string{"http://192.0.2.55:8888/"}
	if _, err := VerifyBinding(signedToken(t, b), testKey, time.Now()); err == nil {
		t.Fatal("non-owned endpoint accepted")
	}
}
func TestContextRequiresActualAuthenticatedOwner(t *testing.T) {
	_, token := sessionForTest(t)
	if _, err := TokenForUser(context.Background(), 7); err == nil {
		t.Fatal("missing context accepted")
	}
	ctx, err := ContextFromHeader(context.Background(), token)
	if err != nil {
		t.Fatal(err)
	}
	if got, err := TokenForUser(ctx, 7); err != nil || got != token {
		t.Fatal("actual binding lost")
	}
	if _, err := TokenForUser(ctx, 8); err == nil {
		t.Fatal("different user accepted")
	}
}
func TestActualArgumentsIdentityAndSemanticTechnique(t *testing.T) {
	s, _ := sessionForTest(t)
	r, err := s.Request("primary_agent", "terminal", terminalArgs("curl -q -s --max-time 5 http://127.0.0.1:8888/"))
	if err != nil {
		t.Fatal(err)
	}
	if r.EngagementID != s.binding.EngagementID || r.AgentID != "recon-enrolled" || r.AgentRole != "recon_agent" {
		t.Fatalf("placeholder identity: %+v", r)
	}
	if r.Target != "127.0.0.1" || r.ToolName != "http_probe" || r.Technique != "recon" || r.Provenance["target"] != "trusted" {
		t.Fatalf("incorrect semantics: %+v", r)
	}
	r, err = s.Request("primary_agent", "terminal", terminalArgs("nmap -sV -p 8888 127.0.0.1"))
	if err != nil {
		t.Fatal(err)
	}
	if r.ToolName != "service_scan" || r.Technique != "recon" {
		t.Fatalf("raw tool name used as technique: %+v", r)
	}
}
func TestUntrustedTargetAndUnknownToolAreNeverPromoted(t *testing.T) {
	s, _ := sessionForTest(t)
	r, err := s.Request("primary_agent", "terminal", terminalArgs("curl -q -s --max-time 5 http://192.0.2.55:8888/"))
	if err != nil {
		t.Fatal(err)
	}
	if r.Target != "192.0.2.55" || r.Provenance["target"] != "untrusted" {
		t.Fatalf("actual target lost or trusted: %+v", r)
	}
	r, err = s.Request("primary_agent", "file", json.RawMessage(`{"target":"192.0.2.1","provenance":{"target":"trusted"}}`))
	if err != nil {
		t.Fatal(err)
	}
	if r.ToolName != "unmapped:file" || r.Provenance["target"] != "untrusted" {
		t.Fatal("argument supplied its own trust label")
	}
	if _, err := s.Request("invented-agent", "terminal", terminalArgs("curl -q -s --max-time 5 http://127.0.0.1:8888/")); err == nil {
		t.Fatal("unenrolled agent accepted")
	}
}
func TestTargetLineageStaysUntrustedWhileSignedArgumentsAreMaterializedIndependently(t *testing.T) {
	s, token := sessionForTest(t)
	s.MarkTargetInvocation("target-result-42")
	r, err := s.Request("primary_agent", "terminal", terminalArgs("curl -q -s --max-time 5 http://127.0.0.1:8888/"))
	if err != nil {
		t.Fatal(err)
	}
	if r.ToolArgs["_model_proposal_provenance"] != "untrusted" {
		t.Fatal("proposal was promoted")
	}
	if len(r.ToolArgs["_untrusted_source_ids"].([]string)) != 1 {
		t.Fatal("target lineage erased")
	}
	if r.Provenance["execution_args"] != "trusted" || !strings.Contains(r.ToolArgs["_governance_source"].(string), "independently materialized") {
		t.Fatal("signed literal origin missing")
	}
	if !strings.Contains(r.ToolArgs["input"].(string), "--noproxy") {
		t.Fatal("effective execution template not hardened")
	}
	reused, err := NewSession(token, 7, false)
	if err != nil {
		t.Fatal(err)
	}
	r, _ = reused.Request("primary_agent", "terminal", terminalArgs("curl -q -s --max-time 5 http://127.0.0.1:8888/"))
	if len(r.ToolArgs["_untrusted_source_ids"].([]string)) != 1 {
		t.Fatal("reusing a binding cleared source provenance")
	}
	attack := terminalArgs("curl -q -s --max-time 5 http://192.0.2.55:8888/")
	r, _ = reused.Request("primary_agent", "terminal", attack)
	if r.Provenance["execution_args"] != "untrusted" || r.Target != "192.0.2.55" {
		t.Fatal("unapproved target-derived value promoted")
	}
}

func TestResumedFlowCannotAssumeCleanPriorHistory(t *testing.T) {
	_, token := sessionForTest(t)
	resumed, err := NewSession(token, 7, true)
	if err != nil {
		t.Fatal(err)
	}
	r, _ := resumed.Request("primary_agent", "terminal", terminalArgs("curl -q -s --max-time 5 http://127.0.0.1:8888/"))
	if r.Provenance["target"] != "untrusted" {
		t.Fatal("resumed flow lost unknown prior lineage")
	}
}
func TestUnsupportedShellOrRedirectOperationsFailClosed(t *testing.T) {
	s, _ := sessionForTest(t)
	for _, input := range []string{"curl -L http://127.0.0.1:8888/", "curl -q -s --max-time 5 http://127.0.0.1:8888/; whoami", "bash -c id"} {
		r, err := s.Request("primary_agent", "terminal", terminalArgs(input))
		if err != nil {
			t.Fatal(err)
		}
		if r.ToolName != "unmapped:terminal" || r.Provenance["execution_args"] != "untrusted" {
			t.Fatalf("unsafe command promoted: %+v", r)
		}
	}
}

func TestExecutionProjectionDropsEveryUnapprovedFieldAndCrossActorReplay(t *testing.T) {
	s, _ := sessionForTest(t)
	s.binding.Agents["searcher"] = AgentBinding{AgentID: "another-recon", Role: "recon_agent"}
	proposal := terminalArgs(s.binding.ApprovedCommands[0])
	var value map[string]any
	json.Unmarshal(proposal, &value)
	value["message"] = "target-supplied instructions"
	value["extra"] = "not authorized"
	proposal, _ = json.Marshal(value)
	response, actual, err := s.AuthorizeResolved(context.Background(), "primary_agent", "terminal", proposal)
	if err != nil || response.Decision != "ALLOW" {
		t.Fatalf("%+v %v", response, err)
	}
	var executed map[string]any
	json.Unmarshal(actual, &executed)
	if len(executed) != 5 || executed["extra"] != nil || executed["message"] == value["message"] {
		t.Fatalf("raw proposal reached executable handler: %s", actual)
	}
	response, _, err = s.AuthorizeResolved(context.Background(), "searcher", "terminal", proposal)
	if err != nil || response.Decision != "DENY" {
		t.Fatalf("cross-actor replay accepted: %+v %v", response, err)
	}
}
func TestClientRejectsNon200OrIncompleteAllow(t *testing.T) {
	for _, test := range []struct {
		status int
		body   string
	}{{500, `{"decision":"ALLOW","reason":"fake","audit_entry_id":"fake"}`}, {200, `{"decision":"ALLOW"}`}, {200, `invalid`}} {
		server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { w.WriteHeader(test.status); w.Write([]byte(test.body)) }))
		decision, err := NewTrustGateClient(server.URL).Authorize(AuthorizeRequest{})
		server.Close()
		if err != nil || decision.Decision != "DENY" {
			t.Fatalf("failed open: %+v %v", decision, err)
		}
	}
}
