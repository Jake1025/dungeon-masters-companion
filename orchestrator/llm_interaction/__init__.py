# orchestrator/llm_interaction/__init__.py

"""
1) Adapter ---------- How to talk to the model
2) Prompt Builders -- How to assemble context
3) Prompt Texts ----- What instructions to give
4) Step Engine ------ How one LLM operation behaves
5) Step Registry ---- Which operations exist


adapter.py
“How we talk to LLMs”
It is the transport + normalization layer.
So given a prompt and payload, how do we reliably get text or JSON from a model?
Nothing else in the system knows about Ollama, everything else just calls:
adapter.request_text(...) or adapter.request_json(...)


prompt_builders.py
“How we assemble context for LLMs”
It converts internal game state into prompt text.
PromptState shows a standardized way to represent what the LLM needs to know.
Each function builds the specific kind of prompt for the operations.


prompt_texts.py
“What instructions we give to LLMs”
It contains the actual text instructions we give to the LLMs.


step.py
“How one LLM operation behaves"
It is like a "unit of LLM work", a step is one structured LLM operation.
When this step runs, expect these sections, validate like this, parse like this.
Flow:
-call adapter
-parse sections
-validate
-parse
-return
It also adds "thoughts" and retries on invalid output.
Parsers:
"Convert text to python"
-parse_intent = dict
-parse_focus = list
-parse_narrative = string
Validators:
"Enforce rules on the output"
-validate_validation_step
-validate_narration_step


step_registry.py
"Which steps exist"
It maps/wires step names to step implementations.
{
  "intent": LLMStep(...),
  "plan": LLMStep(...),
  "validate": LLMStep(...),
  ...
}
It defines the catalog of LLM operations, it does not execute them.
"""