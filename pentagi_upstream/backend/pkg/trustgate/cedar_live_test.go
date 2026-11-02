package trustgate

import (
	"context"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"testing"
	"time"
)

// Opt-in, real Rust/Cedar wire check. No model or target tool executes here.
func TestCedarLiveProfile(t *testing.T) {
	if os.Getenv("TRUSTGATE_TEST_REAL") != "1" {
		t.Skip("requires running local Rust gate and private bridge-key file")
	}
	key, err := bridgeKey()
	if err != nil {
		t.Fatal(err)
	}
	base := os.Getenv("TRUSTGATE_URL")
	if base == "" {
		t.Fatal("TRUSTGATE_URL required")
	}
	eid := fmt.Sprintf("go-wire-%d", time.Now().UnixNano())
	scope := struct {
		Targets   []string `json:"targets"`
		Allowed   []string `json:"allowed_techniques"`
		Forbidden []string `json:"forbidden_actions"`
	}{[]string{"127.0.0.1"}, []string{"recon", "workflow"}, []string{}}
	window := struct {
		Start string `json:"start"`
		End   string `json:"end"`
	}{time.Now().Add(-time.Second).UTC().Format(time.RFC3339), time.Now().Add(time.Minute).UTC().Format(time.RFC3339)}
	scopeJSON, _ := json.Marshal(scope)
	windowJSON, _ := json.Marshal(window)
	mac := hmac.New(sha256.New, key)
	mac.Write([]byte(eid + ":go-wire-operator:" + string(scopeJSON) + ":" + string(windowJSON)))
	loaded, err := NewTrustGateClient(base).LoadROE(map[string]any{"engagement_id": eid, "authorized_by": "go-wire-operator", "scope": scope, "time_window": window, "signature": hex.EncodeToString(mac.Sum(nil))})
	if err != nil || loaded["status"] != "loaded" {
		t.Fatalf("ROE load: %v %v", loaded, err)
	}
	b := testBinding(t)
	b.EngagementID = eid
	raw, _ := json.Marshal(b)
	mac = hmac.New(sha256.New, key)
	mac.Write([]byte(bindingDomain))
	mac.Write(raw)
	token := base64.RawURLEncoding.EncodeToString(raw) + "." + hex.EncodeToString(mac.Sum(nil))
	session, err := NewSession(token, 7, false)
	if err != nil {
		t.Fatal(err)
	}
	args := terminalArgs(b.ApprovedCommands[0])
	allow, err := session.Authorize(context.Background(), "primary_agent", "terminal", args)
	if err != nil || allow.Decision != "ALLOW" || allow.AuditEntryID == "" {
		t.Fatalf("real Cedar expected ALLOW: %+v %v", allow, err)
	}
	session.MarkTargetInvocation("controlled-target-output")
	metadata, err := session.Authorize(context.Background(), "primary_agent", "done", json.RawMessage(`{"result":"target-derived text remains untrusted data"}`))
	if err != nil || metadata.Decision != "ALLOW" || metadata.AuditEntryID == "" {
		t.Fatalf("real Cedar expected explicit workflow metadata ALLOW: %+v %v", metadata, err)
	}
	denied, err := session.Authorize(context.Background(), "primary_agent", "terminal", args)
	if err != nil || denied.Decision != "DENY" || denied.AuditEntryID == "" {
		t.Fatalf("real Cedar expected taint DENY: %+v %v", denied, err)
	}
	t.Logf("engagement=%s approved audit=%s metadata audit=%s duplicate denial audit=%s", eid, allow.AuditEntryID, metadata.AuditEntryID, denied.AuditEntryID)
}
