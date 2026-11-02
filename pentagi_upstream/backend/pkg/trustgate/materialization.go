package trustgate

// An exact signed menu match selects a NEW immutable execution template. It
// never promotes the proposal's bytes or lineage to trusted. Raw proposals stay
// untrusted in the audit; only materialized fields reach an executable handler.
import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"net/url"
	"regexp"
	"strings"
	"time"
)

var quotedCurl = regexp.MustCompile(`^curl -q -sS? --max-time 5 '([^'\r\n]+)'$`)
var plainCurl = regexp.MustCompile(`^curl -q -sS? --max-time 5 (http://[A-Za-z0-9.:-]+/[A-Za-z0-9/_-]*)$`)
var boundedNmap = regexp.MustCompile(`^nmap (-sV )?-p 8888 (127\.0\.0\.1|host\.docker\.internal)$`)
var rawURL = regexp.MustCompile(`https?://[^\s'";]+`)
var scriptMarker = regexp.MustCompile(`^<script>/\*KAYAN_[0-9a-f]{16}\*/</script>$`)
var echoMarker = regexp.MustCompile(`^127\.0\.0\.1 & echo KAYAN_[0-9a-f]{16}$`)

func validEndpoint(raw string) bool {
	u, err := url.Parse(raw)
	if err != nil || strings.ContainsAny(raw, "'\r\n") || u.Scheme != "http" || u.User != nil || u.Port() != "8888" || u.Fragment != "" ||
		(u.Hostname() != "127.0.0.1" && u.Hostname() != "host.docker.internal") {
		return false
	}
	query, err := url.ParseQuery(u.RawQuery)
	if err != nil {
		return false
	}
	switch u.Path {
	case "/", "/api/products":
		return len(query) == 0
	case "/search":
		return len(query) == 1 && len(query["q"]) == 1 && scriptMarker.MatchString(query.Get("q"))
	case "/ping":
		return len(query) == 1 && len(query["host"]) == 1 && echoMarker.MatchString(query.Get("host"))
	case "/file":
		return len(query) == 1 && len(query["path"]) == 1 && query.Get("path") == "../kayan-trustgate/lab/fixtures/verification_marker.txt"
	}
	return false
}
func commandOperation(input, role string) (action, technique, target, endpoint, effective string, ok bool) {
	match := quotedCurl.FindStringSubmatch(input)
	if len(match) == 0 {
		match = plainCurl.FindStringSubmatch(input)
	}
	if len(match) > 1 {
		endpoint = match[1]
		u, err := url.Parse(endpoint)
		if err != nil {
			return
		}
		target = u.Hostname()
		if !validEndpoint(endpoint) {
			return
		}
		switch role {
		case "recon_agent":
			if u.Path == "/" || u.Path == "/api/products" {
				action, technique = "http_probe", "recon"
			}
		case "network_agent":
			if u.Path == "/" {
				action, technique = "service_scan", "network"
			}
		case "webapp_agent":
			technique = "web-app"
			switch u.Path {
			case "/search":
				action = "xss_test"
			case "/ping":
				action = "command_injection_test"
			case "/file":
				action = "directory_traversal"
			}
		}
		if action == "" {
			return
		}
		// Disable curlrc, proxies and redirects; URL is one literal shell argument.
		effective = "curl -q --noproxy '*' -s --max-time 5 '" + endpoint + "'"
		ok = true
		return
	}
	if match := boundedNmap.FindStringSubmatch(input); len(match) > 2 {
		target = match[2]
		endpoint = "http://" + target + ":8888/"
		if role != "recon_agent" && role != "network_agent" {
			return
		}
		action = "port_scan"
		if match[1] != "" {
			action = "service_scan"
		}
		technique = "network"
		if role == "recon_agent" {
			technique = "recon"
		}
		effective = input
		ok = true
	}
	return
}
func workflowAction(name string) string {
	switch name {
	case "done":
		return "complete_task"
	case "subtask_list":
		return "plan_tasks"
	case "pentester", "search", "advice", "coder", "memorist", "maintenance":
		return "delegate_task"
	case "report_result", "hack_result", "search_result", "code_result", "enricher_result", "memorist_result":
		return "record_result"
	}
	return ""
}
func (s *Session) materialize(agentType, name string, raw json.RawMessage) (AuthorizeRequest, json.RawMessage, error) {
	if s == nil {
		return AuthorizeRequest{}, nil, errors.New("TrustGate session missing; tool execution refused")
	}
	expiry, _ := time.Parse(time.RFC3339, s.binding.ExpiresAt)
	if !time.Now().Before(expiry) {
		return AuthorizeRequest{}, nil, errors.New("TrustGate execution binding expired")
	}
	agent, exists := s.binding.Agents[agentType]
	if !exists {
		return AuthorizeRequest{}, nil, fmt.Errorf("upstream agent %q is not enrolled in signed execution binding", agentType)
	}
	proposed := map[string]any{}
	if err := json.Unmarshal(raw, &proposed); err != nil {
		return AuthorizeRequest{}, nil, fmt.Errorf("invalid tool argument object: %w", err)
	}
	s.state.Lock()
	sources := append([]string{}, s.state.Sources...)
	s.state.Unlock()
	scoped, _ := url.Parse(s.binding.AllowedEndpoints[0])
	base := AuthorizeRequest{EngagementID: s.binding.EngagementID, AgentID: agent.AgentID, AgentRole: agent.Role,
		ToolName: "unmapped:" + name, Technique: "unmapped", Target: "unresolved",
		ToolArgs: map[string]any{"_upstream_tool": name, "_upstream_agent_type": agentType,
			"_model_proposal": proposed, "_model_proposal_provenance": "untrusted",
			"_untrusted_source_ids": sources}, Provenance: map[string]string{"target": "untrusted", "execution_args": "untrusted"}}
	if operation := workflowAction(name); operation != "" {
		base.ToolName, base.Technique, base.Target = operation, "workflow", scoped.Hostname()
		base.Provenance = map[string]string{"target": "trusted", "body": "untrusted"}
		base.ToolArgs["_governance_source"] = "non-executing workflow metadata; body remains untrusted"
		return base, raw, nil
	}
	input, _ := proposed["input"].(string)
	if value, ok := proposed["target"].(string); ok {
		base.Target = value
	}
	if value, ok := proposed["url"].(string); ok {
		if u, e := url.Parse(value); e == nil && u.Hostname() != "" {
			base.Target = u.Hostname()
		}
	}
	if value := rawURL.FindString(input); value != "" {
		if u, e := url.Parse(value); e == nil && u.Hostname() != "" {
			base.Target = u.Hostname()
		}
	}
	if name != "terminal" {
		return base, nil, nil
	}
	cwd, cwdOK := proposed["cwd"].(string)
	detach, detachOK := proposed["detach"].(bool)
	timeout, timeoutOK := proposed["timeout"].(float64)
	if !cwdOK || cwd != "/" || !detachOK || detach || !timeoutOK || timeout != 5 {
		return base, nil, nil
	}
	// Retrieve bytes from the signed operator menu, not from the model proposal.
	approved := ""
	for _, command := range s.binding.ApprovedCommands {
		if command == input {
			approved = command
			break
		}
	}
	if approved == "" {
		return base, nil, nil
	}
	action, technique, target, endpoint, effective, ok := commandOperation(approved, agent.Role)
	if !ok || !contains(s.binding.AllowedEndpoints, endpoint) {
		return base, nil, nil
	}
	digest := sha256.Sum256([]byte(agent.Role + ":" + approved))
	intentID := hex.EncodeToString(digest[:])
	s.state.Lock()
	alreadyUsed := s.state.Used[intentID]
	s.state.Unlock()
	if alreadyUsed {
		base.ToolName = "unmapped:already-dispatched-intent"
		base.ToolArgs["_local_refusal"] = "Signed intent was already dispatched"
		return base, nil, nil
	}
	for _, source := range sources {
		if strings.HasPrefix(source, "resumed-flow:") {
			base.ToolArgs["_local_refusal"] = "Resumed flow has unknown dispatch history; fresh signed authorization required"
			return base, nil, nil
		}
	}
	args := map[string]any{"input": effective, "cwd": "/", "detach": false, "timeout": 5, "message": "Executing signed operator-approved " + action}
	for key, value := range args {
		base.ToolArgs[key] = value
	}
	base.ToolArgs["_operator_intent_id"] = intentID
	base.ToolArgs["_governance_source"] = "independently materialized signed operator template; proposal bytes are not execution arguments"
	base.ToolName, base.Technique, base.Target = action, technique, target
	base.Provenance = map[string]string{"target": "trusted", "execution_args": "trusted"}
	actual, _ := json.Marshal(args)
	return base, actual, nil
}
