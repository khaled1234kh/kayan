package tools

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
	"testing"
	"time"

	"pentagi/pkg/database"
	"pentagi/pkg/trustgate"
)

func TestGovernanceExternalRegistryCannotShadowMetadataHandlers(t *testing.T) {
	functions := &Functions{Function: []ExternalFunction{{}}}
	if functions.ValidateGovernedRegistry() == nil {
		t.Fatal("external registry accepted")
	}
	if _, err := NewFlowToolsExecutor(nil, nil, nil, functions, 1, 1); err == nil {
		t.Fatal("persisted external registry accepted before executor construction")
	}
	if err := (*Functions)(nil).ValidateGovernedRegistry(); err != nil {
		t.Fatal(err)
	}
}

func TestGovernanceExecutorRefusesMissingActualAgentContext(t *testing.T) {
	calls := 0
	executor := &customExecutor{handlers: map[string]ExecutorHandler{"terminal": func(context.Context, string, json.RawMessage) (string, error) {
		calls++
		return "should not execute", nil
	}}}
	if _, err := executor.Execute(t.Context(), 1, "call", "terminal", "terminal", "", json.RawMessage(`{}`)); err == nil || calls != 0 {
		t.Fatal("missing context dispatched a handler")
	}
	ctx := PutAgentContext(t.Context(), database.MsgchainTypePrimaryAgent)
	if _, err := executor.Execute(ctx, 1, "call", "terminal", "terminal", "", json.RawMessage(`{}`)); err == nil || calls != 0 {
		t.Fatal("missing signed session dispatched a handler")
	}
}

func TestGovernanceExecutorDispatchesApprovedHandlerOnceThenPropagatesTaint(t *testing.T) {
	executorObserveLangfuse(t)
	key := []byte("unit-executor-governance-key-32-characters")
	keyPath := filepath.Join(t.TempDir(), "key")
	if err := os.WriteFile(keyPath, key, 0600); err != nil {
		t.Fatal(err)
	}
	t.Setenv("TRUSTGATE_BRIDGE_KEY_FILE", keyPath)
	observed := []trustgate.AuthorizeRequest{}
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		var request trustgate.AuthorizeRequest
		json.NewDecoder(r.Body).Decode(&request)
		observed = append(observed, request)
		decision := "ALLOW"
		if request.Provenance["execution_args"] == "untrusted" {
			decision = "DENY"
		}
		json.NewEncoder(w).Encode(trustgate.AuthorizeResponse{Decision: decision, Reason: "controlled gate", AuditEntryID: "unit-audit"})
	}))
	defer server.Close()
	t.Setenv("TRUSTGATE_URL", server.URL)
	command := "curl -q -s --max-time 5 http://127.0.0.1:8888/"
	binding := trustgate.ExecutionBinding{Version: 1, EngagementID: "real-request-engagement-uuid", OperatorUserID: 7,
		ExpiresAt:        time.Now().Add(time.Hour).UTC().Format(time.RFC3339),
		Agents:           map[string]trustgate.AgentBinding{"primary_agent": {AgentID: "actual-recon-identity", Role: "recon_agent"}},
		AllowedEndpoints: []string{"http://127.0.0.1:8888/"}, ApprovedCommands: []string{command}}
	raw, _ := json.Marshal(binding)
	mac := hmac.New(sha256.New, key)
	mac.Write([]byte("kayan-pentagi-governance-v1:"))
	mac.Write(raw)
	token := base64.RawURLEncoding.EncodeToString(raw) + "." + hex.EncodeToString(mac.Sum(nil))
	session, err := trustgate.NewSession(token, 7, false)
	if err != nil {
		t.Fatal(err)
	}
	calls := 0
	executor := &customExecutor{flowID: 999, governance: session, mlp: &executorMsgLog{}, tclp: &executorToolCallLog{}, replacer: identityReplacer{},
		handlers: map[string]ExecutorHandler{"terminal": func(context.Context, string, json.RawMessage) (string, error) {
			calls++
			return "target-environment output", nil
		}}}
	args, _ := json.Marshal(map[string]any{"input": command, "cwd": "/", "detach": false, "timeout": 5, "message": ""})
	ctx := PutAgentContext(t.Context(), database.MsgchainTypePrimaryAgent)
	if _, err := executor.Execute(ctx, 1, "target-call", "terminal", "terminal", "", args); err != nil {
		t.Fatal(err)
	}
	if calls != 1 {
		t.Fatal("approved handler did not execute exactly once")
	}
	if _, err := executor.Execute(ctx, 1, "derived-call", "terminal", "terminal", "", args); err == nil || calls != 1 {
		t.Fatal("tainted continuation dispatched a handler")
	}
	if len(observed) != 3 || observed[1].EngagementID == "999" || observed[1].AgentID != "actual-recon-identity/flow/999" || observed[1].Technique != "recon" {
		t.Fatalf("actual execution metadata not used: %+v", observed)
	}
	if observed[2].Provenance["execution_args"] != "untrusted" {
		t.Fatal("target provenance was not propagated")
	}
}
