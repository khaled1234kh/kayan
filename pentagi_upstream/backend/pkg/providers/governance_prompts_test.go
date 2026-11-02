package providers

import (
	"pentagi/pkg/templates"
	"strings"
	"testing"
)

type constraintFixture struct{}

func (constraintFixture) GovernancePromptConstraints() string { return "SIGNED MENU cwd=/ timeout=5" }

type plainPrompterFixture struct{}

func (plainPrompterFixture) GetTemplate(templates.PromptType) (string, error) { return "original", nil }
func (plainPrompterFixture) RenderTemplate(templates.PromptType, any) (string, error) {
	return "original", nil
}
func (plainPrompterFixture) DumpTemplates() ([]byte, error) { return []byte(`{}`), nil }

func TestGovernancePromptsReachDelegatesWithoutChangingSetupParsers(t *testing.T) {
	p := withGovernancePrompts(plainPrompterFixture{}, constraintFixture{})
	for _, kind := range []templates.PromptType{templates.PromptTypePrimaryAgent, templates.PromptTypePentester,
		templates.PromptTypeGenerator, templates.PromptTypeSubtasksGenerator, templates.PromptTypeReporter} {
		got, err := p.RenderTemplate(kind, nil)
		if err != nil || !strings.HasPrefix(got, "original") || !strings.Contains(got, "SIGNED MENU") {
			t.Fatalf("%s: %q %v", kind, got, err)
		}
	}
	for _, kind := range []templates.PromptType{templates.PromptTypeLanguageChooser, templates.PromptTypeFlowDescriptor, templates.PromptTypeToolCallIDDetector} {
		got, err := p.RenderTemplate(kind, nil)
		if err != nil || got != "original" {
			t.Fatalf("setup parser contaminated: %s %q %v", kind, got, err)
		}
	}
}
