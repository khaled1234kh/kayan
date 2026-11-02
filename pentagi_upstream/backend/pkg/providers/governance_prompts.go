package providers

import "pentagi/pkg/templates"

// Embed preserves the original prompter and appends the independently verified
// scope to each rendered worker/task prompt. It never reads delegation text.
type governedPrompter struct {
	templates.Prompter
	constraints string
}

func withGovernancePrompts(base templates.Prompter, executor any) templates.Prompter {
	if source, ok := executor.(interface{ GovernancePromptConstraints() string }); ok {
		return &governedPrompter{base, source.GovernancePromptConstraints()}
	}
	return base
}

func (p *governedPrompter) RenderTemplate(kind templates.PromptType, params any) (string, error) {
	text, err := p.Prompter.RenderTemplate(kind, params)
	if err != nil {
		return "", err
	}
	// Setup parsers expect a language, title, or tool ID, not operational context.
	switch kind {
	case templates.PromptTypeImageChooser, templates.PromptTypeLanguageChooser,
		templates.PromptTypeFlowDescriptor, templates.PromptTypeTaskDescriptor,
		templates.PromptTypeToolCallIDCollector, templates.PromptTypeToolCallIDDetector:
		return text, nil
	}
	return text + "\n\n" + p.constraints, nil
}
