# Specification: Hooks and Moderation System

## Overview
This document specifies the requirements and design for implementing a flexible hooks and moderation system for the AMI-Orchestrator agents. The system will replace the existing guard system with a more configurable approach using YAML configurations and prompt files.

## Current System Analysis

### Existing Components
- **Guards System** (`ami/core/guards.py`): Basic pattern-based validation for bash commands
- **Policy Engine** (`ami/core/policies/engine.py`): Centralized loading of YAML-based policies
- **Bootloader Agent** (`ami/core/bootloader_agent.py`): Core agent implementation with ReAct loop
- **Configuration System** (`ami/core/config.py`): YAML-based configuration management

### Identified Flaws
1. Rigid security model limited to bash command validation
2. Hardcoded configuration with no dynamic adjustment
3. Limited feedback loop to agents
4. No support for validation at multiple pipeline points
5. No support for LLM-based validation

## Requirements

### 1. Event Interception
- **SPEC-HOOK-001**: System shall support event interception at key pipeline points:
  - User query submission
  - Agent code execution requests
  - Agent response generation

### 2. Configuration Flexibility
- **SPEC-HOOK-002**: All validation rules shall be configurable via YAML files without requiring code changes

- **SPEC-HOOK-003**: System shall support loading prompts from external TXT/MD files for LLM-based validations

### 3. Validation Capabilities
- **SPEC-HOOK-004**: System shall support pattern-based validation using regex expressions

- **SPEC-HOOK-005**: System shall support LLM-based content evaluation using configurable prompts

- **SPEC-HOOK-006**: System shall support four decision types:
  - ALLOW: Permit the action
  - DENY: Block the action
  - MODIFY: Alter the content before proceeding
  - REQUEST_FEEDBACK: Add feedback to the next LLM interaction

### 4. Integration Requirements
- **SPEC-HOOK-007**: System shall replace existing guard mechanisms in `guards.py`

- **SPEC-HOOK-008**: System shall be compatible with all supported agent providers (Claude, Qwen, Gemini)

- **SPEC-HOOK-009**: System shall maintain or enhance existing security properties

- **SPEC-HOOK-010**: System shall support feedback injection back into the agent's next interaction cycle

### 5. Refactoring Requirements
- **SPEC-HOOK-011**: Existing `guards.py` functionality shall be replaced by new system
  - Current `check_command_safety` function logic shall be reimplemented
  - Current `check_edit_safety` function logic shall be reimplemented
  - Current `check_content_safety` function logic shall be reimplemented

- **SPEC-HOOK-012**: Current policy loading mechanisms shall be integrated into the new system
  - `load_bash_patterns`, `load_sensitive_patterns`, etc. shall be accessible through new interfaces

- **SPEC-HOOK-013**: Bootloader agent shall be updated to use new validation system
  - Current validation calls shall be replaced with new system calls
  - Maintain all existing security behaviors

## Architecture Design

### Core Components
1. **Event Dispatcher**: Routes events to appropriate validation functions
2. **Validation Functions**: Individual validation units that can allow, deny, modify, or request feedback
3. **Configuration Loader**: Loads YAML configuration files
4. **Prompt Loader**: Loads prompt templates from TXT/MD files

### Data Flow
1. Event occurs in the agent pipeline
2. Event is passed to appropriate validation function
3. Validation function evaluates the event using configured rules/patterns
4. Decision is made based on evaluation (allow, deny, modify, feedback)
5. Action is taken accordingly

## Technical Implementation Details

### Event Dispatcher
- Module: `ami/core/event_dispatcher.py`
- Function: `dispatch_event(event_type: EventType, content: str, context: dict) -> ValidationResult`
- The dispatcher will route events to appropriate validation functions based on event type
- Uses a registry pattern to map event types to validation functions
- Returns a ValidationResult with decision, message, and optional modified content

### Validation Functions
Each validation function will implement the interface:
```python
class ValidationFunction(ABC):
    @abstractmethod
    def validate(self, content: str, context: dict) -> ValidationResult:
        pass
```

Available validation functions:
- `UserQueryValidation`: Validates user queries against configured patterns/prompts
- `CodeExecutionValidation`: Validates code execution requests (replaces current guards)
- `AgentResponseValidation`: Validates agent responses before output

### Configuration Structure
New configuration file: `ami/config/validation.yaml`
```yaml
validation:
  user_query:
    enabled: true
    rules:
      - type: "pattern"
        pattern: "some_regex_pattern"
        action: "deny"
        message: "Description of violation"
      - type: "prompt"
        prompt_file: "prompts/query_validation.txt"
        action: "request_feedback"

  code_execution:
    enabled: true
    rules:
      - type: "pattern"
        pattern: "forbidden_command_pattern"
        action: "deny"
        message: "Forbidden command detected"
      - type: "prompt"
        prompt_file: "prompts/code_validation.txt"
        action: "allow"

  agent_response:
    enabled: true
    rules:
      - type: "pattern"
        pattern: "prohibited_content_pattern"
        action: "modify"
        message: "Content modified for compliance"
```

### Prompt Files
- Stored in `ami/config/prompts/` directory
- Loaded dynamically based on configuration
- Support Jinja-style templating for context injection
- Example: `ami/config/prompts/code_validation.txt`
```
Review the following code for security issues:
{{ content }}

Respond with "PASS" if safe, or "FAIL: reason" if problematic.
```

### Integration with Bootloader Agent
In `ami/core/bootloader_agent.py`, replace current guard calls:
- `execute_shell()` method: Replace `check_command_safety()` call with `dispatch_event(EventType.CODE_EXECUTION, ...)`
- `run()` method: Add validation for user queries and agent responses

### Integration with Policy Engine
Extend `ami/core/policies/engine.py` to load validation configurations:
- Add methods to load validation rules from YAML
- Cache loaded configurations for performance
- Maintain backward compatibility with existing policy loading

### ValidationResult Structure
```python
@dataclass
class ValidationResult:
    decision: ValidationDecision  # ALLOW, DENY, MODIFY, REQUEST_FEEDBACK
    message: Optional[str] = None
    modified_content: Optional[str] = None
    feedback: Optional[str] = None
```

## Implementation

### Core Implementation
- Implement simple event dispatcher in `ami/core/event_dispatcher.py`
- Create validation functions for each event type
- Implement YAML configuration loading using existing patterns from policy engine
- Implement prompt file loading with context injection
- Replace existing guard system calls with new system calls in bootloader agent
- Update policy engine to handle new validation configuration format

### Migration Steps
1. Create new validation modules alongside existing guards
2. Update bootloader agent to use new validation system
3. Test new system with existing functionality
4. Remove old guard system once validated

## Migration

### Complete Replacement
- The old guard system shall be completely replaced by the new system
- All existing functionality shall be reimplemented in the new architecture
- Security properties shall be maintained or enhanced in the new system

## Dependencies

### Internal Dependencies
- Current guard system in `ami/core/guards.py`
- Configuration system in `ami/core/config.py`
- Existing agent provider implementations
- Current prompt loading mechanisms
- Policy engine in `ami/core/policies/engine.py`

### External Dependencies
- YAML parser (already in use)
- Current LLM provider SDKs (Claude, Qwen, Gemini)

## Success Criteria

### Functional Success
- All existing security behaviors preserved or enhanced
- Ability to configure new validation rules without code deployment
- Successful interception and processing of all defined event types
- Proper integration with existing security measures
- Support for both pattern-based and LLM-based validation