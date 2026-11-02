package trustgate

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"
)

// TrustGateClient is a Go HTTP client for the TrustGate policy enforcement service.
type TrustGateClient struct {
	BaseURL string
	Client  *http.Client
}

// NewTrustGateClient creates a new client pointing at the TrustGate service.
func NewTrustGateClient(baseURL string) *TrustGateClient {
	return &TrustGateClient{
		BaseURL: baseURL,
		Client:  &http.Client{Timeout: 10 * time.Second},
	}
}

// AuthorizeRequest is the request body for /authorize.
type AuthorizeRequest struct {
	EngagementID string            `json:"engagement_id"`
	AgentID      string            `json:"agent_id"`
	AgentRole    string            `json:"agent_role"`
	ToolName     string            `json:"tool_name"`
	ToolArgs     map[string]any    `json:"tool_args"`
	Target       string            `json:"target"`
	Technique    string            `json:"technique"`
	Provenance   map[string]string `json:"provenance"`
}

// AuthorizeResponse is the response from /authorize.
type AuthorizeResponse struct {
	Decision     string `json:"decision"`
	Reason       string `json:"reason"`
	PolicyID     string `json:"policy_id"`
	AuditEntryID string `json:"audit_entry_id"`
}

// Authorize checks if a tool call is authorized.
func (c *TrustGateClient) Authorize(req AuthorizeRequest) (AuthorizeResponse, error) {
	return c.AuthorizeContext(context.Background(), req)
}
func (c *TrustGateClient) AuthorizeContext(ctx context.Context, req AuthorizeRequest) (AuthorizeResponse, error) {
	body, err := json.Marshal(req)
	if err != nil {
		return AuthorizeResponse{}, fmt.Errorf("failed to marshal request: %w", err)
	}

	httpRequest, err := http.NewRequestWithContext(ctx, http.MethodPost, c.BaseURL+"/authorize", bytes.NewReader(body))
	if err != nil {
		return AuthorizeResponse{Decision: "DENY", Reason: err.Error()}, err
	}
	httpRequest.Header.Set("Content-Type", "application/json")
	resp, err := c.Client.Do(httpRequest)
	if err != nil {
		// Fail closed: if TrustGate is unreachable, deny
		return AuthorizeResponse{
			Decision: "DENY",
			Reason:   fmt.Sprintf("TrustGate unreachable: %v", err),
		}, nil
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return AuthorizeResponse{Decision: "DENY", Reason: fmt.Sprintf("TrustGate HTTP %d", resp.StatusCode)}, nil
	}

	var result AuthorizeResponse
	if err := json.NewDecoder(io.LimitReader(resp.Body, 1<<20)).Decode(&result); err != nil {
		return AuthorizeResponse{
			Decision: "DENY",
			Reason:   fmt.Sprintf("failed to decode response: %v", err),
		}, nil
	}
	if result.Decision == "ALLOW" && (result.AuditEntryID == "" || result.Reason == "") {
		return AuthorizeResponse{Decision: "DENY", Reason: "invalid ALLOW response: missing audit reference or reason"}, nil
	}
	if result.Decision != "ALLOW" {
		result.Decision = "DENY"
	}

	return result, nil
}

// LoadROE loads an ROE contract into TrustGate.
func (c *TrustGateClient) LoadROE(roe map[string]any) (map[string]any, error) {
	body, err := json.Marshal(roe)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal ROE: %w", err)
	}

	resp, err := c.Client.Post(c.BaseURL+"/roe/load", "application/json", bytes.NewReader(body))
	if err != nil {
		return nil, fmt.Errorf("failed to load ROE: %w", err)
	}
	defer resp.Body.Close()

	var result map[string]any
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return nil, fmt.Errorf("failed to decode response: %w", err)
	}

	return result, nil
}
